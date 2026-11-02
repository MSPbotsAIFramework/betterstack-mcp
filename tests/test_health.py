"""/health must be a purely local probe, independent of the BetterStack API (AC17/TC-BS-027)."""

from __future__ import annotations

import httpx

from betterstack_mcp.server import build_app


async def test_health_is_local_and_independent_of_upstream():
    # No respx mock installed at all: if /health tried to reach BetterStack,
    # httpx would raise a connection error here instead of this test passing.
    transport = httpx.ASGITransport(app=build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_health_does_not_require_a_credential_header():
    transport = httpx.ASGITransport(app=build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
