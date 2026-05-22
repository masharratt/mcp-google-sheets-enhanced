"""
Regression tests for BUG 3 — apply_filter_criteria and create_filter.

BUG 3a: apply_filter_criteria always emitted updateFilterView, which fails (HTTP 400)
         when targeting the basic filter (id 0). Fix: when filter_view_id is absent,
         use setBasicFilter instead.
BUG 3b: create_filter returned no usable handle. Fix: return sheetId + range so
         callers can target the filter.
"""

import pytest

from tests.conftest import assert_batchupdate_body

SPREADSHEET_ID = "fake-spreadsheet-id"
SHEET_NAME = "Sheet1"

SAMPLE_CRITERIA = {
    "0": {
        "condition": {
            "type": "NUMBER_GREATER",
            "values": [{"userEnteredValue": "100"}],
        }
    }
}


# ---------------------------------------------------------------------------
# BUG 3a: apply_filter_criteria — basic filter path vs filter-view path
# ---------------------------------------------------------------------------


class TestApplyFilterCriteria:
    def test_no_filter_view_id_uses_setBasicFilter(self, mock_sheets_service, fake_ctx):
        """
        Before fix: always sends updateFilterView (fails on basic filter).
        After fix:  when filter_view_id is absent, sends setBasicFilter.
        """
        from gsheets_mcp.tools.filters import apply_filter_criteria

        result = apply_filter_criteria(
            spreadsheet_id=SPREADSHEET_ID,
            sheet_name=SHEET_NAME,
            criteria=SAMPLE_CRITERIA,
            ctx=fake_ctx,
        )

        assert result.get("success") is True, f"Tool returned failure: {result}"

        # Must NOT emit updateFilterView when no filter_view_id given
        kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
        body = kwargs.get("body", {})
        requests = body.get("requests", [])
        bad = [r for r in requests if "updateFilterView" in r]
        assert not bad, (
            "apply_filter_criteria sent updateFilterView even without filter_view_id. "
            "Should use setBasicFilter for the basic filter."
        )

        # Must emit setBasicFilter
        matched = assert_batchupdate_body(mock_sheets_service, "setBasicFilter")
        bf = matched[0]["setBasicFilter"]["filter"]
        assert "criteria" in bf, f"setBasicFilter.filter must include criteria. Got: {bf}"

    def test_setBasicFilter_includes_range(self, mock_sheets_service, fake_ctx):
        """
        setBasicFilter.filter must include a range (sheetId at minimum).
        """
        from gsheets_mcp.tools.filters import apply_filter_criteria

        apply_filter_criteria(
            spreadsheet_id=SPREADSHEET_ID,
            sheet_name=SHEET_NAME,
            criteria=SAMPLE_CRITERIA,
            ctx=fake_ctx,
        )

        kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
        bf = kwargs["body"]["requests"][0]["setBasicFilter"]["filter"]
        assert "range" in bf, f"setBasicFilter.filter missing 'range'. Got: {bf}"
        assert "sheetId" in bf["range"], f"range missing sheetId. Got: {bf['range']}"

    def test_with_filter_view_id_uses_updateFilterView(self, mock_sheets_service, fake_ctx):
        """
        When filter_view_id IS provided, the tool should still use updateFilterView
        (existing named-filter-view path must keep working).
        """
        from gsheets_mcp.tools.filters import apply_filter_criteria

        result = apply_filter_criteria(
            spreadsheet_id=SPREADSHEET_ID,
            sheet_name=SHEET_NAME,
            filter_view_id=99,
            criteria=SAMPLE_CRITERIA,
            ctx=fake_ctx,
        )

        assert result.get("success") is True, f"Tool returned failure: {result}"

        matched = assert_batchupdate_body(mock_sheets_service, "updateFilterView")
        fv = matched[0]["updateFilterView"]["filter"]
        assert fv.get("filterViewId") == 99

    def test_no_filter_view_id_success_message(self, mock_sheets_service, fake_ctx):
        """Result message should not reference a filter_view_id when none was given."""
        from gsheets_mcp.tools.filters import apply_filter_criteria

        result = apply_filter_criteria(
            spreadsheet_id=SPREADSHEET_ID,
            sheet_name=SHEET_NAME,
            criteria=SAMPLE_CRITERIA,
            ctx=fake_ctx,
        )
        assert result.get("success") is True


# ---------------------------------------------------------------------------
# BUG 3b: create_filter — return usable handle
# ---------------------------------------------------------------------------


class TestCreateFilter:
    def test_returns_sheet_id_in_result(self, mock_sheets_service, fake_ctx):
        """
        Before fix: returned only {success, message, range} — no sheetId.
        After fix:  returned result contains sheetId so callers can reference the filter.
        """
        from gsheets_mcp.tools.filters import create_filter

        result = create_filter(
            spreadsheet_id=SPREADSHEET_ID,
            sheet_name=SHEET_NAME,
            range="A1:D10",
            ctx=fake_ctx,
        )

        assert result.get("success") is True, f"Tool returned failure: {result}"
        assert "sheet_id" in result, (
            f"create_filter result missing 'sheet_id'. Got keys: {list(result.keys())}"
        )

    def test_returns_range_in_result(self, mock_sheets_service, fake_ctx):
        """Result must echo back the range so callers know what was filtered."""
        from gsheets_mcp.tools.filters import create_filter

        result = create_filter(
            spreadsheet_id=SPREADSHEET_ID,
            sheet_name=SHEET_NAME,
            range="B2:E5",
            ctx=fake_ctx,
        )

        assert result.get("range") == "B2:E5"

    def test_still_emits_setBasicFilter(self, mock_sheets_service, fake_ctx):
        """create_filter should still send the setBasicFilter batchUpdate request."""
        from gsheets_mcp.tools.filters import create_filter

        create_filter(
            spreadsheet_id=SPREADSHEET_ID,
            sheet_name=SHEET_NAME,
            range="A1:C5",
            ctx=fake_ctx,
        )

        assert_batchupdate_body(mock_sheets_service, "setBasicFilter")
