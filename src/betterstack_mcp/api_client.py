"""Thin async wrapper around BetterStack's Uptime/Incidents REST API.

One instance is created per inbound /mcp request (see server.py's
credential middleware) and reused for every upstream call made while
handling that request -- never cached across requests, never shared
between tenants (vendor-mcp-development SOP section 3.4 / section 5).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from betterstack_mcp.errors import BetterStackAPIError
from betterstack_mcp.telemetry import current_request_id

logger = logging.getLogger("betterstack_mcp.api_client")

CONNECT_TIMEOUT_S = 5.0
READ_TIMEOUT_S = 30.0
MAX_RETRIES = 3
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
DEFAULT_RETRY_AFTER_S = 2.0
MAX_BACKOFF_S = 20.0

# Indirection so tests can patch out the backoff wait without touching the
# global asyncio.sleep used elsewhere in the process.
_sleep = asyncio.sleep


class BetterStackClient:
    """Async client for one request's worth of BetterStack API calls."""

    def __init__(self, token: str, base_url: str) -> None:
        self._token = token
        self._http = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(connect=CONNECT_TIMEOUT_S, read=READ_TIMEOUT_S, write=READ_TIMEOUT_S, pool=READ_TIMEOUT_S),
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "BetterStackClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Issue one request with limited retry on 429/5xx, backoff + Retry-After.

        Every attempt is logged at request scope (request_id from
        ``telemetry.current_request_id()``) with the path, outcome, status
        code (when there is one), and this call's running duration -- on
        the success path too, not just on warning/retry (SOP section 6).
        Never logs the request/response body or the credential header; see
        ``_safe_message`` for the one place an upstream body is touched.
        """
        request_id = current_request_id()
        start = time.monotonic()
        attempt = 0
        last_exc: BetterStackAPIError | None = None
        while attempt <= MAX_RETRIES:
            try:
                response = await self._http.request(method, path, params=params, json=json_body)
            except httpx.TimeoutException:
                last_exc = BetterStackAPIError(f"Request to {path} timed out", status_code=None)
                logger.warning(
                    "request_id=%s method=%s path=%s attempt=%s outcome=timeout",
                    request_id, method, path, attempt,
                )
            except httpx.TransportError as exc:
                last_exc = BetterStackAPIError(f"Network error calling {path}: {type(exc).__name__}", status_code=None)
                logger.warning(
                    "request_id=%s method=%s path=%s attempt=%s outcome=network_error error=%s",
                    request_id, method, path, attempt, type(exc).__name__,
                )
            else:
                if response.status_code < 400:
                    duration_ms = (time.monotonic() - start) * 1000
                    logger.info(
                        "request_id=%s method=%s path=%s attempt=%s status=%s duration_ms=%.1f outcome=ok",
                        request_id, method, path, attempt, response.status_code, duration_ms,
                    )
                    if response.status_code == 204 or not response.content:
                        return None
                    return response.json()
                if response.status_code not in RETRYABLE_STATUS or attempt == MAX_RETRIES:
                    duration_ms = (time.monotonic() - start) * 1000
                    logger.warning(
                        "request_id=%s method=%s path=%s attempt=%s status=%s duration_ms=%.1f outcome=error",
                        request_id, method, path, attempt, response.status_code, duration_ms,
                    )
                    message = _safe_message(response)
                    raise BetterStackAPIError(message, status_code=response.status_code)
                last_exc = BetterStackAPIError(_safe_message(response), status_code=response.status_code)
                delay = _retry_delay(response, attempt)
                logger.warning(
                    "request_id=%s method=%s path=%s attempt=%s status=%s outcome=retrying delay_s=%.1f",
                    request_id, method, path, attempt, response.status_code, delay,
                )
                await _sleep(delay)
                attempt += 1
                continue
            attempt += 1
            if attempt > MAX_RETRIES:
                break
            await _sleep(_retry_delay(None, attempt))
        duration_ms = (time.monotonic() - start) * 1000
        logger.warning(
            "request_id=%s method=%s path=%s attempt=%s duration_ms=%.1f outcome=exhausted",
            request_id, method, path, attempt, duration_ms,
        )
        assert last_exc is not None
        raise last_exc


def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return min(float(retry_after), MAX_BACKOFF_S)
            except ValueError:
                pass
    backoff = DEFAULT_RETRY_AFTER_S * (2**attempt)
    return min(backoff, MAX_BACKOFF_S)


def _safe_message(response: httpx.Response) -> str:
    """Build an error message that never echoes the full upstream body (SOP section 4.2)."""
    return f"BetterStack API returned HTTP {response.status_code} for {response.request.method} {response.request.url.path}"
