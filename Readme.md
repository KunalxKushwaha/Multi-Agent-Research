# Research Pipeline Console

A multi-agent research assistant with a live web UI. Give it a topic, and four agents work it in sequence — search, read, write, critique — while you watch each stage complete in real time.

## How it works

1. **Search agent** finds recent, reliable sources on the topic
2. **Reader agent** picks the most relevant one and scrapes it for depth
3. **Writer chain** drafts a report from the combined research
4. **Critic chain** reviews the draft and gives feedback

Built with **LangChain** + **LangGraph** for the agent orchestration, **FastAPI** for the backend, and a vanilla HTML/CSS/JS frontend — no framework, just fetch + Server-Sent Events streaming progress live to the browser.

## Project structure

```
├── agents.py          # agent/chain definitions (search, reader, writer, critic)
├── tools.py            # tools used by the agents
├── pipeline.py          # original CLI entrypoint — still works standalone
├── server.py            # FastAPI backend, streams pipeline progress over SSE
├── requirements.txt
├── .env                 # API keys (not committed)
└── static/
    ├── index.html        # the UI
    └── favicon.svg
```

## Running locally

```bash
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

Open `http://localhost:8000`.

The original CLI still works too:
```bash
python pipeline.py
```

## Features

- Live progress across all 4 stages via SSE (no polling)
- Cancel a run mid-flight
- Run history saved locally — revisit past reports without re-running
- Auto-extracted source links from search results
- One-click Markdown export of the full report
- Word count / read-time estimate on the draft

## Deployment

Deployed for free on [Render](https://render.com) — see deployment notes for setup steps if you're forking this.

## Notes

This started as a CLI script and grew a web UI on top — the agent logic in `agents.py` is untouched by the web layer; `server.py` just wraps it and streams progress instead of printing to a terminal.