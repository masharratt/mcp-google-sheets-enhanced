"""
Tests for create_pivot_table and delete_pivot_table in gsheets_mcp/tools/pivot.py.
"""

import pytest
from gsheets_mcp.tools.pivot import create_pivot_table, delete_pivot_table


# ---------------------------------------------------------------------------
# create_pivot_table
# ---------------------------------------------------------------------------

def test_create_pivot_table_success(fake_ctx, mock_sheets_service):
    """create_pivot_table returns success=True."""
    result = create_pivot_table(
        spreadsheet_id="ss-1",
        source_sheet="Sheet1",
        source_range="A1:C100",
        anchor_sheet="Sheet1",
        anchor_row=0,
        anchor_col=0,
        rows=[{"source_column_offset": 0, "show_totals": True, "sort_order": "ASCENDING"}],
        values=[{"source_column_offset": 2, "summarize_function": "SUM"}],
        ctx=fake_ctx,
    )
    assert result["success"] is True


def test_create_pivot_table_uses_update_cells(fake_ctx, mock_sheets_service):
    """batchUpdate body must use an updateCells request."""
    create_pivot_table(
        spreadsheet_id="ss-1",
        source_sheet="Sheet1",
        source_range="A1:C100",
        anchor_sheet="Sheet1",
        anchor_row=0,
        anchor_col=0,
        rows=[{"source_column_offset": 0, "show_totals": True, "sort_order": "ASCENDING"}],
        values=[{"source_column_offset": 2, "summarize_function": "SUM"}],
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    body = kwargs.get("body", {})
    requests = body.get("requests", [])
    matched = [r for r in requests if "updateCells" in r]
    assert matched, f"Expected updateCells in requests, got: {requests}"


def test_create_pivot_table_pivot_in_rows(fake_ctx, mock_sheets_service):
    """The updateCells request must contain a pivotTable with rows."""
    create_pivot_table(
        spreadsheet_id="ss-1",
        source_sheet="Sheet1",
        source_range="A1:C100",
        anchor_sheet="Sheet1",
        anchor_row=2,
        anchor_col=3,
        rows=[{"source_column_offset": 1, "show_totals": False, "sort_order": "DESCENDING"}],
        values=[{"source_column_offset": 2, "summarize_function": "COUNT"}],
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    body = kwargs.get("body", {})
    requests = body.get("requests", [])
    matched = [r for r in requests if "updateCells" in r]
    assert matched

    uc = matched[0]["updateCells"]
    # fields must include pivotTable
    assert "pivotTable" in uc.get("fields", ""), f"fields should mention pivotTable, got: {uc.get('fields')}"

    # rows spec should reflect input
    rows_entry = uc["rows"][0]["values"][0]["pivotTable"]["rows"][0]
    assert rows_entry["sourceColumnOffset"] == 1
    assert rows_entry["showTotals"] is False
    assert rows_entry["sortOrder"] == "DESCENDING"


def test_create_pivot_table_values_spec(fake_ctx, mock_sheets_service):
    """pivotTable values must map source_column_offset and summarize_function."""
    create_pivot_table(
        spreadsheet_id="ss-1",
        source_sheet="Sheet1",
        source_range="B2:D50",
        anchor_sheet="Sheet1",
        anchor_row=0,
        anchor_col=5,
        rows=[{"source_column_offset": 0, "show_totals": True, "sort_order": "ASCENDING"}],
        values=[{"source_column_offset": 2, "summarize_function": "AVERAGE"}],
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    body = kwargs.get("body", {})
    requests = body.get("requests", [])
    matched = [r for r in requests if "updateCells" in r]
    uc = matched[0]["updateCells"]
    val_entry = uc["rows"][0]["values"][0]["pivotTable"]["values"][0]
    assert val_entry["sourceColumnOffset"] == 2
    assert val_entry["summarizeFunction"] == "AVERAGE"


def test_create_pivot_table_source_grid_range(fake_ctx, mock_sheets_service):
    """The pivotTable source must be a GridRange with the source sheetId."""
    create_pivot_table(
        spreadsheet_id="ss-1",
        source_sheet="Sheet1",
        source_range="A1:C100",
        anchor_sheet="Sheet1",
        anchor_row=0,
        anchor_col=0,
        rows=[{"source_column_offset": 0, "show_totals": True, "sort_order": "ASCENDING"}],
        values=[{"source_column_offset": 1, "summarize_function": "SUM"}],
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    body = kwargs.get("body", {})
    requests = body.get("requests", [])
    matched = [r for r in requests if "updateCells" in r]
    uc = matched[0]["updateCells"]
    source = uc["rows"][0]["values"][0]["pivotTable"]["source"]
    # sheetId must be the numeric id resolved from mock (Sheet1 -> 0)
    assert "sheetId" in source
    assert "startRowIndex" in source
    assert "endRowIndex" in source


def test_create_pivot_table_with_columns(fake_ctx, mock_sheets_service):
    """Optional columns parameter is included in the pivotTable spec when provided."""
    result = create_pivot_table(
        spreadsheet_id="ss-1",
        source_sheet="Sheet1",
        source_range="A1:D200",
        anchor_sheet="Sheet1",
        anchor_row=0,
        anchor_col=0,
        rows=[{"source_column_offset": 0, "show_totals": True, "sort_order": "ASCENDING"}],
        columns=[{"source_column_offset": 1, "show_totals": True, "sort_order": "ASCENDING"}],
        values=[{"source_column_offset": 3, "summarize_function": "SUM"}],
        ctx=fake_ctx,
    )
    assert result["success"] is True

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    body = kwargs.get("body", {})
    requests = body.get("requests", [])
    matched = [r for r in requests if "updateCells" in r]
    uc = matched[0]["updateCells"]
    pivot = uc["rows"][0]["values"][0]["pivotTable"]
    assert "columns" in pivot
    assert pivot["columns"][0]["sourceColumnOffset"] == 1


def test_create_pivot_table_anchor_cell(fake_ctx, mock_sheets_service):
    """The anchor cell in updateCells must match anchor_row and anchor_col."""
    create_pivot_table(
        spreadsheet_id="ss-1",
        source_sheet="Sheet1",
        source_range="A1:B10",
        anchor_sheet="Sheet1",
        anchor_row=5,
        anchor_col=3,
        rows=[{"source_column_offset": 0, "show_totals": True, "sort_order": "ASCENDING"}],
        values=[{"source_column_offset": 1, "summarize_function": "SUM"}],
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    body = kwargs.get("body", {})
    requests = body.get("requests", [])
    matched = [r for r in requests if "updateCells" in r]
    uc = matched[0]["updateCells"]
    start = uc["start"]
    assert start["rowIndex"] == 5
    assert start["columnIndex"] == 3


# ---------------------------------------------------------------------------
# delete_pivot_table
# ---------------------------------------------------------------------------

def test_delete_pivot_table_success(fake_ctx, mock_sheets_service):
    """delete_pivot_table returns success=True."""
    result = delete_pivot_table(
        spreadsheet_id="ss-1",
        anchor_sheet="Sheet1",
        anchor_row=0,
        anchor_col=0,
        ctx=fake_ctx,
    )
    assert result["success"] is True


def test_delete_pivot_table_uses_update_cells(fake_ctx, mock_sheets_service):
    """delete_pivot_table sends updateCells with an empty cell to remove the pivot."""
    delete_pivot_table(
        spreadsheet_id="ss-1",
        anchor_sheet="Sheet1",
        anchor_row=2,
        anchor_col=1,
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    body = kwargs.get("body", {})
    requests = body.get("requests", [])
    matched = [r for r in requests if "updateCells" in r]
    assert matched, f"Expected updateCells in delete request, got: {requests}"


def test_delete_pivot_table_fields_pivot_table(fake_ctx, mock_sheets_service):
    """delete_pivot_table must set fields='pivotTable' to clear only the pivot."""
    delete_pivot_table(
        spreadsheet_id="ss-1",
        anchor_sheet="Sheet1",
        anchor_row=0,
        anchor_col=0,
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    body = kwargs.get("body", {})
    requests = body.get("requests", [])
    matched = [r for r in requests if "updateCells" in r]
    uc = matched[0]["updateCells"]
    assert uc.get("fields") == "pivotTable", f"fields should be 'pivotTable', got {uc.get('fields')}"


def test_delete_pivot_table_empty_cell(fake_ctx, mock_sheets_service):
    """The rows in updateCells must have an empty cell (no pivotTable key)."""
    delete_pivot_table(
        spreadsheet_id="ss-1",
        anchor_sheet="Sheet1",
        anchor_row=3,
        anchor_col=2,
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    body = kwargs.get("body", {})
    requests = body.get("requests", [])
    matched = [r for r in requests if "updateCells" in r]
    uc = matched[0]["updateCells"]
    cell_value = uc["rows"][0]["values"][0]
    # Empty cell: should NOT have pivotTable key set to anything meaningful
    assert "pivotTable" not in cell_value, f"Expected empty cell, got: {cell_value}"


def test_delete_pivot_table_anchor_position(fake_ctx, mock_sheets_service):
    """The start cell in delete updateCells must match anchor_row and anchor_col."""
    delete_pivot_table(
        spreadsheet_id="ss-1",
        anchor_sheet="Sheet1",
        anchor_row=7,
        anchor_col=4,
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    body = kwargs.get("body", {})
    requests = body.get("requests", [])
    matched = [r for r in requests if "updateCells" in r]
    uc = matched[0]["updateCells"]
    start = uc["start"]
    assert start["rowIndex"] == 7
    assert start["columnIndex"] == 4
