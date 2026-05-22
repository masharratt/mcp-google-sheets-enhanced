"""
Tests for BUG 1: update_conditional_formatting sends both 'rule' and 'newIndex'
simultaneously inside updateConditionalFormatRule, which violates the Sheets API
oneof constraint on the 'instruction' field.

Fix: send only 'rule' (with index) for rule-replacement. Never set newIndex
alongside rule.
"""

import pytest
from unittest.mock import patch

from tests.conftest import assert_batchupdate_body


@pytest.fixture(autouse=True)
def patch_get_sheet_id():
    """Stub _get_sheet_id so the tool never makes a real API call."""
    with patch("gsheets_mcp.tools.conditional._get_sheet_id", return_value=0):
        yield


def test_update_conditional_formatting_does_not_send_both_rule_and_new_index(
    mock_sheets_service, fake_ctx
):
    """
    updateConditionalFormatRule must not contain both 'rule' and 'newIndex'.
    Current buggy code sets both, triggering HTTP 400 from the Sheets API.
    """
    from gsheets_mcp.tools.conditional import update_conditional_formatting

    sample_rule = {
        "ranges": [{"sheetId": 0, "startRowIndex": 0, "endRowIndex": 5,
                    "startColumnIndex": 0, "endColumnIndex": 3}],
        "booleanRule": {
            "condition": {"type": "NUMBER_GREATER",
                          "values": [{"userEnteredValue": "100"}]},
            "format": {"backgroundColor": {"red": 1, "green": 0, "blue": 0}}
        }
    }

    result = update_conditional_formatting(
        spreadsheet_id="test-id",
        sheet_name="Sheet1",
        rule_id=2,
        rule=sample_rule,
        ctx=fake_ctx
    )

    # Tool must succeed (no exception swallowed as False)
    assert result.get("success") is True, f"Tool reported failure: {result}"

    # Inspect what was sent to batchUpdate
    matched = assert_batchupdate_body(mock_sheets_service, "updateConditionalFormatRule")
    update_req = matched[0]["updateConditionalFormatRule"]

    # MUST NOT contain both 'rule' and 'newIndex' simultaneously
    has_rule = "rule" in update_req
    has_new_index = "newIndex" in update_req
    assert not (has_rule and has_new_index), (
        "updateConditionalFormatRule must not set both 'rule' and 'newIndex' "
        f"(oneof violation). Got keys: {list(update_req.keys())}"
    )


def test_update_conditional_formatting_sends_index_and_rule(
    mock_sheets_service, fake_ctx
):
    """
    Rule-replacement (the common case) must send 'index' and 'rule',
    without 'newIndex'.
    """
    from gsheets_mcp.tools.conditional import update_conditional_formatting

    sample_rule = {
        "ranges": [{"sheetId": 0, "startRowIndex": 0, "endRowIndex": 2,
                    "startColumnIndex": 0, "endColumnIndex": 1}],
        "booleanRule": {
            "condition": {"type": "BLANK"},
            "format": {}
        }
    }

    update_conditional_formatting(
        spreadsheet_id="test-id",
        sheet_name="Sheet1",
        rule_id=0,
        rule=sample_rule,
        ctx=fake_ctx
    )

    matched = assert_batchupdate_body(mock_sheets_service, "updateConditionalFormatRule")
    update_req = matched[0]["updateConditionalFormatRule"]

    assert "index" in update_req, "Must include 'index' for rule-replacement"
    assert "rule" in update_req, "Must include 'rule' for rule-replacement"
    assert "newIndex" not in update_req, (
        "'newIndex' must not appear in a rule-replacement request"
    )
