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
        
        # We add 'check' and 'max_idle' to handle long-term idleness
        _PG_POOL = AsyncConnectionPool(
            conninfo=POSTGRES_DB_URL, 
            max_size=10,
            min_size=2,
            open=False,
            # 1. Check if the connection is alive before giving it to a function
            check=AsyncConnectionPool.check_connection,
            # 2. Automatically close connections that have been idle for more than 10 minutes
            max_idle=600,
            # 3. Connection timeout settings
            timeout=30.0,
            kwargs={
                "keepalives": 1,
                "keepalives_idle": 60,
                "keepalives_interval": 10,
                "keepalives_count": 5,
            }
        )
        await _PG_POOL.open()
        await _PG_POOL.wait() 
        logging.info("Postgres Connection Pool is open with Keep-Alives enabled.")
        
    return _PG_POOL

async def close_pg_pool():
    global _PG_POOL
    if _PG_POOL:
        await _PG_POOL.close()
        _PG_POOL = None