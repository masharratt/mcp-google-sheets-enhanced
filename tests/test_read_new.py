"""
Tests for new read tools: get_spreadsheet_metadata and batch_get_values.

TDD: these tests were written before the implementation.
"""

import pytest

# Ensure tools are registered before tests run.
import server  # noqa: F401


# ---------------------------------------------------------------------------
# get_spreadsheet_metadata
# ---------------------------------------------------------------------------

class TestGetSpreadsheetMetadata:
    """Tests for get_spreadsheet_metadata tool."""

    def _fake_spreadsheet_response(self):
        """Realistic spreadsheets.get response with fields mask applied."""
        return {
            'spreadsheetId': 'test-sid',
            'properties': {
                'title': 'My Workbook',
                'locale': 'en_US',
                'timeZone': 'America/New_York',
                'autoRecalc': 'ON_CHANGE',
                'defaultFormat': {}
            },
            'sheets': [
                {
                    'properties': {
                        'sheetId': 0,
                        'title': 'Sheet1',
                        'index': 0,
                        'sheetType': 'GRID',
                        'hidden': False,
                        'gridProperties': {
                            'rowCount': 1000,
                            'columnCount': 26
                        }
                    }
                },
                {
                    'properties': {
                        'sheetId': 1,
                        'title': 'Data',
                        'index': 1,
                        'sheetType': 'GRID',
                        'hidden': True,
                        'gridProperties': {
                            'rowCount': 500,
                            'columnCount': 10
                        }
                    }
                }
            ]
        }

    def test_returns_spreadsheet_level_properties(self, fake_ctx, mock_sheets_service):
        """Top-level properties (title, locale, timeZone, autoRecalc) appear in result."""
        from gsheets_mcp.tools.read import get_spreadsheet_metadata

        mock_sheets_service.set_execute_return(self._fake_spreadsheet_response())

        result = get_spreadsheet_metadata(
            spreadsheet_id='test-sid',
            ctx=fake_ctx
        )

        props = result['properties']
        assert props['title'] == 'My Workbook'
        assert props['locale'] == 'en_US'
        assert props['timeZone'] == 'America/New_York'
        assert props['autoRecalc'] == 'ON_CHANGE'
        assert 'defaultFormat' in props

    def test_returns_sheet_properties_by_default(self, fake_ctx, mock_sheets_service):
        """With include_sheet_properties=True (default), sheets list is present."""
        from gsheets_mcp.tools.read import get_spreadsheet_metadata

        mock_sheets_service.set_execute_return(self._fake_spreadsheet_response())

        result = get_spreadsheet_metadata(
            spreadsheet_id='test-sid',
            ctx=fake_ctx
        )

        assert 'sheets' in result
        assert len(result['sheets']) == 2

    def test_sheet_properties_have_expected_keys(self, fake_ctx, mock_sheets_service):
        """Each sheet entry exposes sheetId, title, index, sheetType, hidden, gridProperties."""
        from gsheets_mcp.tools.read import get_spreadsheet_metadata

        mock_sheets_service.set_execute_return(self._fake_spreadsheet_response())

        result = get_spreadsheet_metadata(
            spreadsheet_id='test-sid',
            ctx=fake_ctx
        )

        sheet = result['sheets'][0]['properties']
        assert sheet['sheetId'] == 0
        assert sheet['title'] == 'Sheet1'
        assert sheet['index'] == 0
        assert sheet['sheetType'] == 'GRID'
        assert sheet['hidden'] is False
        assert sheet['gridProperties']['rowCount'] == 1000
        assert sheet['gridProperties']['columnCount'] == 26

    def test_hidden_sheet_flag_is_preserved(self, fake_ctx, mock_sheets_service):
        """hidden=True on Data sheet is reflected in the result."""
        from gsheets_mcp.tools.read import get_spreadsheet_metadata

        mock_sheets_service.set_execute_return(self._fake_spreadsheet_response())

        result = get_spreadsheet_metadata(
            spreadsheet_id='test-sid',
            ctx=fake_ctx
        )

        data_sheet = result['sheets'][1]['properties']
        assert data_sheet['title'] == 'Data'
        assert data_sheet['hidden'] is True

    def test_exclude_sheet_properties_omits_sheets_key(self, fake_ctx, mock_sheets_service):
        """With include_sheet_properties=False, the sheets key is absent."""
        from gsheets_mcp.tools.read import get_spreadsheet_metadata

        # Return a response without sheets (fields mask excluded them).
        mock_sheets_service.set_execute_return({
            'spreadsheetId': 'test-sid',
            'properties': {
                'title': 'My Workbook',
                'locale': 'en_US',
                'timeZone': 'America/New_York',
                'autoRecalc': 'ON_CHANGE',
                'defaultFormat': {}
            }
        })

        result = get_spreadsheet_metadata(
            spreadsheet_id='test-sid',
            include_sheet_properties=False,
            ctx=fake_ctx
        )

        assert 'sheets' not in result

    def test_calls_spreadsheets_get_not_values(self, fake_ctx, mock_sheets_service):
        """Verifies the tool goes through spreadsheets().get(), not values() API."""
        from gsheets_mcp.tools.read import get_spreadsheet_metadata

        mock_sheets_service.set_execute_return(self._fake_spreadsheet_response())

        get_spreadsheet_metadata(spreadsheet_id='test-sid', ctx=fake_ctx)

        # The mock records the last kwargs for each named method.
        # 'get' should have been called with spreadsheetId and fields.
        get_kwargs = mock_sheets_service._last_call_kwargs.get('get', {})
        assert get_kwargs.get('spreadsheetId') == 'test-sid'
        assert 'fields' in get_kwargs

    def test_fields_mask_excludes_cell_data(self, fake_ctx, mock_sheets_service):
        """The fields mask must NOT request sheets.data (grid/cell data)."""
        from gsheets_mcp.tools.read import get_spreadsheet_metadata

        mock_sheets_service.set_execute_return(self._fake_spreadsheet_response())

        get_spreadsheet_metadata(spreadsheet_id='test-sid', ctx=fake_ctx)

        get_kwargs = mock_sheets_service._last_call_kwargs.get('get', {})
        fields = get_kwargs.get('fields', '')
        assert 'data' not in fields.lower() or 'sheets.data' not in fields

    def test_spreadsheet_id_in_result(self, fake_ctx, mock_sheets_service):
        """Result contains the spreadsheetId field."""
        from gsheets_mcp.tools.read import get_spreadsheet_metadata

        mock_sheets_service.set_execute_return(self._fake_spreadsheet_response())

        result = get_spreadsheet_metadata(spreadsheet_id='test-sid', ctx=fake_ctx)

        assert result.get('spreadsheetId') == 'test-sid'


# ---------------------------------------------------------------------------
# batch_get_values
# ---------------------------------------------------------------------------

class TestBatchGetValues:
    """Tests for batch_get_values tool."""

    def _fake_batch_response(self):
        """Realistic spreadsheets.values.batchGet response."""
        return {
            'spreadsheetId': 'test-sid',
            'valueRanges': [
                {
                    'range': 'Sheet1!A1:B2',
                    'majorDimension': 'ROWS',
                    'values': [['Name', 'Score'], ['Alice', '95']]
                },
                {
                    'range': 'Sheet1!D1:D3',
                    'majorDimension': 'ROWS',
                    'values': [['X'], ['Y'], ['Z']]
                }
            ]
        }

    def test_returns_list_of_range_value_dicts(self, fake_ctx, mock_sheets_service):
        """Result is a list with one entry per requested range."""
        from gsheets_mcp.tools.read import batch_get_values

        mock_sheets_service.set_execute_return(self._fake_batch_response())

        result = batch_get_values(
            spreadsheet_id='test-sid',
            ranges=['Sheet1!A1:B2', 'Sheet1!D1:D3'],
            ctx=fake_ctx
        )

        assert isinstance(result, list)
        assert len(result) == 2

    def test_each_entry_has_range_and_values_keys(self, fake_ctx, mock_sheets_service):
        """Each item in the result has 'range' and 'values' keys."""
        from gsheets_mcp.tools.read import batch_get_values

        mock_sheets_service.set_execute_return(self._fake_batch_response())

        result = batch_get_values(
            spreadsheet_id='test-sid',
            ranges=['Sheet1!A1:B2', 'Sheet1!D1:D3'],
            ctx=fake_ctx
        )

        for entry in result:
            assert 'range' in entry
            assert 'values' in entry

    def test_values_match_api_response(self, fake_ctx, mock_sheets_service):
        """Values in each entry match what the API returned."""
        from gsheets_mcp.tools.read import batch_get_values

        mock_sheets_service.set_execute_return(self._fake_batch_response())

        result = batch_get_values(
            spreadsheet_id='test-sid',
            ranges=['Sheet1!A1:B2', 'Sheet1!D1:D3'],
            ctx=fake_ctx
        )

        assert result[0]['values'] == [['Name', 'Score'], ['Alice', '95']]
        assert result[1]['values'] == [['X'], ['Y'], ['Z']]

    def test_calls_batchget_not_separate_gets(self, fake_ctx, mock_sheets_service):
        """Tool calls values().batchGet (one API call), not values().get multiple times."""
        from gsheets_mcp.tools.read import batch_get_values

        mock_sheets_service.set_execute_return(self._fake_batch_response())

        batch_get_values(
            spreadsheet_id='test-sid',
            ranges=['Sheet1!A1:B2', 'Sheet1!D1:D3'],
            ctx=fake_ctx
        )

        # batchGet should have been called with the spreadsheetId and ranges.
        batch_kwargs = mock_sheets_service._last_call_kwargs.get('batchGet', {})
        assert batch_kwargs.get('spreadsheetId') == 'test-sid'
        assert 'Sheet1!A1:B2' in batch_kwargs.get('ranges', [])
        assert 'Sheet1!D1:D3' in batch_kwargs.get('ranges', [])

    def test_default_render_option_is_formatted(self, fake_ctx, mock_sheets_service):
        """Default value_render_option is FORMATTED_VALUE."""
        from gsheets_mcp.tools.read import batch_get_values

        mock_sheets_service.set_execute_return(self._fake_batch_response())

        batch_get_values(
            spreadsheet_id='test-sid',
            ranges=['Sheet1!A1:B2'],
            ctx=fake_ctx
        )

        batch_kwargs = mock_sheets_service._last_call_kwargs.get('batchGet', {})
        assert batch_kwargs.get('valueRenderOption') == 'FORMATTED_VALUE'

    def test_custom_render_option_is_forwarded(self, fake_ctx, mock_sheets_service):
        """Passing value_render_option='FORMULA' forwards it to the API call."""
        from gsheets_mcp.tools.read import batch_get_values

        mock_sheets_service.set_execute_return(self._fake_batch_response())

        batch_get_values(
            spreadsheet_id='test-sid',
            ranges=['Sheet1!A1:B2'],
            value_render_option='FORMULA',
            ctx=fake_ctx
        )

        batch_kwargs = mock_sheets_service._last_call_kwargs.get('batchGet', {})
        assert batch_kwargs.get('valueRenderOption') == 'FORMULA'

    def test_default_major_dimension_is_rows(self, fake_ctx, mock_sheets_service):
        """Default major_dimension is ROWS."""
        from gsheets_mcp.tools.read import batch_get_values

        mock_sheets_service.set_execute_return(self._fake_batch_response())

        batch_get_values(
            spreadsheet_id='test-sid',
            ranges=['Sheet1!A1:B2'],
            ctx=fake_ctx
        )

        batch_kwargs = mock_sheets_service._last_call_kwargs.get('batchGet', {})
        assert batch_kwargs.get('majorDimension') == 'ROWS'

    def test_columns_major_dimension_is_forwarded(self, fake_ctx, mock_sheets_service):
        """Passing major_dimension='COLUMNS' forwards it to the API call."""
        from gsheets_mcp.tools.read import batch_get_values

        mock_sheets_service.set_execute_return(self._fake_batch_response())

        batch_get_values(
            spreadsheet_id='test-sid',
            ranges=['Sheet1!A1:B2'],
            major_dimension='COLUMNS',
            ctx=fake_ctx
        )

        batch_kwargs = mock_sheets_service._last_call_kwargs.get('batchGet', {})
        assert batch_kwargs.get('majorDimension') == 'COLUMNS'

    def test_empty_values_key_when_range_is_empty(self, fake_ctx, mock_sheets_service):
        """A range with no data returns values as an empty list, not missing key."""
        from gsheets_mcp.tools.read import batch_get_values

        mock_sheets_service.set_execute_return({
            'spreadsheetId': 'test-sid',
            'valueRanges': [
                {
                    'range': 'Sheet1!A1:B2',
                    'majorDimension': 'ROWS'
                    # no 'values' key - API omits it for empty ranges
                }
            ]
        })

        result = batch_get_values(
            spreadsheet_id='test-sid',
            ranges=['Sheet1!A1:B2'],
            ctx=fake_ctx
        )

        assert result[0]['values'] == []

    def test_single_range_still_returns_list(self, fake_ctx, mock_sheets_service):
        """Even with one range, the result is a list (not unwrapped to a dict)."""
        from gsheets_mcp.tools.read import batch_get_values

        mock_sheets_service.set_execute_return({
            'spreadsheetId': 'test-sid',
            'valueRanges': [
                {
                    'range': 'Sheet1!A1:A1',
                    'majorDimension': 'ROWS',
                    'values': [['hello']]
                }
            ]
        })

        result = batch_get_values(
            spreadsheet_id='test-sid',
            ranges=['Sheet1!A1:A1'],
            ctx=fake_ctx
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]['values'] == [['hello']]
