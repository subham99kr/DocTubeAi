
INSERT_USER_SQL = """
INSERT INTO public.users (user_id, oauth)
VALUES ($1, $2)
ON CONFLICT (user_id) DO NOTHING
"""
SELECT_USER_BY_OAUTH_SQL = """SELECT user_id FROM public.users WHERE oauth = $1"""
INSERT_SESSION_SQL = """
INSERT INTO public.sessions (session_id, user_id, checkpoint, last_activity)
VALUES ($1,$2,$3,now())
ON CONFLICT (session_id) DO NOTHING
"""
SELECT_SESSION_SQL = "SELECT session_id, user_id, checkpoint FROM public.sessions WHERE session_id = $1"

UPDATE_SESSION_CHECKPOINT_SQL = """
UPDATE public.sessions 
SET checkpoint = $1, last_activity = now()
WHERE session_id = $2
RETURNING session_id, checkpoint
"""