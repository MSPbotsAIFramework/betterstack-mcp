"""Logs must never contain the credential header value or a raw upstream
response body (AC16/TC-BS-026), and every tool call must produce a
structured, correlatable log trail: a request-id shared by the tool-level
and the upstream-call-level log lines, the tool name, and the call duration
(vendor-mcp-development SOP section 6 / section 14 checklist -- added as a
code-review must-fix, see docs/tickets/PRD-21258-review.md Round 1 finding 1).
"""

from __future__ import annotations

import logging
import re

import httpx

from tests.conftest import TEST_BASE_URL, TEST_TOKEN, call_tool


async def test_logs_never_contain_the_credential_header_value(mcp, credentials, betterstack_api, caplog):
    secret_body_fragment = "super-secret-internal-stack-trace-do-not-log"
    betterstack_api.get(f"{TEST_BASE_URL}/monitors/1").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}, json={"message": secret_body_fragment}),
            httpx.Response(200, json={"data": {"id": "1", "type": "monitor", "attributes": {}}}),
        ]
    )

    with caplog.at_level(logging.DEBUG):
        await call_tool(mcp, "betterstack_get_monitor", {"id": "1"})

    full_log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert TEST_TOKEN not in full_log_text
    assert f"Bearer {TEST_TOKEN}" not in full_log_text
    assert secret_body_fragment not in full_log_text


async def test_logs_request_id_tool_name_and_duration_on_success(mcp, credentials, betterstack_api, caplog):
    """Success path: tools.py logs tool=<name> ... outcome=ok, api_client.py
    logs the same request_id with status=200 ... outcome=ok, and the two log
    lines correlate via one shared request_id (not just two separate ids).
    """
    betterstack_api.get(f"{TEST_BASE_URL}/monitors/1").mock(
        return_value=httpx.Response(200, json={"data": {"id": "1", "type": "monitor", "attributes": {}}})
    )

    with caplog.at_level(logging.INFO):
        await call_tool(mcp, "betterstack_get_monitor", {"id": "1"})

    tool_records = [r for r in caplog.records if r.name == "betterstack_mcp.tools"]
    client_records = [r for r in caplog.records if r.name == "betterstack_mcp.api_client"]
    assert len(tool_records) == 1, f"expected exactly one tool-level log line, got {tool_records!r}"
    assert len(client_records) == 1, f"expected exactly one api-client log line, got {client_records!r}"

    tool_line = tool_records[0].getMessage()
    client_line = client_records[0].getMessage()
    assert "tool=betterstack_get_monitor" in tool_line
    assert "outcome=ok" in tool_line
    assert re.search(r"duration_ms=\d+\.\d", tool_line)

    assert "status=200" in client_line
    assert "outcome=ok" in client_line
    assert re.search(r"duration_ms=\d+\.\d", client_line)

    tool_request_id = re.search(r"request_id=(\S+)", tool_line).group(1)
    client_request_id = re.search(r"request_id=(\S+)", client_line).group(1)
    assert tool_request_id == client_request_id
    assert tool_request_id != "-"


async def test_logs_request_id_and_status_on_upstream_error(mcp, credentials, betterstack_api, caplog):
    """Failure path: a non-retryable 404 is logged with its status code and
    error outcome at the api_client level, even though the tool itself
    returns an error envelope instead of raising (so it still logs outcome=ok
    for "the tool call executed without an internal exception").
    """
    betterstack_api.get(f"{TEST_BASE_URL}/monitors/missing").mock(return_value=httpx.Response(404))

    with caplog.at_level(logging.INFO):
        await call_tool(mcp, "betterstack_get_monitor", {"id": "missing"})

    client_records = [r for r in caplog.records if r.name == "betterstack_mcp.api_client"]
    assert len(client_records) == 1
    client_line = client_records[0].getMessage()
    assert "status=404" in client_line
    assert "outcome=error" in client_line
    assert re.search(r"request_id=\S+", client_line)
