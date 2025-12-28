# postgres_helper.py
import uuid
import asyncpg

INSERT_USER_SQL = """
INSERT INTO public.users (userId, oauth)
VALUES ($1, $2)
ON CONFLICT (userId) DO NOTHING
"""

SELECT_USER_BY_OAUTH_SQL = "SELECT userId FROM public.users WHERE oauth = $1"

INSERT_SESSION_SQL = """
INSERT INTO public.sessions (session_id, user_id, checkpoint, last_activity)
VALUES ($1, $2, $3, now())
ON CONFLICT (session_id) DO NOTHING
"""

SELECT_SESSION_SQL = "SELECT session_id, user_id, checkpoint FROM public.sessions WHERE session_id = $1"

UPDATE_SESSION_CHECKPOINT_SQL = """
UPDATE public.sessions
SET checkpoint = $1, last_activity = now()
WHERE session_id = $2
RETURNING session_id, checkpoint
"""

INSERT_CHECKPOINT_HISTORY_SQL = """
INSERT INTO public.checkpoints_history (id, session_id, checkpoint_id, created_at)
VALUES ($1, $2, $3, now())
"""

async def ensure_user(conn: asyncpg.Connection, oauth_id: str | None) -> str | None:
    """Return userId (existing) or create new one. If oauth_id falsy -> None."""
    if not oauth_id:
        return None
    row = await conn.fetchrow(SELECT_USER_BY_OAUTH_SQL, oauth_id)
    if row:
        return row["userid"] if "userid" in row.keys() else row[0]  # defensive
    # create new userId (use uuid or use oauth_id as userId if that fits)
    new_user_id = str(uuid.uuid4())
    await conn.execute(INSERT_USER_SQL, new_user_id, oauth_id)
    return new_user_id

async def ensure_session(conn: asyncpg.Connection, session_id: str | None, user_id: str | None) -> dict:
    """
    Ensure a session row exists. If session_id is None, create new session_id and row.
    Returns session row as dict with keys: session_id, user_id, checkpoint.
    """
    if not session_id:
        session_id = f"session::{str(uuid.uuid4())}"
        await conn.execute(INSERT_SESSION_SQL, session_id, user_id, None)
        row = await conn.fetchrow(SELECT_SESSION_SQL, session_id)
        return dict(row)
    # Insert if missing (ON CONFLICT DO NOTHING)
    await conn.execute(INSERT_SESSION_SQL, session_id, user_id, None)
    row = await conn.fetchrow(SELECT_SESSION_SQL, session_id)
    return dict(row)

async def update_session_checkpoint(conn: asyncpg.Connection, session_id: str, checkpoint_id: str):
    """Update sessions and append to checkpoint history."""
    await conn.execute(UPDATE_SESSION_CHECKPOINT_SQL, checkpoint_id, session_id)
    await conn.execute(INSERT_CHECKPOINT_HISTORY_SQL, str(uuid.uuid4()), session_id, checkpoint_id)
