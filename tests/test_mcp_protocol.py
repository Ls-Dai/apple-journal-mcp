"""The server as an MCP client sees it: registered tools, annotations, calls."""

from __future__ import annotations

import asyncio
import json

from mcp.shared.memory import create_connected_server_and_client_session

from apple_journal_mcp import server

EXPECTED_TOOLS = {
    "recent_entries",
    "list_entries",
    "show_entry",
    "search_entries",
    "list_journals",
    "journal_stats",
    "doctor",
}


def list_tools():
    return asyncio.run(server.mcp.list_tools())


def call_tool(name: str, arguments: dict):
    async def go():
        async with create_connected_server_and_client_session(server.mcp) as client:
            return await client.call_tool(name, arguments)

    return asyncio.run(go())


def test_exposes_exactly_the_read_tools():
    # A new tool must be added here on purpose, after checking it cannot write.
    assert {t.name for t in list_tools()} == EXPECTED_TOOLS


def test_every_tool_is_annotated_read_only():
    for tool in list_tools():
        assert tool.annotations is not None, tool.name
        assert tool.annotations.readOnlyHint is True, tool.name
        assert tool.annotations.openWorldHint is False, tool.name


def test_every_tool_has_a_description():
    for tool in list_tools():
        assert tool.description and tool.description.strip(), tool.name


def test_list_entries_schema_requires_only_since():
    schema = next(t for t in list_tools() if t.name == "list_entries").inputSchema
    assert schema["required"] == ["since"]
    assert set(schema["properties"]) == {"since", "until", "limit"}


def test_call_tool_round_trip(fake_cli):
    fake_cli.respond(stdout='{"id": 7, "assets": []}')
    result = call_tool("show_entry", {"entry_id": 7})
    assert not result.isError
    assert json.loads(result.content[0].text) == {"id": 7, "assets": []}
    assert fake_cli.calls == [["show", "7", "--json"]]


def test_call_tool_validation_error_is_returned_as_text(fake_cli):
    result = call_tool("search_entries", {"query": "--live"})
    assert "must not start with '--'" in json.loads(result.content[0].text)["error"]
    assert fake_cli.calls == []
