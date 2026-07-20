"""Tests for MCP initialize.instructions capture and tool_describe injection."""
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tools.mcp_tool import (
    MCPServerTask,
    _MCP_SERVER_INSTRUCTIONS_MAX_CHARS,
    _extract_initialize_instructions,
    _truncate_mcp_server_instructions,
    get_mcp_server_instructions,
    get_mcp_server_instructions_for_tool,
    mcp_prefixed_tool_name,
    sanitize_mcp_name_component,
)
from tools.mcp_tool import (
    _mcp_tool_server_names,
    _servers,
    _lock,
)


class TestExtractAndTruncateInstructions:
    def test_extract_empty_when_missing(self):
        assert _extract_initialize_instructions(None) == ""
        assert _extract_initialize_instructions(SimpleNamespace()) == ""

    def test_extract_from_attribute(self):
        init = SimpleNamespace(instructions="  Use label_values first.  ")
        assert _extract_initialize_instructions(init) == "Use label_values first."

    def test_extract_from_dict(self):
        assert _extract_initialize_instructions({"instructions": "hello"}) == "hello"

    def test_truncate_short_text_unchanged(self):
        text = "Short server guidelines."
        assert _truncate_mcp_server_instructions(text) == text

    def test_truncate_long_text_adds_suffix(self):
        text = "x" * (_MCP_SERVER_INSTRUCTIONS_MAX_CHARS + 500)
        out = _truncate_mcp_server_instructions(text)
        assert len(out) <= _MCP_SERVER_INSTRUCTIONS_MAX_CHARS
        assert "truncated" in out.lower()

    def test_truncate_prefers_paragraph_boundary(self):
        head = "A" * 1800
        tail = "B" * 500
        text = head + "\n\n" + tail
        out = _truncate_mcp_server_instructions(text)
        assert out.endswith("…]")
        assert "AAAA" in out


class TestCaptureInitializeResult:
    def test_capture_sets_cached_instructions(self):
        task = MCPServerTask("prometheus")
        init = SimpleNamespace(
            instructions="Never assume a metric exists.",
            capabilities=SimpleNamespace(tools=SimpleNamespace()),
        )
        task._capture_initialize_result(init)
        assert task.initialize_result is init
        assert task.server_instructions == "Never assume a metric exists."

    def test_capture_empty_instructions_is_none(self):
        task = MCPServerTask("empty")
        task._capture_initialize_result(SimpleNamespace())
        assert task.server_instructions is None


class TestGetMcpServerInstructions:
    def setup_method(self):
        self._saved_servers = dict(_servers)
        self._saved_map = dict(_mcp_tool_server_names)

    def teardown_method(self):
        with _lock:
            _servers.clear()
            _servers.update(self._saved_servers)
            _mcp_tool_server_names.clear()
            _mcp_tool_server_names.update(self._saved_map)

    def test_get_for_tool_via_provenance_map(self):
        server = MCPServerTask("prometheus")
        server.server_instructions = "Discover before you query."
        tool_name = mcp_prefixed_tool_name("prometheus", "query")
        with _lock:
            _servers["prometheus"] = server
            _mcp_tool_server_names[tool_name] = sanitize_mcp_name_component("prometheus")
        assert get_mcp_server_instructions_for_tool(tool_name) == "Discover before you query."
        assert get_mcp_server_instructions("prometheus") == "Discover before you query."

    def test_get_for_unknown_tool_returns_none(self):
        assert get_mcp_server_instructions_for_tool("mcp__missing__query") is None


class TestToolDescribeInjection:
    def test_tool_describe_includes_server_instructions_for_mcp(self):
        from tools.tool_search import dispatch_tool_describe

        tool_name = "mcp__prometheus__query"
        tool_defs = [{
            "type": "function",
            "function": {
                "name": tool_name,
                "description": "Run PromQL",
                "parameters": {"type": "object", "properties": {}},
            },
        }]
        with patch(
            "tools.mcp_tool.get_mcp_server_instructions_for_tool",
            return_value="Use discovery tools first.",
        ):
            payload = json.loads(
                dispatch_tool_describe({"name": tool_name}, current_tool_defs=tool_defs)
            )
        assert payload["server_instructions"] == "Use discovery tools first."
        assert "server_instructions_note" in payload

    def test_tool_describe_omits_field_when_no_instructions(self):
        from tools.tool_search import dispatch_tool_describe

        tool_name = "mcp__prometheus__query"
        tool_defs = [{
            "type": "function",
            "function": {
                "name": tool_name,
                "description": "Run PromQL",
                "parameters": {"type": "object", "properties": {}},
            },
        }]
        with patch(
            "tools.mcp_tool.get_mcp_server_instructions_for_tool",
            return_value=None,
        ):
            payload = json.loads(
                dispatch_tool_describe({"name": tool_name}, current_tool_defs=tool_defs)
            )
        assert "server_instructions" not in payload
