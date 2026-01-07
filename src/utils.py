"""
Suzerain Utilities - Retry logic, connection pooling, and resilience features.

"He never sleeps, the judge. He is dancing, dancing."

This module provides:
- Reusable retry decorator with exponential backoff
- Connection pooling for HTTP requests
- HTTP client wrapper for Deepgram API
"""

import functools
import logging
import random
import socket
import ssl
import time
import urllib.error
import urllib.request
from http.client import HTTPConnection, HTTPSConnection, HTTPException
from typing import Callable, Optional, Tuple, Type, TypeVar, Union
from urllib.parse import urlparse

# Configure logging
logger = logging.getLogger(__name__)

T = TypeVar('T')


# === Retryable Exception Categories ===

# Network/transient errors that should be retried
RETRYABLE_EXCEPTIONS = (
    urllib.error.URLError,
    socket.timeout,
    TimeoutError,
    ConnectionError,
    ConnectionResetError,
    ConnectionRefusedError,
    BrokenPipeError,
    ssl.SSLError,
    HTTPException,
)

# HTTP status codes that should be retried (transient server errors)
RETRYABLE_HTTP_CODES = {
    408,  # Request Timeout
    429,  # Too Many Requests
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
}

# HTTP status codes that should NOT be retried (client errors, auth errors)
NON_RETRYABLE_HTTP_CODES = {
    400,  # Bad Request
    401,  # Unauthorized
    403,  # Forbidden
    404,  # Not Found
    405,  # Method Not Allowed
    422,  # Unprocessable Entity
}


# === Retry Decorator ===

def retry(
    max_attempts: int = 3,
    backoff: str = "exponential",
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retry_on: Tuple[Type[Exception], ...] = RETRYABLE_EXCEPTIONS,
    retry_on_http_codes: set = None,
    on_retry: Callable[[Exception, int, float], None] = None,
    jitter: bool = True,
):
    """
    Decorator for retry with configurable backoff strategy.

    Args:
        max_attempts: Maximum number of attempts (including first try)
        backoff: Backoff strategy - "exponential", "linear", or "constant"
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        retry_on: Tuple of exception types to retry on
        retry_on_http_codes: Set of HTTP status codes to retry on (default: 5xx)
        on_retry: Callback called before each retry (exception, attempt, delay)
        jitter: Add random jitter to delay (helps avoid thundering herd)

    Example:
        @retry(max_attempts=3, backoff="exponential", retry_on=(NetworkError, TimeoutError))
        def transcribe_audio(...):
            ...
    """
    if retry_on_http_codes is None:
        retry_on_http_codes = RETRYABLE_HTTP_CODES

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except urllib.error.HTTPError as e:
                    # Check if HTTP error should be retried
                    if e.code in NON_RETRYABLE_HTTP_CODES:
                        # Auth errors and client errors - don't retry
                        raise
                    elif e.code in retry_on_http_codes:
                        last_exception = e
                    else:
                        # Unknown status code - don't retry by default
                        raise
                except retry_on as e:
                    last_exception = e
                except Exception:
                    # Unknown exception - don't retry
                    raise

                # Check if we've exhausted retries
                if attempt >= max_attempts:
                    break

                # Calculate delay
                delay = _calculate_delay(
                    attempt, backoff, base_delay, max_delay, jitter
                )

                if on_retry:
                    on_retry(last_exception, attempt, delay)

                logger.warning(
                    f"Retry {attempt}/{max_attempts} for {func.__name__} "
                    f"after {delay:.1f}s: {last_exception}"
                )

                time.sleep(delay)

            # All retries exhausted
            raise last_exception

        return wrapper
    return decorator


def _calculate_delay(
    attempt: int,
    backoff: str,
    base_delay: float,
    max_delay: float,
    jitter: bool
) -> float:
    """Calculate delay for a given attempt."""
    if backoff == "exponential":
        delay = base_delay * (2 ** (attempt - 1))
    elif backoff == "linear":
        delay = base_delay * attempt
    else:  # constant
        delay = base_delay

    # Cap at max delay
    delay = min(delay, max_delay)

    # Add jitter (10-30% of delay)
    if jitter:
        jitter_amount = delay * random.uniform(0.1, 0.3)
        delay += jitter_amount

    return delay


# === Connection Pooling ===

class HTTPConnectionPool:
    """
    Simple HTTP connection pool for reusing connections.

    Keeps connections alive to avoid TCP handshake overhead
    on repeated requests to the same host.

    Usage:
        pool = HTTPConnectionPool()
        with pool.get_connection("api.deepgram.com", 443, https=True) as conn:
            conn.request("POST", "/v1/listen", body=audio_data, headers=headers)
            response = conn.getresponse()
    """

    def __init__(self, max_connections_per_host: int = 4, timeout: float = 10.0):
        self._pools: dict = {}
        self._max_connections = max_connections_per_host
        self._timeout = timeout

    def get_connection(
        self,
        host: str,
        port: int = 443,
        https: bool = True
    ) -> Union[HTTPConnection, HTTPSConnection]:
        """
        Get a connection from the pool, or create a new one.

        Returns a connection that should be used in a context manager
        or manually closed.
        """
        key = (host, port, https)

        # Check for existing idle connection
        if key in self._pools:
            connections = self._pools[key]
            while connections:
                conn = connections.pop(0)
                # Test if connection is still alive
                try:
                    # Check socket state
                    if conn.sock is not None:
                        return conn
                except Exception:
                    pass

        # Create new connection
        if https:
            context = ssl.create_default_context()
            conn = HTTPSConnection(host, port, timeout=self._timeout, context=context)
        else:
            conn = HTTPConnection(host, port, timeout=self._timeout)

        return conn

    def return_connection(
        self,
        conn: Union[HTTPConnection, HTTPSConnection],
        host: str,
        port: int = 443,
        https: bool = True
    ):
        """Return a connection to the pool for reuse."""
        key = (host, port, https)

        if key not in self._pools:
            self._pools[key] = []

        # Only pool if we haven't exceeded max
        if len(self._pools[key]) < self._max_connections:
            self._pools[key].append(conn)
        else:
            # Close excess connections
            conn.close()

    def close_all(self):
        """Close all pooled connections."""
        for key, connections in self._pools.items():
            for conn in connections:
                try:
                    conn.close()
                except Exception:
                    pass
        self._pools.clear()


# Global connection pool instance
_connection_pool: Optional[HTTPConnectionPool] = None


def get_connection_pool() -> HTTPConnectionPool:
    """Get or create the global connection pool."""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = HTTPConnectionPool()
    return _connection_pool


def close_connection_pool():
    """Close the global connection pool."""
    global _connection_pool
    if _connection_pool is not None:
        _connection_pool.close_all()
        _connection_pool = None


# === Pooled HTTP Client ===

class PooledHTTPClient:
    """
    HTTP client that uses connection pooling.

    Example:
        client = PooledHTTPClient()
        response = client.request(
            "POST",
            "https://api.deepgram.com/v1/listen",
            body=audio_data,
            headers={"Authorization": "Token xxx"}
        )
    """

    def __init__(self, pool: HTTPConnectionPool = None, timeout: float = 10.0):
        self._pool = pool or get_connection_pool()
        self._timeout = timeout

    def request(
        self,
        method: str,
        url: str,
        body: bytes = None,
        headers: dict = None,
    ) -> Tuple[int, dict, bytes]:
        """
        Make an HTTP request using a pooled connection.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL
            body: Request body (bytes)
            headers: Request headers

        Returns:
            Tuple of (status_code, response_headers, response_body)

        Raises:
            urllib.error.HTTPError: On HTTP errors
            urllib.error.URLError: On network errors
        """
        parsed = urlparse(url)
        https = parsed.scheme == "https"
        port = parsed.port or (443 if https else 80)
        host = parsed.hostname
        path = parsed.path
        if parsed.query:
            path += "?" + parsed.query

        headers = headers or {}
        headers["Host"] = host
        headers["Connection"] = "keep-alive"

        conn = self._pool.get_connection(host, port, https)

        try:
            conn.request(method, path, body=body, headers=headers)
            response = conn.getresponse()

            status = response.status
            resp_headers = dict(response.getheaders())
            resp_body = response.read()

            # Return connection to pool if successful
            if status < 400:
                self._pool.return_connection(conn, host, port, https)
            else:
                conn.close()
                # Raise HTTPError for error status codes
                raise urllib.error.HTTPError(
                    url, status, response.reason, resp_headers, None
                )

            return status, resp_headers, resp_body

        except Exception as e:
            # Don't return errored connections to pool
            try:
                conn.close()
            except Exception:
                pass

            if isinstance(e, urllib.error.HTTPError):
                raise

            # Wrap other exceptions as URLError
            raise urllib.error.URLError(str(e)) from e


# Global pooled client instance
_pooled_client: Optional[PooledHTTPClient] = None


def get_pooled_client() -> PooledHTTPClient:
    """Get or create the global pooled HTTP client."""
    global _pooled_client
    if _pooled_client is None:
        _pooled_client = PooledHTTPClient()
    return _pooled_client


# === Helper Functions ===

def is_retryable_error(exception: Exception) -> bool:
    """Check if an exception is retryable."""
    if isinstance(exception, urllib.error.HTTPError):
        return exception.code in RETRYABLE_HTTP_CODES
    return isinstance(exception, RETRYABLE_EXCEPTIONS)


def is_auth_error(exception: Exception) -> bool:
    """Check if an exception is an authentication/authorization error."""
    if isinstance(exception, urllib.error.HTTPError):
        return exception.code in (401, 403)
    return False
