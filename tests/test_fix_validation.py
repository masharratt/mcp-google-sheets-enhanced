"""
Tests for BUG 2: clear_data_validation emits a 'deleteDataValidation' request
type that does not exist in the Sheets API, causing HTTP 400.

Fix: clear validation by sending a 'setDataValidation' request for the range
with the 'rule' key omitted (the documented approach).
"""

import pytest
from unittest.mock import patch

from tests.conftest import assert_batchupdate_body


@pytest.fixture(autouse=True)
def patch_get_sheet_id():
    """Stub _get_sheet_id so the tool never makes a real API call."""
    with patch("gsheets_mcp.tools.validation._get_sheet_id", return_value=0):
        yield


def test_clear_data_validation_does_not_send_delete_data_validation(
    mock_sheets_service, fake_ctx
):
    """
    clear_data_validation must NOT emit 'deleteDataValidation' — that request
    type does not exist in the Sheets API and causes HTTP 400.
    """
    from gsheets_mcp.tools.validation import clear_data_validation

    clear_data_validation(
        spreadsheet_id="test-id",
        sheet_name="Sheet1",
        range="A1:C10",
        ctx=fake_ctx
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    body = kwargs.get("body", {})
    requests = body.get("requests", [])

    bad_requests = [r for r in requests if "deleteDataValidation" in r]
    assert not bad_requests, (
        "'deleteDataValidation' is not a valid Sheets API request type. "
        f"Found: {bad_requests}"
    )


def test_clear_data_validation_sends_set_data_validation_without_rule(
    mock_sheets_service, fake_ctx
):
    """
    clear_data_validation must emit 'setDataValidation' without a 'rule' key
    (the documented way to clear validation in the Sheets API).
    """
    from gsheets_mcp.tools.validation import clear_data_validation

    result = clear_data_validation(
        spreadsheet_id="test-id",
        sheet_name="Sheet1",
        range="B2:D5",
        ctx=fake_ctx
    )

    assert result.get("success") is True, f"Tool reported failure: {result}"

    matched = assert_batchupdate_body(mock_sheets_service, "setDataValidation")
    set_req = matched[0]["setDataValidation"]

    # Must include the range
    assert "range" in set_req, "setDataValidation must include 'range'"

    # Must NOT include 'rule' — omitting rule is how the API clears validation
    assert "rule" not in set_req, (
        "To clear validation, setDataValidation must omit 'rule'. "
        f"Got keys: {list(set_req.keys())}"
    )


def test_clear_data_validation_grid_range_has_correct_sheet_id(
    mock_sheets_service, fake_ctx
):
    """
    The GridRange inside setDataValidation must carry the correct sheetId
    (0, as returned by the stubbed _get_sheet_id).
    """
    from gsheets_mcp.tools.validation import clear_data_validation

    clear_data_validation(
        spreadsheet_id="test-id",
        sheet_name="Sheet1",
        range="A1:A1",
        ctx=fake_ctx
    )

    matched = assert_batchupdate_body(mock_sheets_service, "setDataValidation")
    grid_range = matched[0]["setDataValidation"]["range"]

    assert grid_range.get("sheetId") == 0, (
        f"GridRange sheetId should be 0, got {grid_range.get('sheetId')}"
    )
