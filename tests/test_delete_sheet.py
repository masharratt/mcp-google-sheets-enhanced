"""
TDD tests for delete_sheet in gsheets_mcp/tools/sheets.py.

Removes a sheet tab by name via a deleteSheet batchUpdate request.
"""

import pytest

# Ensure all tools are registered before tests run.
import server  # noqa: F401

from tests.conftest import assert_batchupdate_body


class TestDeleteSheet:
    def test_sends_deleteSheet_request(self, fake_ctx, mock_sheets_service):
        """delete_sheet calls batchUpdate with a deleteSheet request for the resolved sheetId."""
        from gsheets_mcp.tools.sheets import delete_sheet

        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Scratch', 'sheetId': 12}}],
            'replies': [{}],
        })

        delete_sheet(spreadsheet_id='sid', sheet='Scratch', ctx=fake_ctx)

        matched = assert_batchupdate_body(mock_sheets_service, 'deleteSheet')
        assert matched[0]['deleteSheet']['sheetId'] == 12

    def test_returns_success(self, fake_ctx, mock_sheets_service):
        """delete_sheet returns success=True with the deleted sheet name and id."""
        from gsheets_mcp.tools.sheets import delete_sheet

        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Old', 'sheetId': 3}}],
            'replies': [{}],
        })

        result = delete_sheet(spreadsheet_id='sid', sheet='Old', ctx=fake_ctx)

        assert result['success'] is True
        assert result['sheet'] == 'Old'
        assert result['sheet_id'] == 3
        assert result['spreadsheetId'] == 'sid'

    def test_sheet_not_found_returns_error(self, fake_ctx, mock_sheets_service):
        """delete_sheet returns an error dict when the sheet does not exist."""
        from gsheets_mcp.tools.sheets import delete_sheet

        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Other', 'sheetId': 1}}],
        })

        result = delete_sheet(spreadsheet_id='sid', sheet='Missing', ctx=fake_ctx)

        assert result.get('success') is not True
        assert 'Missing' in (result.get('error') or '')
