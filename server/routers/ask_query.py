# ask_query.py
import os
import uuid
import asyncio
import asyncpg
import json
from dotenv import load_dotenv
from pymongo import MongoClient
import psycopg2  # sync DB client used by SyncPostgresCheckpointer

load_dotenv()

POSTGRES_DB_URL = os.getenv("POSTGRES_DB_URL")  # e.g. postgres://user:pw@host:port/dbname
MONGO_URI = os.getenv("MONGODB_URI")
MONGO_DB = os.getenv("MONGO_DB", "rag_db")
MONGO_COLL = os.getenv("MONGO_COLL", "documents")
VECTOR_INDEX_NAME = os.getenv("MONGO_VECTOR_INDEX", "embedding_index")

# LLM factory (your code)
from modules.llm import get_llm_chain  # should return a callable or object with .invoke
from graph.graph_builder import RAGGraphBuilder

# SQL (adjust to your schema)
INSERT_USER_SQL = "INSERT INTO public.users (user_id, oauth) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING"
SELECT_USER_BY_OAUTH_SQL = "SELECT user_id FROM public.users WHERE oauth = $1"
INSERT_SESSION_SQL = "INSERT INTO public.sessions (session_id, user_id, checkpoint, last_activity) VALUES ($1,$2,$3,now()) ON CONFLICT (session_id) DO NOTHING"
SELECT_SESSION_SQL = "SELECT session_id, user_id, checkpoint FROM public.sessions WHERE session_id = $1"
UPDATE_SESSION_CHECKPOINT_SQL = "UPDATE public.sessions SET checkpoint = $1, last_activity = now() WHERE session_id = $2 RETURNING session_id, checkpoint"
INSERT_CHECKPOINT_HISTORY_SQL = "INSERT INTO public.checkpoint_history (id, session_id, checkpoint, payload, created_at) VALUES ($1,$2,$3,$4,now())"

_COMPILED_GRAPH = None
_MONGO_CLIENT = None
_CHECKPOINTER = None

# ---------- Small sync checkpointer implementation ----------
class SyncPostgresCheckpointer:
    """
    Synchronous checkpointer that saves a serialized payload into checkpoint_history and returns checkpoint id.
    We use psycopg2 here (blocking) and call this object from the graph node (sync).
    """
    def __init__(self, pg_dsn):
        self.dsn = pg_dsn

    def save(self, thread_id: str, payload: dict) -> str:
        """
        Save payload (dict) for thread_id, return checkpoint_str (UUID).
        Also insert into checkpoint_history table as JSON payload.
        """
        checkpoint_id = str(uuid.uuid4())
        payload_json = json.dumps(payload, default=str)
        conn = psycopg2.connect(self.dsn)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO public.checkpoint_history (id, session_id, checkpoint, payload, created_at) VALUES (%s,%s,%s,%s,now())",
                    (checkpoint_id, thread_id, checkpoint_id, payload_json)
                )
                # Also update sessions table short-term checkpoint if you want immediate short-term update:
                cur.execute(
                    "UPDATE public.sessions SET checkpoint=%s, last_activity=now() WHERE session_id=%s",
                    (checkpoint_id, thread_id)
                )
                conn.commit()
        finally:
            conn.close()
        return checkpoint_id

    def load(self, thread_id: str):
        """
        Load the latest checkpoint payload for a thread (optional).
        """
        conn = psycopg2.connect(self.dsn)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT payload FROM public.checkpoint_history WHERE session_id=%s ORDER BY created_at DESC LIMIT 1",
                    (thread_id,)
                )
                row = cur.fetchone()
                if not row:
                    return None
                return json.loads(row[0])
        finally:
            conn.close()


# ---------- init_once: build singletons ----------
async def init_once():
    global _COMPILED_GRAPH, _MONGO_CLIENT, _CHECKPOINTER
    if _COMPILED_GRAPH:
        return _COMPILED_GRAPH

    # create Mongo client
    _MONGO_CLIENT = MongoClient(MONGO_URI)

    # create llm object/callable
    llm_obj = get_llm_chain()  # may be a chain object or callable
    # normalize to a callable (prefer .invoke if present)
    if hasattr(llm_obj, "invoke"):
        llm_fn = llm_obj.invoke
    else:
        llm_fn = llm_obj

    # create sync checkpointer (we will call it in the graph nodes)
    _CHECKPOINTER = SyncPostgresCheckpointer(pg_dsn=POSTGRES_DB_URL)

    # build graph and compile
    builder = RAGGraphBuilder(llm_callable=llm_fn,
                              mongo_client=_MONGO_CLIENT,
                              mongo_db_name=MONGO_DB,
                              mongo_coll_name=MONGO_COLL,
                              vector_index_name=VECTOR_INDEX_NAME,
                              checkpointer=_CHECKPOINTER)
    compiled = builder.build_rag_graph()
    _COMPILED_GRAPH = compiled
    return _COMPILED_GRAPH

# ---------- Postgres helpers (async) ----------
async def _ensure_user(conn, oauth_id):
    if not oauth_id:
        return None
    row = await conn.fetchrow(SELECT_USER_BY_OAUTH_SQL, oauth_id)
    if row:
        return row["user_id"]
    new_user_id = str(uuid.uuid4())
    await conn.execute(INSERT_USER_SQL, new_user_id, oauth_id)
    return new_user_id

async def _ensure_session(conn, session_id, user_id):
    if not session_id:
        session_id = f"session::{uuid.uuid4()}"
        await conn.execute(INSERT_SESSION_SQL, session_id, user_id, None)
        row = await conn.fetchrow(SELECT_SESSION_SQL, session_id)
        return row
    await conn.execute(INSERT_SESSION_SQL, session_id, user_id, None)
    row = await conn.fetchrow(SELECT_SESSION_SQL, session_id)
    return row

async def _update_session_checkpoint(conn, session_id, checkpoint, payload_json=None):
    # update sessions table short-term
    await conn.execute(UPDATE_SESSION_CHECKPOINT_SQL, checkpoint, session_id)
    # insert into checkpoint_history with payload
    await conn.execute(INSERT_CHECKPOINT_HISTORY_SQL, str(uuid.uuid4()), session_id, checkpoint, payload_json or "{}")

# ---------- ask_with_graph (main request) ----------
async def ask_with_graph(obj: dict):
    """
    obj:
      - users_query (required)
      - session_id (optional)
      - oauthID (optional)
      - query_vector (optional)
      - flags ...
    """
    users_query = obj.get("users_query")
    if not users_query:
        raise ValueError("users_query required")
    session_id = obj.get("session_id")
    oauthID = obj.get("oauthID")

    # 1) ensure DB rows (async)
    conn = await asyncpg.connect(POSTGRES_DB_URL)
    try:
        user_id = await _ensure_user(conn, oauthID)
        session_row = await _ensure_session(conn, session_id, user_id)
        session_id = session_row["session_id"]
        existing_checkpoint = session_row.get("checkpoint")
    finally:
        await conn.close()

    # 2) init graph
    compiled = await init_once()

    # 3) prepare state (include existing_checkpoint so nodes can use it)
    state = {
        "messages": [{"role": "user", "content": users_query}],
        "users_query": users_query,
        "session_id": session_id,
        "user_id": user_id,
        "checkpoint": existing_checkpoint,
        "query_vector": obj.get("query_vector"),
        "numCandidates": obj.get("numCandidates", 150),
        "limit": obj.get("limit", 5),
        "force_use_internet": obj.get("force_use_internet", False),
        "prefer_vector_first": obj.get("prefer_vector_first", True)
    }

    # 4) run the compiled graph
    # Many compiled graphs provide .run(state, config) or .stream(...)
    if hasattr(compiled, "run"):
        # compiled.run may be awaitable or sync — we assume awaitable
        if asyncio.iscoroutinefunction(compiled.run):
            result_state = await compiled.run(state, {"configurable": {"session_id": session_id, "userId": user_id}})
        else:
            # sync run: run in thread so we don't block event loop (the nodes are sync)
            result_state = await asyncio.to_thread(compiled.run, state, {"configurable": {"session_id": session_id, "userId": user_id}})
    else:
        # use streaming API and collect last chunk
        last = None
        async for chunk in compiled.stream(state, {"configurable": {"session_id": session_id, "userId": user_id}, "streamMode": "values"}):
            last = chunk
        result_state = last

    # 5) extract answer and checkpoint (the checkpoint node writes "checkpoint" into result_state)
    answer_text = result_state.get("answer") or (result_state.get("messages") and result_state["messages"][-1].get("content"))
    checkpoint_str = result_state.get("checkpoint")

    # If graph didn't produce checkpoint (e.g. checkpointer missing), create one and persist with the state
    if not checkpoint_str:
        # create checkpoint payload and call the synchronous checkpointer in a thread
        payload = {"messages": result_state.get("messages"), "user_id": user_id}
        checkpoint_str = await asyncio.to_thread(_CHECKPOINTER.save, session_id, payload)

    # 6) persist short-term session checkpoint and a json payload to checkpoint_history (async)
    payload_json = json.dumps({"messages": result_state.get("messages"), "user_id": user_id}, default=str)
    conn = await asyncpg.connect(POSTGRES_DB_URL)
    try:
        await _update_session_checkpoint(conn, session_id, checkpoint_str, payload_json)
    finally:
        await conn.close()

    return {"session_id": session_id, "answer": answer_text, "checkpoint": checkpoint_str}
