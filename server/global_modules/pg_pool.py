import logging
import os

from dotenv import load_dotenv
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

load_dotenv()

POSTGRES_DB_URL = os.getenv("POSTGRES_DB_URL")

_PG_POOL: AsyncConnectionPool | None = None


async def get_pg_pool() -> AsyncConnectionPool:
    global _PG_POOL

    if _PG_POOL is None:
        logger.info("Initializing Postgres Connection Pool...")

        _PG_POOL = AsyncConnectionPool(
            conninfo=POSTGRES_DB_URL,
            max_size=10,
            min_size=2,
            open=False,
            check=AsyncConnectionPool.check_connection,
            max_idle=600,
            timeout=30.0,
            kwargs={
                "keepalives": 1,
                "keepalives_idle": 60,
                "keepalives_interval": 10,
                "keepalives_count": 5,
            },
        )

        await _PG_POOL.open()

        await _PG_POOL.wait()

        logger.info("Postgres Connection Pool is open.")

    return _PG_POOL


async def close_pg_pool() -> None:
    global _PG_POOL

    pool = _PG_POOL

    if pool is None:
        return

    logger.info("Closing Postgres Connection Pool...")

    _PG_POOL = None

    await pool.close()

    logger.info("Postgres Connection Pool closed.")
