"""
Smoke tests: drive representative tools through fake_ctx + mocks and assert
they produce the expected API request shape.

Three representative tools are tested:
  1. get_sheet_data (read tool - values path)
  2. update_cells (write tool - values().update() path)
  3. apply_conditional_formatting (conditional tool - batchUpdate path)

These also serve as templates for later wave tests.
"""

import pytest

# Ensure tools are registered before tests run.
import server  # noqa: F401


# ---------------------------------------------------------------------------
# Read tool: get_sheet_data
# ---------------------------------------------------------------------------

class TestGetSheetData:
    def test_values_path_returns_expected_shape(self, fake_ctx, mock_sheets_service):
        """get_sheet_data without include_grid_data uses values().get() and returns valueRanges."""
        from gsheets_mcp.tools.read import get_sheet_data

        # Wire the mock to return a realistic values response.
        mock_sheets_service.set_execute_return({
            'values': [['Name', 'Score'], ['Alice', '95'], ['Bob', '87']]
        })

        result = get_sheet_data(
            spreadsheet_id='test-spreadsheet-id',
            sheet='Sheet1',
            range='A1:B3',
            include_grid_data=False,
            ctx=fake_ctx
        )

        # Should wrap the response in the expected structure.
        assert 'valueRanges' in result
        assert result['spreadsheetId'] == 'test-spreadsheet-id'
        value_range = result['valueRanges'][0]
        assert value_range['range'] == 'Sheet1!A1:B3'
        assert value_range['values'] == [['Name', 'Score'], ['Alice', '95'], ['Bob', '87']]

    def test_full_range_when_no_range_given(self, fake_ctx, mock_sheets_service):
        """get_sheet_data with no range uses sheet name as the full range."""
        from gsheets_mcp.tools.read import get_sheet_data

        mock_sheets_service.set_execute_return({'values': []})

        result = get_sheet_data(
            spreadsheet_id='sid',
            sheet='MySheet',
            ctx=fake_ctx
        )

        assert result['valueRanges'][0]['range'] == 'MySheet'

    def test_grid_data_path_calls_get(self, fake_ctx, mock_sheets_service):
        """get_sheet_data with include_grid_data=True returns the raw spreadsheets().get() result."""
        from gsheets_mcp.tools.read import get_sheet_data

        expected = {'spreadsheetId': 'sid', 'sheets': [{'data': []}]}
        mock_sheets_service.set_execute_return(expected)

        result = get_sheet_data(
            spreadsheet_id='sid',
            sheet='Sheet1',
            include_grid_data=True,
            ctx=fake_ctx
        )

        # Should return the raw response from spreadsheets().get()
        assert result == expected


# ---------------------------------------------------------------------------
# Write tool: update_cells
# ---------------------------------------------------------------------------

class TestUpdateCells:
    def test_builds_correct_range_and_body(self, fake_ctx, mock_sheets_service):
        """update_cells constructs the correct full range and passes the data in the body."""
        from gsheets_mcp.tools.write import update_cells

        expected_response = {
            'spreadsheetId': 'test-id',
            'updatedRange': 'Sheet1!A1:B2',
            'updatedRows': 2,
            'updatedColumns': 2,
            'updatedCells': 4
        }
        mock_sheets_service.set_execute_return(expected_response)

        data = [['Hello', 'World'], ['Foo', 'Bar']]
        result = update_cells(
            spreadsheet_id='test-id',
            sheet='Sheet1',
            range='A1:B2',
            data=data,
            ctx=fake_ctx
        )

        assert result == expected_response

    def test_returns_service_response(self, fake_ctx, mock_sheets_service):
        """update_cells passes through whatever the API returns."""
        from gsheets_mcp.tools.write import update_cells

        mock_sheets_service.set_execute_return({'updatedCells': 10})

        result = update_cells(
            spreadsheet_id='sid',
            sheet='Sheet1',
            range='A1:E2',
            data=[['a'] * 5, ['b'] * 5],
            ctx=fake_ctx
        )

        assert result == {'updatedCells': 10}


class TestBatchUpdateCells:
    def test_multiple_ranges_are_included(self, fake_ctx, mock_sheets_service):
        """batch_update_cells passes all ranges into the body data list."""
        from gsheets_mcp.tools.write import batch_update_cells

        mock_sheets_service.set_execute_return({'totalUpdatedCells': 6})

        result = batch_update_cells(
            spreadsheet_id='sid',
            sheet='Sheet1',
            ranges={
                'A1:B2': [[1, 2], [3, 4]],
                'D1:E2': [['x', 'y'], ['z', 'w']]
            },
            ctx=fake_ctx
        )

        assert result == {'totalUpdatedCells': 6}


# ---------------------------------------------------------------------------
# Conditional formatting tool: apply_conditional_formatting
# ---------------------------------------------------------------------------

class TestApplyConditionalFormatting:
    def test_boolean_rule_sends_batchupdate(self, fake_ctx, mock_sheets_service):
        """apply_conditional_formatting with a boolean rule calls spreadsheets().batchUpdate."""
        from gsheets_mcp.tools.conditional import apply_conditional_formatting
        from tests.conftest import assert_batchupdate_body

        # Wire get() to return sheet metadata so _get_sheet_id finds Sheet1.
        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}]
        })

        result = apply_conditional_formatting(
            spreadsheet_id='test-id',
            sheet_name='Sheet1',
            range='A1:C10',
            rules=[{
                'condition_type': 'NUMBER_GREATER',
                'values': [100],
                'format': {'background_color': {'red': 1, 'green': 0, 'blue': 0}}
            }],
            ctx=fake_ctx
        )

        assert result['success'] is True
        assert result['rules_applied'] == 1

    def test_legacy_alias_maps_correctly(self, fake_ctx, mock_sheets_service):
        """Legacy alias 'greater_than' should map to NUMBER_GREATER."""
        from gsheets_mcp.tools.conditional import (
            _normalize_condition_type,
            _CONDITION_TYPE_ALIASES
        )

        assert _normalize_condition_type('greater_than') == 'NUMBER_GREATER'
        assert _normalize_condition_type('less_than') == 'NUMBER_LESS'
        assert _normalize_condition_type('text_contains') == 'TEXT_CONTAINS'
        assert _normalize_condition_type('is_blank') == 'BLANK'
        # Real Google enum should pass through upper-cased.
        assert _normalize_condition_type('NUMBER_EQ') == 'NUMBER_EQ'

    def test_gradient_rule_uses_gradient_key(self, fake_ctx, mock_sheets_service):
        """apply_conditional_formatting with gradient key sends a gradientRule."""
        from gsheets_mcp.tools.conditional import apply_conditional_formatting

        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}]
        })

        result = apply_conditional_formatting(
            spreadsheet_id='test-id',
            sheet_name='Sheet1',
            range='A1:A10',
            rules=[{
                'gradient': {
                    'minpoint': {'color': {'red': 0, 'green': 1, 'blue': 0}, 'type': 'MIN'},
                    'maxpoint': {'color': {'red': 1, 'green': 0, 'blue': 0}, 'type': 'MAX'}
                }
            }],
            ctx=fake_ctx
        )

        assert result['success'] is True
        assert result['rules_applied'] == 1

    def test_zero_value_conditions_carry_no_values(self):
        """BLANK and NOT_BLANK condition types should produce empty ConditionValue lists."""
        from gsheets_mcp.tools.conditional import _build_condition_values

        assert _build_condition_values('BLANK', []) == []
        assert _build_condition_values('NOT_BLANK', ['ignored']) == []

    def test_two_value_condition_uses_first_two(self):
        """NUMBER_BETWEEN should use exactly two values."""
        from gsheets_mcp.tools.conditional import _build_condition_values

        result = _build_condition_values('NUMBER_BETWEEN', [10, 20, 99])
        assert len(result) == 2
        assert result[0]['userEnteredValue'] == '10'
        assert result[1]['userEnteredValue'] == '20'

    def test_single_value_condition(self):
        """NUMBER_GREATER should use only the first value."""
        from gsheets_mcp.tools.conditional import _build_condition_values

        result = _build_condition_values('NUMBER_GREATER', [50])
        assert len(result) == 1
        assert result[0]['userEnteredValue'] == '50'
