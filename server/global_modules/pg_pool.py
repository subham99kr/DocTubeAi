import os
import logging
from dotenv import load_dotenv
from psycopg_pool import AsyncConnectionPool

load_dotenv()
POSTGRES_DB_URL = os.getenv("POSTGRES_DB_URL")

_PG_POOL = None

async def get_pg_pool():
    global _PG_POOL
    
    if _PG_POOL is None:
        logging.info("Initializing Postgres Connection Pool...")
        _PG_POOL = AsyncConnectionPool(
            conninfo=POSTGRES_DB_URL, 
            max_size=10,
            min_size=2,
            open=False
        )
        await _PG_POOL.open()
        await _PG_POOL.wait() # wait until min_size connections are ready
        logging.info("Postgres Connection Pool is open and ready.")
        
    return _PG_POOL

async def close_pg_pool():
    """
    shutdown the pool.
    Do it during exit.
    """
    global _PG_POOL
    if _PG_POOL:
        await _PG_POOL.close()
        _PG_POOL = None