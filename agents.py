from langchain.agents import create_agent
from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from tools import web_search , scrape_url 

from dotenv import load_dotenv

load_dotenv()

#model setup 
llm = ChatMistralAI(model = "mistral-small-2506",temperature=0)


## TOOLS
#1st agent 
def build_search_agent():
    return create_agent(
        model = llm,
        tools= [web_search]
    )

#2nd agent 

def build_reader_agent():
    return create_agent(
        model = llm,
        tools = [scrape_url]
    )


## RUNNABLES
#1. writer chain

writer_agent = ChatPromptTemplate([
    """You: """
])