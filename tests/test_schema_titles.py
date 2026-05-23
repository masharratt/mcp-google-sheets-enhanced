"""
Regression guard: served tool inputSchemas must contain NO 'title' keys.

FastMCP/pydantic auto-generates redundant 'title' fields for every parameter
("Spreadsheet Id") and a top-level "<tool>Arguments" title. These carry zero
semantic value (the model already sees the property key) and cost ~2,500
tokens of MCP context across the tool set. core.py strips them after
registration; this test ensures the strip stays in place.
"""

import asyncio


def _has_title(obj) -> bool:
    if isinstance(obj, dict):
        if "title" in obj:
            return True
        return any(_has_title(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_title(x) for x in obj)
    return False


def test_no_title_keys_in_any_input_schema():
    import server  # noqa: F401 - triggers tool registration + title strip
    from gsheets_mcp.core import mcp

    tools = asyncio.get_event_loop().run_until_complete(mcp.list_tools())

    offenders = [t.name for t in tools if _has_title(t.inputSchema)]
    assert not offenders, (
        f"{len(offenders)} tool schemas still contain 'title' keys "
        f"(token waste): {sorted(offenders)}"
    )
