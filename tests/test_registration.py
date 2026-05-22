"""
Regression guard: verify that exactly 42 tools are registered on the mcp instance
after the package split.

If this count changes, a tool was added or accidentally lost during refactoring.
"""

import asyncio
import pytest


def test_tool_count():
    """Exactly 42 tools must be registered after importing the package."""
    import server  # noqa: F401 - triggers tool registration via gsheets_mcp.tools

    from gsheets_mcp.core import mcp

    # list_tools() is a coroutine in FastMCP; run it synchronously.
    tools = asyncio.get_event_loop().run_until_complete(mcp.list_tools())
    tool_names = [t.name for t in tools]

    assert len(tool_names) == 69, (
        f"Expected 69 registered tools, got {len(tool_names)}.\n"
        f"Registered tools: {sorted(tool_names)}"
    )


def test_tool_names_include_expected():
    """Spot-check that key tools from each module are present."""
    import asyncio
    import server  # noqa: F401

    from gsheets_mcp.core import mcp

    tools = asyncio.get_event_loop().run_until_complete(mcp.list_tools())
    tool_names = {t.name for t in tools}

    expected = {
        # read
        'get_sheet_data', 'get_sheet_formulas', 'get_multiple_sheet_data',
        'get_multiple_spreadsheet_summary', 'list_sheets',
        # write
        'update_cells', 'batch_update_cells',
        # structure
        'add_rows', 'add_columns', 'delete_rows_columns', 'auto_resize_dimensions',
        # sheets
        'create_spreadsheet', 'create_sheet', 'list_spreadsheets', 'list_folders',
        'rename_sheet', 'copy_sheet', 'share_spreadsheet',
        # format
        'apply_cell_formatting', 'set_number_format', 'add_cell_borders',
        'apply_text_formatting', 'merge_cells', 'move_range',
        # conditional
        'apply_conditional_formatting', 'update_conditional_formatting',
        'clear_conditional_formatting',
        # validation
        'set_data_validation', 'list_validation_rules', 'clear_data_validation',
        # protection
        'protect_sheet_range', 'set_edit_permissions', 'remove_protection',
        # charts
        'create_chart', 'update_chart', 'move_resize_chart',
        # named_ranges
        'create_named_range', 'list_named_ranges', 'update_named_range',
        # filters
        'create_filter', 'apply_filter_criteria', 'clear_filter',
        # --- expansion wave additions ---
        # write
        'append_data', 'batch_clear_values', 'find_replace',
        # structure
        'insert_rows', 'insert_columns', 'delete_columns', 'freeze_dimensions',
        'set_dimension_size', 'group_dimensions', 'ungroup_dimensions', 'sort_range',
        # sheets
        'duplicate_sheet', 'set_sheet_visibility', 'reorder_sheet',
        'move_spreadsheet_to_folder', 'trash_spreadsheet',
        # read
        'get_spreadsheet_metadata', 'batch_get_values',
        # filters / format
        'create_filter_view', 'delete_filter_view', 'add_banding', 'remove_banding',
        # charts / pivot / metadata
        'delete_chart', 'create_pivot_table', 'delete_pivot_table',
        'create_developer_metadata', 'search_developer_metadata',
    }

    missing = expected - tool_names
    assert not missing, f"Missing tools after refactor: {sorted(missing)}"
