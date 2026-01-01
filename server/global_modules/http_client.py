import httpx
import logging

logger = logging.getLogger(__name__)

class HttpClientManager:
    _client: httpx.AsyncClient = None

    @classmethod
    async def get_client(cls) -> httpx.AsyncClient:
        """Returns the singleton instance of the AsyncClient."""
        if cls._client is None or cls._client.is_closed:
            cls._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                follow_redirects=True
            )
            logger.info("✅ Singleton HTTP Client Initialized")
        return cls._client

    @classmethod
    async def close_client(cls):
        """Closes the client connection pool."""
        if cls._client and not cls._client.is_closed:
            await cls._client.aclose()
            logger.info("🔴 Singleton HTTP Client Closed")


async def get_http_client() -> httpx.AsyncClient:
    return await HttpClientManager.get_client()