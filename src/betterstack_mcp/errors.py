"""Structured error envelope shared by every tool.

Per vendor-mcp-development SOP section 4.2: tools never raise, they return a
JSON string. Errors use a fixed, small vocabulary of codes so the calling
Agent can branch on ``code`` and decide on ``retryable`` without having to
parse a human-readable message.
"""

from __future__ import annotations

import json
from typing import Literal

ErrorCode = Literal[
    "not_configured",
    "unauthorized",
    "not_found",
    "invalid_argument",
    "rate_limited",
    "upstream_error",
]

# HTTP status -> error code. Checked in order; first match wins.
_STATUS_CODE_MAP: tuple[tuple[range, ErrorCode], ...] = (
    (range(401, 403), "unauthorized"),  # 401
    (range(403, 404), "unauthorized"),  # 403
    (range(404, 405), "not_found"),  # 404
    (range(400, 401), "invalid_argument"),  # 400
    (range(422, 423), "invalid_argument"),  # 422
    (range(429, 430), "rate_limited"),  # 429
)

_RETRYABLE: frozenset[ErrorCode] = frozenset({"rate_limited", "upstream_error"})


class BetterStackAPIError(Exception):
    """Raised by api_client.py when BetterStack's API returns an error.

    Carries the upstream HTTP status (or ``None`` for a network-level
    failure such as a timeout) so the tools layer can map it to a
    structured error code without re-parsing the response.
    """

    def __init__(self, message: str, *, status_code: int | None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def code_for_status(status_code: int | None) -> ErrorCode:
    """Map an upstream HTTP status (or None for network errors) to our code."""
    if status_code is None:
        return "upstream_error"
    if 500 <= status_code < 600:
        return "upstream_error"
    for status_range, code in _STATUS_CODE_MAP:
        if status_code in status_range:
            return code
    return "upstream_error"


def error_envelope(code: ErrorCode, message: str, *, retryable: bool | None = None) -> str:
    """Build the fixed JSON error envelope (serialized as a string).

    ``message`` must never contain the credential header value or the raw
    upstream response body (SOP section 4.2 / section 6).
    """
    if retryable is None:
        retryable = code in _RETRYABLE
    payload = {"error": {"code": code, "message": message, "retryable": retryable}}
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def error_from_api_exception(exc: BetterStackAPIError) -> str:
    """Build the error envelope for a caught BetterStackAPIError."""
    code = code_for_status(exc.status_code)
    return error_envelope(code, exc.message)
