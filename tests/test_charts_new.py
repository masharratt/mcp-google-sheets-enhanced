"""
Tests for delete_chart tool added to gsheets_mcp/tools/charts.py.
"""

import pytest
from gsheets_mcp.tools.charts import delete_chart


def test_delete_chart_success(fake_ctx, mock_sheets_service, assert_batchupdate_body=None):
    """delete_chart builds a deleteEmbeddedObject request with the chart id."""
    result = delete_chart(
        spreadsheet_id="spreadsheet-abc",
        chart_id=42,
        ctx=fake_ctx,
    )

    assert result["success"] is True
    assert result["chart_id"] == 42


def test_delete_chart_request_body(fake_ctx, mock_sheets_service):
    """The batchUpdate body must contain a deleteEmbeddedObject request."""
    delete_chart(
        spreadsheet_id="spreadsheet-abc",
        chart_id=99,
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    body = kwargs.get("body", {})
    requests = body.get("requests", [])

    matched = [r for r in requests if "deleteEmbeddedObject" in r]
    assert matched, f"Expected deleteEmbeddedObject in requests, got: {requests}"

    obj_id = matched[0]["deleteEmbeddedObject"]["objectId"]
    assert obj_id == 99, f"Expected objectId=99, got {obj_id}"


def test_delete_chart_correct_spreadsheet_id(fake_ctx, mock_sheets_service):
    """batchUpdate is called with the correct spreadsheetId."""
    delete_chart(
        spreadsheet_id="my-sheet-id",
        chart_id=7,
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    assert kwargs.get("spreadsheetId") == "my-sheet-id"


def test_delete_chart_error_handling(fake_ctx, mock_sheets_service):
    """delete_chart returns success=False on exception."""
    # Force execute() to raise
    mock_sheets_service.set_execute_return(None)

    # Patch execute to raise
    original_execute = mock_sheets_service.execute
    mock_sheets_service.execute = lambda: (_ for _ in ()).throw(Exception("API error"))

    result = delete_chart(
        spreadsheet_id="spreadsheet-abc",
        chart_id=5,
        ctx=fake_ctx,
    )

    assert result["success"] is False
    assert "error" in result["message"].lower() or "API error" in result["message"]

    # Restore
    mock_sheets_service.execute = original_execute
