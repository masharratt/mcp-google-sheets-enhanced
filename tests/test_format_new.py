"""
TDD tests for new format tools: add_banding and remove_banding.
"""

import pytest

import server  # noqa: F401 - ensures all tools are registered


_SHEET_META = {'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}]}


class TestAddBanding:
    def test_sends_addbanding_request(self, fake_ctx, mock_sheets_service):
        """add_banding sends an addBanding batchUpdate request."""
        from gsheets_mcp.tools.format import add_banding
        from tests.conftest import assert_batchupdate_body

        # Include sheets metadata so _get_sheet_id succeeds; batchUpdate uses same execute().
        mock_sheets_service.set_execute_return({
            **_SHEET_META,
            'replies': [{'addBanding': {'bandedRange': {'bandedRangeId': 1}}}]
        })

        add_banding(
            spreadsheet_id='ss-id',
            sheet='Sheet1',
            range='A1:D10',
            first_band_color={'red': 1.0, 'green': 1.0, 'blue': 1.0},
            second_band_color={'red': 0.8, 'green': 0.8, 'blue': 0.8},
            ctx=fake_ctx,
        )

        assert_batchupdate_body(mock_sheets_service, 'addBanding')

    def test_request_body_contains_correct_range(self, fake_ctx, mock_sheets_service):
        """add_banding encodes A1:D10 into GridRange indices correctly."""
        from gsheets_mcp.tools.format import add_banding
        from tests.conftest import assert_batchupdate_body

        mock_sheets_service.set_execute_return({
            **_SHEET_META,
            'replies': [{'addBanding': {'bandedRange': {'bandedRangeId': 2}}}]
        })

        add_banding(
            spreadsheet_id='ss-id',
            sheet='Sheet1',
            range='A1:D10',
            first_band_color={'red': 1.0, 'green': 1.0, 'blue': 1.0},
            second_band_color={'red': 0.8, 'green': 0.8, 'blue': 0.8},
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'addBanding')
        grid_range = matched[0]['addBanding']['bandedRange']['range']
        assert grid_range['sheetId'] == 0
        assert grid_range['startRowIndex'] == 0
        assert grid_range['endRowIndex'] == 10
        assert grid_range['startColumnIndex'] == 0
        assert grid_range['endColumnIndex'] == 4

    def test_row_banding_uses_row_properties(self, fake_ctx, mock_sheets_service):
        """add_banding with apply_to='ROWS' sets rowProperties on the BandedRange."""
        from gsheets_mcp.tools.format import add_banding
        from tests.conftest import assert_batchupdate_body

        mock_sheets_service.set_execute_return({
            **_SHEET_META,
            'replies': [{'addBanding': {'bandedRange': {'bandedRangeId': 3}}}]
        })

        add_banding(
            spreadsheet_id='ss-id',
            sheet='Sheet1',
            range='A1:C5',
            first_band_color={'red': 1.0, 'green': 0.9, 'blue': 0.9},
            second_band_color={'red': 0.9, 'green': 1.0, 'blue': 0.9},
            apply_to='ROWS',
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'addBanding')
        banded_range = matched[0]['addBanding']['bandedRange']
        assert 'rowProperties' in banded_range
        assert 'columnProperties' not in banded_range

    def test_column_banding_uses_column_properties(self, fake_ctx, mock_sheets_service):
        """add_banding with apply_to='COLUMNS' sets columnProperties on the BandedRange."""
        from gsheets_mcp.tools.format import add_banding
        from tests.conftest import assert_batchupdate_body

        mock_sheets_service.set_execute_return({
            **_SHEET_META,
            'replies': [{'addBanding': {'bandedRange': {'bandedRangeId': 4}}}]
        })

        add_banding(
            spreadsheet_id='ss-id',
            sheet='Sheet1',
            range='A1:C5',
            first_band_color={'red': 0.0, 'green': 0.5, 'blue': 1.0},
            second_band_color={'red': 1.0, 'green': 1.0, 'blue': 1.0},
            apply_to='COLUMNS',
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'addBanding')
        banded_range = matched[0]['addBanding']['bandedRange']
        assert 'columnProperties' in banded_range
        assert 'rowProperties' not in banded_range

    def test_band_colors_are_set_in_properties(self, fake_ctx, mock_sheets_service):
        """add_banding sets firstBandColor and secondBandColor in the properties."""
        from gsheets_mcp.tools.format import add_banding
        from tests.conftest import assert_batchupdate_body

        first = {'red': 0.1, 'green': 0.2, 'blue': 0.3}
        second = {'red': 0.4, 'green': 0.5, 'blue': 0.6}

        mock_sheets_service.set_execute_return({
            **_SHEET_META,
            'replies': [{'addBanding': {'bandedRange': {'bandedRangeId': 5}}}]
        })

        add_banding(
            spreadsheet_id='ss-id',
            sheet='Sheet1',
            range='A1:B4',
            first_band_color=first,
            second_band_color=second,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'addBanding')
        props = matched[0]['addBanding']['bandedRange']['rowProperties']
        assert props['firstBandColor'] == first
        assert props['secondBandColor'] == second

    def test_header_color_included_when_provided(self, fake_ctx, mock_sheets_service):
        """add_banding includes headerColor in properties when header_color is given."""
        from gsheets_mcp.tools.format import add_banding
        from tests.conftest import assert_batchupdate_body

        header = {'red': 0.0, 'green': 0.0, 'blue': 1.0}

        mock_sheets_service.set_execute_return({
            **_SHEET_META,
            'replies': [{'addBanding': {'bandedRange': {'bandedRangeId': 6}}}]
        })

        add_banding(
            spreadsheet_id='ss-id',
            sheet='Sheet1',
            range='A1:E20',
            first_band_color={'red': 1.0, 'green': 1.0, 'blue': 1.0},
            second_band_color={'red': 0.9, 'green': 0.9, 'blue': 0.9},
            header_color=header,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'addBanding')
        props = matched[0]['addBanding']['bandedRange']['rowProperties']
        assert props['headerColor'] == header

    def test_no_header_color_key_when_not_provided(self, fake_ctx, mock_sheets_service):
        """add_banding omits headerColor when not supplied."""
        from gsheets_mcp.tools.format import add_banding
        from tests.conftest import assert_batchupdate_body

        mock_sheets_service.set_execute_return({
            **_SHEET_META,
            'replies': [{'addBanding': {'bandedRange': {'bandedRangeId': 7}}}]
        })

        add_banding(
            spreadsheet_id='ss-id',
            sheet='Sheet1',
            range='A1:B3',
            first_band_color={'red': 1.0, 'green': 1.0, 'blue': 1.0},
            second_band_color={'red': 0.8, 'green': 0.8, 'blue': 0.8},
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'addBanding')
        props = matched[0]['addBanding']['bandedRange']['rowProperties']
        assert 'headerColor' not in props

    def test_returns_banded_range_id_from_reply(self, fake_ctx, mock_sheets_service):
        """add_banding extracts and returns the bandedRangeId from the API reply."""
        from gsheets_mcp.tools.format import add_banding

        mock_sheets_service.set_execute_return({
            **_SHEET_META,
            'replies': [{'addBanding': {'bandedRange': {'bandedRangeId': 88}}}]
        })

        result = add_banding(
            spreadsheet_id='ss-id',
            sheet='Sheet1',
            range='A1:C10',
            first_band_color={'red': 1.0, 'green': 1.0, 'blue': 1.0},
            second_band_color={'red': 0.9, 'green': 0.9, 'blue': 0.9},
            ctx=fake_ctx,
        )

        assert result['success'] is True
        assert result['banded_range_id'] == 88

    def test_returns_error_on_exception(self, fake_ctx, mock_sheets_service):
        """add_banding catches exceptions and returns success=False."""
        from gsheets_mcp.tools.format import add_banding

        original_execute = mock_sheets_service.execute

        def _raise():
            raise RuntimeError("banding failed")

        mock_sheets_service.execute = _raise

        result = add_banding(
            spreadsheet_id='bad-id',
            sheet='NoSheet',
            range='A1:B2',
            first_band_color={'red': 1.0, 'green': 1.0, 'blue': 1.0},
            second_band_color={'red': 0.9, 'green': 0.9, 'blue': 0.9},
            ctx=fake_ctx,
        )

        assert result['success'] is False

        mock_sheets_service.execute = original_execute


class TestRemoveBanding:
    def test_sends_deletebanding_request(self, fake_ctx, mock_sheets_service):
        """remove_banding sends a deleteBanding batchUpdate request."""
        from gsheets_mcp.tools.format import remove_banding
        from tests.conftest import assert_batchupdate_body

        mock_sheets_service.set_execute_return({'replies': [{}]})

        remove_banding(
            spreadsheet_id='ss-id',
            banded_range_id=10,
            ctx=fake_ctx,
        )

        assert_batchupdate_body(mock_sheets_service, 'deleteBanding')

    def test_request_body_contains_correct_banded_range_id(self, fake_ctx, mock_sheets_service):
        """remove_banding sends the correct bandedRangeId in the request."""
        from gsheets_mcp.tools.format import remove_banding
        from tests.conftest import assert_batchupdate_body

        mock_sheets_service.set_execute_return({'replies': [{}]})

        remove_banding(
            spreadsheet_id='ss-id',
            banded_range_id=33,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'deleteBanding')
        assert matched[0]['deleteBanding']['bandedRangeId'] == 33

    def test_returns_success_true(self, fake_ctx, mock_sheets_service):
        """remove_banding returns success=True on success."""
        from gsheets_mcp.tools.format import remove_banding

        mock_sheets_service.set_execute_return({'replies': [{}]})

        result = remove_banding(
            spreadsheet_id='ss-id',
            banded_range_id=10,
            ctx=fake_ctx,
        )

        assert result['success'] is True

    def test_returns_banded_range_id_in_response(self, fake_ctx, mock_sheets_service):
        """remove_banding echoes the banded_range_id in the response."""
        from gsheets_mcp.tools.format import remove_banding

        mock_sheets_service.set_execute_return({'replies': [{}]})

        result = remove_banding(
            spreadsheet_id='ss-id',
            banded_range_id=66,
            ctx=fake_ctx,
        )

        assert result['banded_range_id'] == 66

    def test_returns_error_on_exception(self, fake_ctx, mock_sheets_service):
        """remove_banding catches exceptions and returns success=False."""
        from gsheets_mcp.tools.format import remove_banding

        original_execute = mock_sheets_service.execute

        def _raise():
            raise RuntimeError("delete banding failed")

        mock_sheets_service.execute = _raise

        result = remove_banding(
            spreadsheet_id='ss-id',
            banded_range_id=1,
            ctx=fake_ctx,
        )

        assert result['success'] is False

        mock_sheets_service.execute = original_execute
