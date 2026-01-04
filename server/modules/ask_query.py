import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from nodes.tavily_search_node import internet_search
from nodes.vector_search_node import docs_or_Youtube_Transcript_or_knowledgeBase_Search
from nodes.web_scraper_node import web_scraper_node
from modules.llm import summary_llm,get_model
from langchain.messages import HumanMessage
from tavily import AsyncTavilyClient
from graph.graph_builder import RAGGraphBuilder
from global_modules.pg_pool import get_pg_pool
from global_modules.http_client import get_http_client



#more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


# defining global variable to for using singleton pattern
_CHECKPOINTER = None 
_COMPILED_GRAPH = None
_TAVILY_CLIENT = None

async def global_init():
    """This runs only once and makes required connections for everyone to use"""
    global  _CHECKPOINTER, _COMPILED_GRAPH, _TAVILY_CLIENT

    if _TAVILY_CLIENT is None:
        _TAVILY_CLIENT = AsyncTavilyClient(os.getenv("TAVILY_API_KEY"))
        logger.info("✅ Tavily Client Initialized")

        
    pool = await get_pg_pool()

    if _COMPILED_GRAPH is None:
        _CHECKPOINTER = AsyncPostgresSaver(pool)
        
        builder = RAGGraphBuilder(
            llm=get_model,
            summary_llm=summary_llm,
            tools=[docs_or_Youtube_Transcript_or_knowledgeBase_Search, internet_search, web_scraper_node]
        )
        _COMPILED_GRAPH = builder.compile(checkpointer=_CHECKPOINTER)
        logger.info("✅ LangGraph Compiled")

    return _COMPILED_GRAPH


async def ask_with_graph(obj: Dict[str, Any]) -> Dict[str, Any]:
    query = obj.get("users_query", "")
    session_id = obj.get("session_id")

    try:
        # 1. Validation
        if not query.strip():
            logger.warning(f"Empty query received for session {session_id}")
            return {"answer": "The query cannot be empty.", "code": 400}
        
        # 2. Initialization
        logger.info(f"🦜Starting graph execution for session: {session_id}")
        await global_init()

        http_client = await get_http_client()
        # 4. Setting up config
        config = {"configurable": {
            "thread_id": session_id,
            "tavily_client": _TAVILY_CLIENT,
            "http_client": http_client,    
            "session_id": session_id,
        }}
        
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "query": query,
        }

        # 5. Graph Invocation (Most likely place for errors)
        logger.info(f"Invoking graph for thread_id: {session_id}")
        result = await _COMPILED_GRAPH.ainvoke(initial_state, config)
        logger.info("✅ Graph invocation successful")

        # 6. Extracting Final Answer
        messages = result.get("messages", [])
        final_answer = "I'm sorry, I couldn't generate a response."
        
        for msg in reversed(messages):
            if msg.type == "ai" and msg.content:
                final_answer = msg.content
                break
        
        return {
            "answer": final_answer,
            "session_id": session_id,
            "status": "success",
            "code": 200,
        }

    except Exception as e:
        # exc_info=True captures the full traceback including the line number
        logger.error(f"🔴 Error in ask_with_graph for session {session_id}: {str(e)}", exc_info=True)
        return {
            "answer": "An internal error occurred during processing.",
            "status": "error",
            "code": 500
        }