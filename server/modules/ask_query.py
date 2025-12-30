import os
import uuid
import logging
import httpx
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
_HTTP_CLIENT = None

async def global_init():
    """This runs only once and makes required connections for everyone to use"""
    global  _CHECKPOINTER, _COMPILED_GRAPH, _TAVILY_CLIENT, _HTTP_CLIENT

    if _TAVILY_CLIENT is None:
        _TAVILY_CLIENT = AsyncTavilyClient(os.getenv("TAVILY_API_KEY"))
        logger.info("✅ Tavily Client Initialized")

    if _HTTP_CLIENT is None:
        _HTTP_CLIENT = httpx.AsyncClient(timeout=httpx.Timeout(30.0), follow_redirects=True)
        logger.info("✅ HTTP Client Initialized")
        
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

async def _get_or_create_user(oauth_id: str) -> str:
    oauth_str = oauth_id or "guest_user"
    pool = await get_pg_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT userId FROM public.users WHERE oauth = %s", (oauth_str,))
            row = await cur.fetchone()
            if row:
                return row[0]
            
            user_id = str(uuid.uuid4())
            await cur.execute(
                "INSERT INTO public.users (userId, oauth) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (user_id, oauth_str)
            )
            return user_id

async def _ensure_session(session_id: str, user_id: str) -> str:
    """Ensures session exists and returns the session_id."""
    pool = await get_pg_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT session_id FROM public.sessions WHERE session_id = %s", (session_id,))
            row = await cur.fetchone()
            if not row:
                await cur.execute(
                    "INSERT INTO public.sessions (session_id, user_id, last_activity) VALUES (%s, %s, now())",
                    (session_id, user_id)
                )
            return session_id

async def ask_with_graph(obj: Dict[str, Any]) -> Dict[str, Any]:
    query = obj.get("users_query", "")
    session_id = obj.get("session_id")
    oauth_id = obj.get("oauthID")

    try:
        # 1. Validation
        if not query.strip():
            logger.warning(f"Empty query received for session {session_id}")
            return {"answer": "The query cannot be empty.", "code": 400}
        
        # 2. Initialization
        logger.info(f"🦜Starting graph execution for session: {session_id}")
        await global_init()

        # 3. User & Session Setup
        logger.info("Setting up user and session...")
        user_id = await _get_or_create_user(oauth_id)
        await _ensure_session(session_id, user_id)

        # 4. Setting up config
        config = {"configurable": {
            "thread_id": session_id,
            "tavily_client": _TAVILY_CLIENT,
            "http_client": _HTTP_CLIENT,    
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
            "answer": str(final_answer),
            "session_id": session_id,
            "status": "success",
            "code": 200,
        }

    except Exception as e:
        # exc_info=True captures the full traceback including the line number
        logger.error(f"❌ Error in ask_with_graph for session {session_id}: {str(e)}", exc_info=True)
        return {
            "answer": "An internal error occurred during processing.",
            "status": "error",
            "code": 500
        }