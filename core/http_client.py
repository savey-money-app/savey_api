"""Shared HTTP client for external API calls"""

import httpx
from typing import Optional

class HTTPClientManager:
    """
    Manages a single shared httpx.AsyncClient instance for reuse across requests.
    This avoids creating new TCP connections on every request.
    """

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    def get_client(self) -> httpx.AsyncClient:
        """Get or create the shared HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(
                    max_keepalive_connections=20,
                    max_connections=50,
                    keepalive_expiry=30.0,
                ),
                # Connection pooling settings
                http2=True,  # Enable HTTP/2 for better performance
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


# Global instance
http_client_manager = HTTPClientManager()


def get_http_client() -> httpx.AsyncClient:
    """Get the shared HTTP client. Use this in your endpoints."""
    return http_client_manager.get_client()


async def close_http_client():
    """Close the HTTP client. Call during app shutdown."""
    await http_client_manager.close()
