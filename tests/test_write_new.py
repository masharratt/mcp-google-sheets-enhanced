"""
TDD tests for new write tools: append_data, batch_clear_values, find_replace.

Drives each tool through fake_ctx (from conftest.py) and asserts the exact
API request body built.
"""

import pytest
from unittest.mock import MagicMock

# Import from conftest via pytest fixtures (fake_ctx, mock_sheets_service, assert_batchupdate_body)


# ---------------------------------------------------------------------------
# Helper: build a fresh _ChainableMock wired for both sheets().get() (for
# _get_sheet_id) AND a second terminal call (append / batchClear / batchUpdate).
# The _ChainableMock is stateless-chain: every call returns self, so a single
# execute_return applies to all .execute() calls on the chain. We need two
# different return values (get -> sheet metadata, append -> API response).
# We override set_execute_return between calls where needed.
# ---------------------------------------------------------------------------


# ============================================================
# append_data tests
# ============================================================

class TestAppendData:
    """Tests for the append_data tool."""

    def test_append_data_basic(self, fake_ctx, mock_sheets_service):
        """append_data calls values().append with correct spreadsheetId, range, and body."""
        from gsheets_mcp.tools.write import append_data

        mock_sheets_service.set_execute_return({
            'spreadsheetId': 'ss1',
            'tableRange': 'Sheet1!A1:C3',
            'updates': {'updatedRows': 2}
        })

        result = append_data(
            spreadsheet_id='ss1',
            sheet='Sheet1',
            data=[['a', 'b'], ['c', 'd']],
            ctx=fake_ctx
        )

        # Verify append was called
        assert 'append' in mock_sheets_service._last_call_kwargs
        kwargs = mock_sheets_service._last_call_kwargs['append']
        assert kwargs['spreadsheetId'] == 'ss1'
        # default range: whole sheet
        assert kwargs['range'] == 'Sheet1'
        assert kwargs['valueInputOption'] == 'USER_ENTERED'
        assert kwargs['insertDataOption'] == 'INSERT_ROWS'
        assert kwargs['body'] == {'values': [['a', 'b'], ['c', 'd']]}

        # Result is the API response
        assert result['updates']['updatedRows'] == 2

    def test_append_data_with_explicit_range(self, fake_ctx, mock_sheets_service):
        """append_data builds full_range as sheet!range when range param provided."""
        from gsheets_mcp.tools.write import append_data

        mock_sheets_service.set_execute_return({'updates': {'updatedRows': 1}})

        append_data(
            spreadsheet_id='ss1',
            sheet='Sheet1',
            range='A5',
            data=[['x']],
            ctx=fake_ctx
        )

        kwargs = mock_sheets_service._last_call_kwargs['append']
        assert kwargs['range'] == 'Sheet1!A5'

    def test_append_data_raw_value_input(self, fake_ctx, mock_sheets_service):
        """append_data passes RAW when value_input_option='RAW'."""
        from gsheets_mcp.tools.write import append_data

        mock_sheets_service.set_execute_return({'updates': {}})

        append_data(
            spreadsheet_id='ss1',
            sheet='Sheet1',
            data=[['=SUM(A1:A3)']],
            value_input_option='RAW',
            ctx=fake_ctx
        )

        kwargs = mock_sheets_service._last_call_kwargs['append']
        assert kwargs['valueInputOption'] == 'RAW'

    def test_append_data_overwrite_insert_option(self, fake_ctx, mock_sheets_service):
        """append_data passes OVERWRITE when insert_data_option='OVERWRITE'."""
        from gsheets_mcp.tools.write import append_data

        mock_sheets_service.set_execute_return({'updates': {}})

        append_data(
            spreadsheet_id='ss1',
            sheet='Sheet1',
            data=[['val']],
            insert_data_option='OVERWRITE',
            ctx=fake_ctx
        )

        kwargs = mock_sheets_service._last_call_kwargs['append']
        assert kwargs['insertDataOption'] == 'OVERWRITE'

    def test_append_data_returns_api_response(self, fake_ctx, mock_sheets_service):
        """append_data returns the full API response dict."""
        from gsheets_mcp.tools.write import append_data

        api_response = {
            'spreadsheetId': 'ss1',
            'tableRange': 'Sheet1!A1:B5',
            'updates': {
                'spreadsheetId': 'ss1',
                'updatedRange': 'Sheet1!A6:B7',
                'updatedRows': 2,
                'updatedColumns': 2,
                'updatedCells': 4
            }
        }
        mock_sheets_service.set_execute_return(api_response)

        result = append_data(
            spreadsheet_id='ss1',
            sheet='Sheet1',
            data=[['x', 'y'], ['z', 'w']],
            ctx=fake_ctx
        )

        assert result == api_response


# ============================================================
# batch_clear_values tests
# ============================================================

class TestBatchClearValues:
    """Tests for the batch_clear_values tool."""

    def test_batch_clear_basic(self, fake_ctx, mock_sheets_service):
        """batch_clear_values calls values().batchClear with correct spreadsheetId and ranges."""
        from gsheets_mcp.tools.write import batch_clear_values

        mock_sheets_service.set_execute_return({
            'spreadsheetId': 'ss2',
            'clearedRanges': ['Sheet1!A1:B2', 'Sheet2!C3:D4']
        })

        result = batch_clear_values(
            spreadsheet_id='ss2',
            ranges=['Sheet1!A1:B2', 'Sheet2!C3:D4'],
            ctx=fake_ctx
        )

        assert 'batchClear' in mock_sheets_service._last_call_kwargs
        kwargs = mock_sheets_service._last_call_kwargs['batchClear']
        assert kwargs['spreadsheetId'] == 'ss2'
        assert kwargs['body'] == {'ranges': ['Sheet1!A1:B2', 'Sheet2!C3:D4']}

    def test_batch_clear_returns_cleared_ranges(self, fake_ctx, mock_sheets_service):
        """batch_clear_values returns the clearedRanges list from the API response."""
        from gsheets_mcp.tools.write import batch_clear_values

        mock_sheets_service.set_execute_return({
            'spreadsheetId': 'ss2',
            'clearedRanges': ['Sheet1!A1:Z100']
        })

        result = batch_clear_values(
            spreadsheet_id='ss2',
            ranges=['Sheet1!A1:Z100'],
            ctx=fake_ctx
        )

        assert result == ['Sheet1!A1:Z100']

    def test_batch_clear_single_range(self, fake_ctx, mock_sheets_service):
        """batch_clear_values works with a single range in the list."""
        from gsheets_mcp.tools.write import batch_clear_values

        mock_sheets_service.set_execute_return({
            'spreadsheetId': 'ss2',
            'clearedRanges': ['Sheet1!A1:A10']
        })

        result = batch_clear_values(
            spreadsheet_id='ss2',
            ranges=['Sheet1!A1:A10'],
            ctx=fake_ctx
        )

        kwargs = mock_sheets_service._last_call_kwargs['batchClear']
        assert kwargs['body']['ranges'] == ['Sheet1!A1:A10']
        assert result == ['Sheet1!A1:A10']

    def test_batch_clear_multiple_ranges(self, fake_ctx, mock_sheets_service):
        """batch_clear_values passes all provided ranges to the API."""
        from gsheets_mcp.tools.write import batch_clear_values

        ranges = ['A1:B2', 'C3:D4', 'E5:F6']
        mock_sheets_service.set_execute_return({
            'spreadsheetId': 'ss2',
            'clearedRanges': ranges
        })

        batch_clear_values(
            spreadsheet_id='ss2',
            ranges=ranges,
            ctx=fake_ctx
        )

        kwargs = mock_sheets_service._last_call_kwargs['batchClear']
        assert kwargs['body']['ranges'] == ranges


# ============================================================
# find_replace tests
# ============================================================

class TestFindReplace:
    """Tests for the find_replace tool (spreadsheets.batchUpdate with findReplace request)."""

    def test_find_replace_all_sheets(self, fake_ctx, mock_sheets_service):
        """find_replace with no sheet targets all sheets (allSheets=True in request)."""
        from gsheets_mcp.tools.write import find_replace

        mock_sheets_service.set_execute_return({
            'spreadsheetId': 'ss3',
            'replies': [{'findReplace': {'occurrencesChanged': 3, 'valuesChanged': 3}}]
        })

        result = find_replace(
            spreadsheet_id='ss3',
            find='foo',
            replacement='bar',
            ctx=fake_ctx
        )

        assert 'batchUpdate' in mock_sheets_service._last_call_kwargs
        kwargs = mock_sheets_service._last_call_kwargs['batchUpdate']
        assert kwargs['spreadsheetId'] == 'ss3'

        body = kwargs['body']
        requests = body.get('requests', [])
        fr_requests = [r for r in requests if 'findReplace' in r]
        assert len(fr_requests) == 1

        fr = fr_requests[0]['findReplace']
        assert fr['find'] == 'foo'
        assert fr['replacement'] == 'bar'
        assert fr.get('allSheets') is True
        assert 'sheetId' not in fr

    def test_find_replace_specific_sheet(self, fake_ctx, mock_sheets_service):
        """find_replace with a sheet name restricts to that sheetId (uses _get_sheet_id)."""
        from gsheets_mcp.tools.write import find_replace

        # The mock will return the metadata dict for spreadsheets().get() and
        # then the batchUpdate response for the find/replace call.
        # Because _ChainableMock returns self for every call chain, both
        # .execute() calls return the same _execute_return. We need the
        # spreadsheets().get() to return sheet metadata so _get_sheet_id works.
        # We set execute_return to include both sheets[] and replies[].
        # _get_sheet_id only reads 'sheets', batchUpdate response only reads 'replies'.
        mock_sheets_service.set_execute_return({
            'spreadsheetId': 'ss3',
            'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 42}}],
            'replies': [{'findReplace': {'occurrencesChanged': 1, 'valuesChanged': 1}}]
        })

        result = find_replace(
            spreadsheet_id='ss3',
            find='hello',
            replacement='world',
            sheet='Sheet1',
            ctx=fake_ctx
        )

        kwargs = mock_sheets_service._last_call_kwargs['batchUpdate']
        requests = kwargs['body']['requests']
        fr = [r for r in requests if 'findReplace' in r][0]['findReplace']

        assert fr['sheetId'] == 42
        assert 'allSheets' not in fr or fr.get('allSheets') is False

    def test_find_replace_match_case(self, fake_ctx, mock_sheets_service):
        """find_replace passes matchCase=True when requested."""
        from gsheets_mcp.tools.write import find_replace

        mock_sheets_service.set_execute_return({
            'replies': [{'findReplace': {'occurrencesChanged': 0}}]
        })

        find_replace(
            spreadsheet_id='ss3',
            find='Foo',
            replacement='Bar',
            match_case=True,
            ctx=fake_ctx
        )

        kwargs = mock_sheets_service._last_call_kwargs['batchUpdate']
        fr = [r for r in kwargs['body']['requests'] if 'findReplace' in r][0]['findReplace']
        assert fr['matchCase'] is True

    def test_find_replace_match_entire_cell(self, fake_ctx, mock_sheets_service):
        """find_replace passes matchEntireCell=True when requested."""
        from gsheets_mcp.tools.write import find_replace

        mock_sheets_service.set_execute_return({
            'replies': [{'findReplace': {'occurrencesChanged': 0}}]
        })

        find_replace(
            spreadsheet_id='ss3',
            find='exact',
            replacement='match',
            match_entire_cell=True,
            ctx=fake_ctx
        )

        kwargs = mock_sheets_service._last_call_kwargs['batchUpdate']
        fr = [r for r in kwargs['body']['requests'] if 'findReplace' in r][0]['findReplace']
        assert fr['matchEntireCell'] is True

    def test_find_replace_search_by_regex(self, fake_ctx, mock_sheets_service):
        """find_replace passes searchByRegex=True when requested."""
        from gsheets_mcp.tools.write import find_replace

        mock_sheets_service.set_execute_return({
            'replies': [{'findReplace': {'occurrencesChanged': 2}}]
        })

        find_replace(
            spreadsheet_id='ss3',
            find=r'\d+',
            replacement='NUM',
            search_by_regex=True,
            ctx=fake_ctx
        )

        kwargs = mock_sheets_service._last_call_kwargs['batchUpdate']
        fr = [r for r in kwargs['body']['requests'] if 'findReplace' in r][0]['findReplace']
        assert fr['searchByRegex'] is True

    def test_find_replace_include_formulas(self, fake_ctx, mock_sheets_service):
        """find_replace passes includeFormulas=True when requested."""
        from gsheets_mcp.tools.write import find_replace

        mock_sheets_service.set_execute_return({
            'replies': [{'findReplace': {'occurrencesChanged': 1}}]
        })

        find_replace(
            spreadsheet_id='ss3',
            find='SUM',
            replacement='AVERAGE',
            include_formulas=True,
            ctx=fake_ctx
        )

        kwargs = mock_sheets_service._last_call_kwargs['batchUpdate']
        fr = [r for r in kwargs['body']['requests'] if 'findReplace' in r][0]['findReplace']
        assert fr['includeFormulas'] is True

    def test_find_replace_returns_counts(self, fake_ctx, mock_sheets_service):
        """find_replace returns dict with occurrencesChanged and valuesChanged."""
        from gsheets_mcp.tools.write import find_replace

        mock_sheets_service.set_execute_return({
            'spreadsheetId': 'ss3',
            'replies': [{'findReplace': {'occurrencesChanged': 5, 'valuesChanged': 3}}]
        })

        result = find_replace(
            spreadsheet_id='ss3',
            find='x',
            replacement='y',
            ctx=fake_ctx
        )

        assert result['occurrencesChanged'] == 5
        assert result['valuesChanged'] == 3

    def test_find_replace_defaults_false_flags(self, fake_ctx, mock_sheets_service):
        """find_replace sends False for all boolean flags by default."""
        from gsheets_mcp.tools.write import find_replace

        mock_sheets_service.set_execute_return({
            'replies': [{'findReplace': {'occurrencesChanged': 0}}]
        })

        find_replace(
            spreadsheet_id='ss3',
            find='a',
            replacement='b',
            ctx=fake_ctx
        )

        kwargs = mock_sheets_service._last_call_kwargs['batchUpdate']
        fr = [r for r in kwargs['body']['requests'] if 'findReplace' in r][0]['findReplace']
        assert fr['matchCase'] is False
        assert fr['matchEntireCell'] is False
        assert fr['searchByRegex'] is False
        assert fr['includeFormulas'] is False
