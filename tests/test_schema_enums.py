"""
Regression guard: closed-set parameters must expose JSON-Schema 'enum' lists
(generated from Literal type hints), not bare string types.

Moving allowed-value constraints into the schema gives MCP clients
machine-readable validation and a single source of truth, replacing prose
value-lists in the tool description.

Ground-truth value sets come from the mapping dicts in the tool source:
  charts.chart_type        -> COLUMN BAR LINE PIE SCATTER AREA
  format.set_number_format -> TEXT NUMBER CURRENCY PERCENT DATE TIME DATE_TIME SCIENTIFIC
  format.merge_cells       -> MERGE_ALL MERGE_COLUMNS MERGE_ROWS UNMERGE
"""

import asyncio

import pytest


def _schema(tools, name):
    return next(t.inputSchema for t in tools if t.name == name)


@pytest.fixture(scope="module")
def tools():
    import server  # noqa: F401 - triggers registration
    from gsheets_mcp.core import mcp
    return asyncio.get_event_loop().run_until_complete(mcp.list_tools())


@pytest.mark.parametrize(
    "tool_name,param,expected",
    [
        ("create_chart", "chart_type",
         {"COLUMN", "BAR", "LINE", "PIE", "SCATTER", "AREA"}),
        ("set_number_format", "number_format",
         {"TEXT", "NUMBER", "CURRENCY", "PERCENT", "DATE", "TIME",
          "DATE_TIME", "SCIENTIFIC"}),
        ("merge_cells", "merge_type",
         {"MERGE_ALL", "MERGE_COLUMNS", "MERGE_ROWS", "UNMERGE"}),
    ],
)
def test_closed_set_param_exposes_enum(tools, tool_name, param, expected):
    props = _schema(tools, tool_name)["properties"]
    assert param in props, f"{tool_name} missing param {param}"
    enum = props[param].get("enum")
    assert enum is not None, f"{tool_name}.{param} has no 'enum' in schema"
    assert set(enum) == expected, (
        f"{tool_name}.{param} enum mismatch: got {sorted(enum)}, "
        f"expected {sorted(expected)}"
    )
