"""
Tests for env-driven tool filtering (GSHEETS_ONLY / GSHEETS_DISABLE).

Disabled tools are never registered on the MCP instance, so they cost zero
context tokens. Selection logic is a pure function tested here in isolation;
a subprocess integration test confirms it wires through to mcp.list_tools().
"""

import os
import subprocess
import sys

from gsheets_mcp.core import (
    _parse_filter_tokens,
    _select_tool_names,
    _unknown_filter_tokens,
)


# Small fake category map: tool name -> category.
FAKE = {
    "get_sheet_data": "read",
    "list_sheets": "read",
    "update_cells": "write",
    "create_chart": "charts",
    "update_chart": "charts",
    "create_pivot_table": "pivot",
}
ALL = set(FAKE)


# ---- token parsing ----

def test_parse_splits_strips_lowercases_and_drops_empties():
    assert _parse_filter_tokens(" Read, create_Chart ,, ,WRITE ") == {
        "read", "create_chart", "write",
    }


def test_parse_empty_string_is_empty_set():
    assert _parse_filter_tokens("") == set()
    assert _parse_filter_tokens(None) == set()


# ---- selection ----

def test_no_filter_keeps_all():
    assert _select_tool_names(FAKE, only=set(), disable=set()) == ALL


def test_allowlist_by_category():
    assert _select_tool_names(FAKE, only={"read"}, disable=set()) == {
        "get_sheet_data", "list_sheets",
    }


def test_allowlist_by_tool_name():
    assert _select_tool_names(FAKE, only={"create_chart"}, disable=set()) == {
        "create_chart",
    }


def test_allowlist_mixes_category_and_tool():
    assert _select_tool_names(FAKE, only={"read", "create_pivot_table"}, disable=set()) == {
        "get_sheet_data", "list_sheets", "create_pivot_table",
    }


def test_denylist_by_category():
    assert _select_tool_names(FAKE, only=set(), disable={"charts"}) == {
        "get_sheet_data", "list_sheets", "update_cells", "create_pivot_table",
    }


def test_denylist_by_tool_name():
    assert _select_tool_names(FAKE, only=set(), disable={"update_chart"}) == (
        ALL - {"update_chart"}
    )


def test_allow_then_deny_precedence():
    # allowlist charts, then drop one charts tool by name
    assert _select_tool_names(FAKE, only={"charts"}, disable={"update_chart"}) == {
        "create_chart",
    }


def test_unknown_tokens_detected():
    assert _unknown_filter_tokens(FAKE, {"read", "bogus", "create_chart"}) == {"bogus"}
    assert _unknown_filter_tokens(FAKE, {"charts"}) == set()


# ---- integration: env wires through to real registration ----

def test_env_disable_drops_tools_from_list_tools():
    code = (
        "import asyncio, server;"
        "from gsheets_mcp.core import mcp;"
        "t=asyncio.get_event_loop().run_until_complete(mcp.list_tools());"
        "n={x.name for x in t};"
        "assert 'create_pivot_table' not in n, 'pivot not dropped';"
        "assert 'delete_pivot_table' not in n, 'pivot not dropped';"
        "assert 'get_sheet_data' in n, 'read wrongly dropped';"
        "print(len(n))"
    )
    env = dict(os.environ, GSHEETS_DISABLE="pivot")
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        env=env, capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    assert int(out.stdout.strip()) == 69  # 71 - 2 pivot tools
