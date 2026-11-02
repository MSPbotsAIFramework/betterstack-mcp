"""Entry point: run the Starlette app (health + MCP) with uvicorn."""

from __future__ import annotations

import logging

import uvicorn

from betterstack_mcp.config import settings
from betterstack_mcp.server import build_app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app = build_app()
    uvicorn.run(app, host=settings.mcp_http_host, port=settings.mcp_http_port)


if __name__ == "__main__":
    main()
