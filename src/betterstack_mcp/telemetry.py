"""Per-call structured logging: every tool invocation gets a request-id that
is threaded through to the upstream HTTP client, so one line of logs can be
correlated end to end (vendor-mcp-development SOP section 6 / section 14
checklist: "structured logs carry a request-id").

Only the *shape* of the arguments (their names) is logged, never their
values -- this service has no way to know in advance which future tool might
grow a sensitive parameter, so redaction is the default rather than an
opt-in per field. Credentials never reach here at all: they live in
server.py's own ContextVar and are never passed into a tool's arguments.
"""

from __future__ import annotations

import contextvars
import functools
import logging
import time
import uuid
from typing import Any, Awaitable, Callable, TypeVar

logger = logging.getLogger("betterstack_mcp.tools")

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("betterstack_request_id", default="-")

_F = TypeVar("_F", bound=Callable[..., Awaitable[Any]])


def current_request_id() -> str:
    """The request-id of the tool call in flight, or '-' outside of one."""
    return request_id_var.get()


def logged_tool(fn: _F) -> _F:
    """Wrap one ``@mcp.tool`` handler with request-id/duration/outcome logging.

    Must sit *below* ``@mcp.tool(...)`` (closest to ``def``) so FastMCP's
    schema introspection -- ``inspect.signature(fn, eval_str=True)`` -- sees
    the wrapped function's real parameters via ``functools.wraps``'
    ``__wrapped__`` chain, not this wrapper's ``(*args, **kwargs)``.
    """

    tool_name = fn.__name__

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        request_id = uuid.uuid4().hex[:12]
        token = request_id_var.set(request_id)
        start = time.monotonic()
        try:
            result = await fn(*args, **kwargs)
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            logger.warning(
                "tool=%s request_id=%s args=%s duration_ms=%.1f outcome=error error=%s",
                tool_name,
                request_id,
                sorted(kwargs.keys()),
                duration_ms,
                type(exc).__name__,
            )
            raise
        else:
            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "tool=%s request_id=%s args=%s duration_ms=%.1f outcome=ok",
                tool_name,
                request_id,
                sorted(kwargs.keys()),
                duration_ms,
            )
            return result
        finally:
            request_id_var.reset(token)

    return wrapper  # type: ignore[return-value]
