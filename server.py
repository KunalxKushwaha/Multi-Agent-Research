"""
server.py
---------
Drop this file into the SAME folder as your existing agents.py, tools.py,
pipeline.py and .env.

It exposes your `run_research_pipeline` logic over HTTP so the web UI
(static/index.html) can drive it, and streams progress for each of the
four stages (search -> reader -> writer -> critic) live to the browser
using Server-Sent Events (SSE), instead of making the user wait for the
whole pipeline to finish before seeing anything.

Run it with:
    pip install fastapi uvicorn sse-starlette
    uvicorn server:app --reload --port 8000

Then open http://localhost:8000 in your browser.

Your original pipeline.py / CLI usage is untouched -- this file only
*reuses* build_search_agent, build_reader_agent, writer_chain and
critic_chain from your agents.py, it does not modify them.
"""

import json
import queue
import threading
import traceback
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agents import build_reader_agent, build_search_agent, writer_chain, critic_chain

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Research Pipeline Console")

# Dev-friendly CORS. Tighten this to your real origin before deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ResearchRequest(BaseModel):
    topic: str


def _content_of(result) -> str:
    """
    Agent/chain outputs vary: langgraph agents return {"messages":[...]},
    LCEL chains might return a plain string or an AIMessage-like object
    with a `.content` attribute. This normalizes any of those to a string
    so the UI always gets plain text.
    """
    if isinstance(result, dict) and "messages" in result:
        return result["messages"][-1].content
    if hasattr(result, "content"):
        return result.content
    return str(result)


def _run_pipeline(topic: str, q: "queue.Queue"):
    """Runs in a background thread; pushes progress events onto q."""

    def emit(stage: str, status: str, **payload):
        q.put({"stage": stage, "status": status, **payload})

    state = {}
    try:
        # ---- Step 1: Search ----------------------------------------
        emit("search", "running", message="Searching for recent, reliable sources...")
        search_agent = build_search_agent()
        search_result = search_agent.invoke(
            {"messages": [("user", f"Find recent, reliable and detailed information about: {topic}")]}
        )
        state["search_results"] = _content_of(search_result)
        emit("search", "done", output=state["search_results"])

        # ---- Step 2: Reader ------------------------------------------
        emit("reader", "running", message="Scraping the most relevant source for deeper content...")
        reader_agent = build_reader_agent()
        reader_result = reader_agent.invoke(
            {
                "messages": [
                    (
                        "user",
                        f"Based on the following search results about '{topic}', "
                        f"pick the most relevant URL and scrape it for deeper content.\n\n"
                        f"Search Results:\n{state['search_results'][:800]}",
                    )
                ]
            }
        )
        state["scraped_content"] = _content_of(reader_result)
        emit("reader", "done", output=state["scraped_content"])

        # ---- Step 3: Writer --------------------------------------------
        emit("writer", "running", message="Drafting the report...")
        research_combined = (
            f"SEARCH RESULTS : \n {state['search_results']} \n\n"
            f"DETAILED SCRAPED CONTENT : \n {state['scraped_content']}"
        )
        report_result = writer_chain.invoke({"topic": topic, "research": research_combined})
        state["report"] = _content_of(report_result)
        emit("writer", "done", output=state["report"])

        # ---- Step 4: Critic -------------------------------------------
        emit("critic", "running", message="Reviewing the report...")
        feedback_result = critic_chain.invoke({"report": state["report"]})
        state["feedback"] = _content_of(feedback_result)
        emit("critic", "done", output=state["feedback"])

        emit("pipeline", "complete", state=state)

    except Exception as exc:  # noqa: BLE001
        emit("pipeline", "error", message=str(exc), trace=traceback.format_exc())


@app.get("/")
def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.post("/api/research/stream")
def research_stream(req: ResearchRequest):
    topic = req.topic.strip()
    if not topic:
        def err():
            yield f"data: {json.dumps({'stage': 'pipeline', 'status': 'error', 'message': 'Topic cannot be empty.'})}\n\n"
        return StreamingResponse(err(), media_type="text/event-stream")

    q: "queue.Queue" = queue.Queue()
    thread = threading.Thread(target=_run_pipeline, args=(topic, q), daemon=True)
    thread.start()

    def event_stream():
        while True:
            event = q.get()
            yield f"data: {json.dumps(event)}\n\n"
            if event["stage"] == "pipeline" and event["status"] in ("complete", "error"):
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")
