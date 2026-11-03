"""Upstream status -> structured error code mapping (AC13-AC14, TC-BS-022..024)."""

from __future__ import annotations

import json

import httpx

from tests.conftest import TEST_BASE_URL, call_tool


async def test_upstream_401_maps_to_unauthorized(mcp, credentials, betterstack_api):
    betterstack_api.get(f"{TEST_BASE_URL}/monitors/1").mock(return_value=httpx.Response(401, json={}))

    result = json.loads(await call_tool(mcp, "betterstack_get_monitor", {"id": "1"}))

    assert result == {"error": {"code": "unauthorized", "message": result["error"]["message"], "retryable": False}}
    assert "token" not in result["error"]["message"].lower()


async def test_upstream_429_retries_then_rate_limited(mcp, credentials, betterstack_api):
    route = betterstack_api.get(f"{TEST_BASE_URL}/monitors/1").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"}, json={})
    )

    result = json.loads(await call_tool(mcp, "betterstack_get_monitor", {"id": "1"}))

    assert result["error"]["code"] == "rate_limited"
    assert result["error"]["retryable"] is True
    # MAX_RETRIES=3 -> up to 4 attempts total before giving up
    assert route.call_count == 4


async def test_upstream_5xx_and_timeout_map_to_upstream_error(mcp, credentials, betterstack_api):
    betterstack_api.get(f"{TEST_BASE_URL}/monitors/1").mock(return_value=httpx.Response(500, text="internal trace, do not leak"))

    result = json.loads(await call_tool(mcp, "betterstack_get_monitor", {"id": "1"}))

    assert result["error"]["code"] == "upstream_error"
    assert result["error"]["retryable"] is True
    assert "internal trace" not in result["error"]["message"]

    betterstack_api.get(f"{TEST_BASE_URL}/monitors/2").mock(side_effect=httpx.ReadTimeout("timed out"))

    timeout_result = json.loads(await call_tool(mcp, "betterstack_get_monitor", {"id": "2"}))

    assert timeout_result["error"]["code"] == "upstream_error"
    assert timeout_result["error"]["retryable"] is True
