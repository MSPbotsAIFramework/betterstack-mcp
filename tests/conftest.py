"""Shared fixtures: a fresh FastMCP instance, a request-credentials context,
and a respx router mocking BetterStack's API -- no real network, no real
token (vendor-mcp-development SOP section 10: unit tests mock the API).
"""

from __future__ import annotations

from typing import Any

import pytest
import respx

from betterstack_mcp.server import RequestCredentials, _credentials, build_mcp

TEST_TOKEN = "test-token-123"
TEST_BASE_URL = "https://uptime.betterstack.com/api/v2"


@pytest.fixture
def mcp():
    return build_mcp()


@pytest.fixture
def credentials():
    reset_token = _credentials.set(RequestCredentials(token=TEST_TOKEN, base_url=TEST_BASE_URL))
    yield
    _credentials.reset(reset_token)


@pytest.fixture
def betterstack_api():
    with respx.mock(assert_all_called=False) as router:
        yield router


@pytest.fixture(autouse=True)
def _fast_retry_backoff(monkeypatch):
    """Skip real sleeps during retry/backoff so the 429/5xx tests run fast."""
    import betterstack_mcp.api_client as api_client_module

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(api_client_module, "_sleep", _no_sleep)


async def call_tool(mcp, name: str, arguments: dict[str, Any] | None = None) -> str:
    """Call a registered tool and return its single text-content payload."""
    content, _structured = await mcp.call_tool(name, arguments or {})
    assert len(content) == 1, f"expected exactly one content block, got {content!r}"
    return content[0].text
