"""Logs must never contain the credential header value or a raw upstream
response body (AC16/TC-BS-026).
"""

from __future__ import annotations

import logging

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
