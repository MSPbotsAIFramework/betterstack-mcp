"""FastMCP factory and the per-request credential middleware.

Three hard rules drive everything here (vendor-mcp-development SOP section 3
and section 1.3): credentials only ever come from an HTTP header, every
request is isolated via contextvars.ContextVar (set on entry, reset in
``finally``), and the service holds no state between requests.
"""

from __future__ import annotations

import contextvars
import logging
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from betterstack_mcp.api_client import BetterStackClient
from betterstack_mcp.config import settings
from betterstack_mcp.tools import incidents, monitors, oncall

logger = logging.getLogger("betterstack_mcp.server")

TOKEN_HEADER = "x-betterstack-api-token"
BASE_URL_HEADER = "x-betterstack-base-url"

INSTRUCTIONS = (
    "BetterStack connector for uptime monitoring, incident response, and on-call "
    "visibility. Core concepts: a monitor watches a URL/host and has a status "
    "(up/down/paused); an incident is created when a monitor goes down and moves "
    "through started -> acknowledged -> resolved; an on-call schedule has events "
    "describing who is on call for a time window. Typical flows: list_monitors to "
    "see what is being watched, list_incidents(resolved=false) to see what is "
    "currently on fire, acknowledge_incident then resolve_incident to triage one, "
    "list_oncall_events to find who should be paged right now."
)


@dataclass(frozen=True)
class RequestCredentials:
    token: str
    base_url: str


_credentials: contextvars.ContextVar[RequestCredentials] = contextvars.ContextVar("betterstack_credentials")


def get_client() -> BetterStackClient:
    """Build a fresh API client for the credentials of the current request.

    Raises LookupError if called outside a request that passed the
    credential middleware -- that should never happen in production since
    the middleware runs before any tool code, but it keeps this function
    honest for tests that forget to set the context.
    """
    creds = _credentials.get()
    return BetterStackClient(creds.token, creds.base_url)


class CredentialMiddleware:
    """ASGI middleware: extract the per-tenant credential header, isolate it
    in a ContextVar for the lifetime of this one request, and reset it when
    the request finishes (success or failure) so nothing leaks to the next
    concurrent request sharing this process.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        token = headers.get(TOKEN_HEADER)
        if not token:
            response = JSONResponse(
                {
                    "error": "Missing required header: X-Betterstack-Api-Token",
                    "required_headers": ["X-Betterstack-Api-Token"],
                },
                status_code=401,
            )
            await response(scope, receive, send)
            return

        base_url = headers.get(BASE_URL_HEADER) or settings.base_url
        token_reset = _credentials.set(RequestCredentials(token=token, base_url=base_url))
        try:
            await self.app(scope, receive, send)
        finally:
            _credentials.reset(token_reset)


async def health(_: Request) -> Response:
    """Purely local liveness probe -- never calls BetterStack (SOP section 1.1)."""
    return JSONResponse({"status": "ok"})


def build_mcp() -> FastMCP:
    mcp = FastMCP(
        name="betterstack-mcp",
        instructions=INSTRUCTIONS,
        stateless_http=True,
    )
    monitors.register(mcp, get_client)
    incidents.register(mcp, get_client)
    oncall.register(mcp, get_client)
    return mcp


def build_app() -> Starlette:
    mcp = build_mcp()

    # DNS-rebinding protection must be off *before* the session manager is
    # built: the service sits behind an internal reverse proxy / gateway, not
    # localhost, and the MCP SDK's default protection rejects non-localhost
    # Host headers with 421 (SOP section 7).
    mcp.settings.transport_security.enable_dns_rebinding_protection = False

    mcp_asgi_app = mcp.streamable_http_app()

    app = Starlette(
        routes=[
            # /health first: it must be matched before the catch-all mount below.
            Route("/health", health, methods=["GET"]),
            # Mounted at "/" (not "/mcp") because mcp_asgi_app already serves its
            # own "/mcp" route internally (FastMCP.settings.streamable_http_path);
            # mounting it under "/mcp" here would require "/mcp/mcp".
            Mount("/", app=mcp_asgi_app),
        ],
        # The MCP session manager's run() must be the OUTER app's lifespan --
        # Mount() does not start a sub-app's lifespan on its own, and without
        # this /mcp fails with "Task group is not initialized" while /health
        # still returns 200 (SOP section 7).
        lifespan=lambda _app: mcp.session_manager.run(),
    )
    app.add_middleware(CredentialMiddleware)
    return app


__all__ = ["build_app", "build_mcp", "get_client", "RequestCredentials", "_credentials"]
