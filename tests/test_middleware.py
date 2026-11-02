"""Credential middleware tests: missing-header 401 (AC12/TC-BS-021) and
request-level isolation under concurrency (AC15/TC-BS-025).
"""

from __future__ import annotations

import asyncio

import httpx
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from betterstack_mcp.server import CredentialMiddleware, _credentials


async def _echo_token(request):
    # Yield control twice so concurrent requests actually interleave instead
    # of running start-to-finish before the next one begins.
    await asyncio.sleep(0)
    creds = _credentials.get()
    await asyncio.sleep(0)
    return JSONResponse({"token": creds.token, "base_url": creds.base_url})


def _build_echo_app() -> Starlette:
    app = Starlette(routes=[Route("/mcp", _echo_token, methods=["POST"])])
    app.add_middleware(CredentialMiddleware)
    return app


async def test_missing_credential_header_returns_401_with_header_name():
    transport = httpx.ASGITransport(app=_build_echo_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/mcp", json={})

    assert response.status_code == 401
    body = response.json()
    assert body["required_headers"] == ["X-Betterstack-Api-Token"]
    assert "X-Betterstack-Api-Token" in body["error"]


async def test_header_present_reaches_the_app_with_the_right_token():
    transport = httpx.ASGITransport(app=_build_echo_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/mcp", headers={"X-Betterstack-Api-Token": "tok-abc"}, json={})

    assert response.status_code == 200
    assert response.json()["token"] == "tok-abc"


async def test_concurrent_requests_do_not_leak_credentials_across_tenants():
    transport = httpx.ASGITransport(app=_build_echo_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

        async def _call(token: str) -> str:
            response = await client.post("/mcp", headers={"X-Betterstack-Api-Token": token}, json={})
            return response.json()["token"]

        results = await asyncio.gather(*[_call(f"tenant-{i}") for i in range(20)])

    assert results == [f"tenant-{i}" for i in range(20)]


async def test_base_url_override_header_is_honored():
    transport = httpx.ASGITransport(app=_build_echo_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/mcp",
            headers={
                "X-Betterstack-Api-Token": "tok",
                "X-Betterstack-Base-Url": "https://incidents.betterstack.com/api/v2",
            },
            json={},
        )

    assert response.json()["base_url"] == "https://incidents.betterstack.com/api/v2"
