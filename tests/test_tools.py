"""tools/list snapshot: exactly the 11 tools the design specifies, each with
the expected required parameters (vendor-mcp-development SOP section 10 /
section 13 -- this snapshot is the thing that goes red when a tool's public
contract changes).
"""

from __future__ import annotations

EXPECTED_TOOLS: dict[str, set[str]] = {
    "betterstack_list_monitors": set(),
    "betterstack_get_monitor": {"id"},
    "betterstack_create_monitor": {"url", "monitor_type", "pronounceable_name"},
    "betterstack_update_monitor": {"id"},
    "betterstack_delete_monitor": {"id"},
    "betterstack_list_incidents": set(),
    "betterstack_get_incident": {"id"},
    "betterstack_acknowledge_incident": {"id"},
    "betterstack_resolve_incident": {"id"},
    "betterstack_list_oncall_schedules": set(),
    "betterstack_list_oncall_events": set(),
}


async def test_tools_list_snapshot(mcp):
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert names == set(EXPECTED_TOOLS), f"tool set changed: {names - set(EXPECTED_TOOLS)} added, {set(EXPECTED_TOOLS) - names} removed"

    by_name = {t.name: t for t in tools}
    for name, expected_required in EXPECTED_TOOLS.items():
        required = set(by_name[name].inputSchema.get("required", []))
        assert required == expected_required, f"{name}: required params changed to {required}"


async def test_tool_descriptions_are_concise(mcp):
    """SOP section 2.2: description <= 500 chars, first line <= 100 chars."""
    tools = await mcp.list_tools()
    for tool in tools:
        description = tool.description or ""
        assert len(description) <= 500, f"{tool.name} description too long: {len(description)} chars"
        first_line = description.splitlines()[0] if description else ""
        assert len(first_line) <= 100, f"{tool.name} first line too long: {len(first_line)} chars"


async def test_tool_names_use_vendor_prefix(mcp):
    tools = await mcp.list_tools()
    assert all(t.name.startswith("betterstack_") for t in tools)


async def test_write_and_delete_tools_are_annotated(mcp):
    tools = {t.name: t for t in await mcp.list_tools()}
    assert tools["betterstack_delete_monitor"].annotations.destructiveHint is True
    assert tools["betterstack_acknowledge_incident"].annotations.idempotentHint is True
    assert tools["betterstack_resolve_incident"].annotations.idempotentHint is True
    for read_only in ("betterstack_list_monitors", "betterstack_get_monitor", "betterstack_list_incidents"):
        assert tools[read_only].annotations.readOnlyHint is True
