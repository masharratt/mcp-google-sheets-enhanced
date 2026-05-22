"""
TDD tests for new filter view tools: create_filter_view and delete_filter_view.
"""

import pytest

import server  # noqa: F401 - ensures all tools are registered


_SHEET_META = {'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}]}


class TestCreateFilterView:
    def test_sends_addfilerview_request(self, fake_ctx, mock_sheets_service):
        """create_filter_view sends an addFilterView batchUpdate request."""
        from gsheets_mcp.tools.filters import create_filter_view

        # Include sheets metadata so _get_sheet_id succeeds; batchUpdate uses same execute().
        mock_sheets_service.set_execute_return({
            **_SHEET_META,
            'replies': [{'addFilterView': {'filter': {'filterViewId': 42}}}]
        })

        result = create_filter_view(
            spreadsheet_id='ss-id',
            sheet='Sheet1',
            range='A1:D10',
            title='My Filter',
            ctx=fake_ctx,
        )

        assert result['success'] is True

    def test_request_body_contains_correct_range(self, fake_ctx, mock_sheets_service):
        """create_filter_view encodes A1:D10 into GridRange indices correctly."""
        from gsheets_mcp.tools.filters import create_filter_view
        from tests.conftest import assert_batchupdate_body

        mock_sheets_service.set_execute_return({
            **_SHEET_META,
            'replies': [{'addFilterView': {'filter': {'filterViewId': 7}}}]
        })

        create_filter_view(
            spreadsheet_id='ss-id',
            sheet='Sheet1',
            range='A1:D10',
            title='My Filter',
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'addFilterView')
        grid_range = matched[0]['addFilterView']['filter']['range']
        assert grid_range['sheetId'] == 0
        assert grid_range['startRowIndex'] == 0       # row 1 -> index 0
        assert grid_range['endRowIndex'] == 10        # row 10 -> exclusive index 10
        assert grid_range['startColumnIndex'] == 0    # col A -> index 0
        assert grid_range['endColumnIndex'] == 4      # col D -> exclusive index 4

    def test_request_body_contains_title(self, fake_ctx, mock_sheets_service):
        """create_filter_view places the title in the filter spec."""
        from gsheets_mcp.tools.filters import create_filter_view
        from tests.conftest import assert_batchupdate_body

        mock_sheets_service.set_execute_return({
            **_SHEET_META,
            'replies': [{'addFilterView': {'filter': {'filterViewId': 1}}}]
        })

        create_filter_view(
            spreadsheet_id='ss-id',
            sheet='Sheet1',
            range='B2:C5',
            title='Sales View',
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'addFilterView')
        assert matched[0]['addFilterView']['filter']['title'] == 'Sales View'

    def test_request_body_includes_criteria_when_provided(self, fake_ctx, mock_sheets_service):
        """create_filter_view passes criteria into the filterView when supplied."""
        from gsheets_mcp.tools.filters import create_filter_view
        from tests.conftest import assert_batchupdate_body

        criteria = {
            "0": {
                "condition": {
                    "type": "NUMBER_GREATER",
                    "values": [{"userEnteredValue": "100"}]
                }
            }
        }

        mock_sheets_service.set_execute_return({
            **_SHEET_META,
            'replies': [{'addFilterView': {'filter': {'filterViewId': 3}}}]
        })

        create_filter_view(
            spreadsheet_id='ss-id',
            sheet='Sheet1',
            range='A1:C10',
            title='Filtered',
            criteria=criteria,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'addFilterView')
        assert matched[0]['addFilterView']['filter']['criteria'] == criteria

    def test_no_criteria_key_when_not_provided(self, fake_ctx, mock_sheets_service):
        """create_filter_view omits criteria key when no criteria given."""
        from gsheets_mcp.tools.filters import create_filter_view
        from tests.conftest import assert_batchupdate_body

        mock_sheets_service.set_execute_return({
            **_SHEET_META,
            'replies': [{'addFilterView': {'filter': {'filterViewId': 5}}}]
        })

        create_filter_view(
            spreadsheet_id='ss-id',
            sheet='Sheet1',
            range='A1:B3',
            title='No Criteria',
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'addFilterView')
        assert 'criteria' not in matched[0]['addFilterView']['filter']

    def test_returns_filter_view_id_from_reply(self, fake_ctx, mock_sheets_service):
        """create_filter_view extracts and returns the filterViewId from the API reply."""
        from gsheets_mcp.tools.filters import create_filter_view

        mock_sheets_service.set_execute_return({
            **_SHEET_META,
            'replies': [{'addFilterView': {'filter': {'filterViewId': 99}}}]
        })

        result = create_filter_view(
            spreadsheet_id='ss-id',
            sheet='Sheet1',
            range='A1:Z100',
            title='Big View',
            ctx=fake_ctx,
        )

        assert result['success'] is True
        assert result['filter_view_id'] == 99

    def test_returns_error_on_exception(self, fake_ctx, mock_sheets_service):
        """create_filter_view catches exceptions and returns success=False."""
        from gsheets_mcp.tools.filters import create_filter_view

        # Make the mock raise on execute
        mock_sheets_service.set_execute_return(None)
        original_execute = mock_sheets_service.execute

        def _raise():
            raise RuntimeError("API error")

        mock_sheets_service.execute = _raise

        result = create_filter_view(
            spreadsheet_id='bad-id',
            sheet='NoSheet',
            range='A1:B2',
            title='Broken',
            ctx=fake_ctx,
        )

        assert result['success'] is False
        assert 'error' in result['message'].lower() or 'error' in result.get('message', '').lower()

        # Restore
        mock_sheets_service.execute = original_execute


class TestDeleteFilterView:
    def test_sends_deletefilerview_request(self, fake_ctx, mock_sheets_service):
        """delete_filter_view sends a deleteFilterView batchUpdate request."""
        from gsheets_mcp.tools.filters import delete_filter_view
        from tests.conftest import assert_batchupdate_body

        mock_sheets_service.set_execute_return({'replies': [{}]})

        delete_filter_view(
            spreadsheet_id='ss-id',
            filter_view_id=42,
            ctx=fake_ctx,
        )

        assert_batchupdate_body(mock_sheets_service, 'deleteFilterView')

    def test_request_body_contains_correct_filter_view_id(self, fake_ctx, mock_sheets_service):
        """delete_filter_view sends the correct filterViewId in the request."""
        from gsheets_mcp.tools.filters import delete_filter_view
        from tests.conftest import assert_batchupdate_body

        mock_sheets_service.set_execute_return({'replies': [{}]})

        delete_filter_view(
            spreadsheet_id='ss-id',
            filter_view_id=77,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'deleteFilterView')
        assert matched[0]['deleteFilterView']['filterId'] == 77

    def test_returns_success_true(self, fake_ctx, mock_sheets_service):
        """delete_filter_view returns success=True on success."""
        from gsheets_mcp.tools.filters import delete_filter_view

        mock_sheets_service.set_execute_return({'replies': [{}]})

        result = delete_filter_view(
            spreadsheet_id='ss-id',
            filter_view_id=10,
            ctx=fake_ctx,
        )

        assert result['success'] is True

    def test_returns_filter_view_id_in_response(self, fake_ctx, mock_sheets_service):
        """delete_filter_view echoes the filter_view_id in the response."""
        from gsheets_mcp.tools.filters import delete_filter_view

        mock_sheets_service.set_execute_return({'replies': [{}]})

        result = delete_filter_view(
            spreadsheet_id='ss-id',
            filter_view_id=55,
            ctx=fake_ctx,
        )

        assert result['filter_view_id'] == 55

    def test_returns_error_on_exception(self, fake_ctx, mock_sheets_service):
        """delete_filter_view catches exceptions and returns success=False."""
        from gsheets_mcp.tools.filters import delete_filter_view

        original_execute = mock_sheets_service.execute

        def _raise():
            raise RuntimeError("delete failed")

        mock_sheets_service.execute = _raise

        result = delete_filter_view(
            spreadsheet_id='ss-id',
            filter_view_id=1,
            ctx=fake_ctx,
        )

        assert result['success'] is False

        mock_sheets_service.execute = original_execute
