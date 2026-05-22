"""
TDD tests for apply_dashboard_template tool.

Tests are written first (failing) before implementation.
"""

import json
import os
import pytest

import server  # noqa: F401 - triggers tool registration

from tests.conftest import assert_batchupdate_body


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_batchupdate_requests(mock_service):
    """Return the 'requests' list from the captured batchUpdate call."""
    kwargs = mock_service._last_call_kwargs.get('batchUpdate', {})
    body = kwargs.get('body', {})
    return body.get('requests', [])


def _has_request_type(requests, key):
    return any(key in r for r in requests)


# ---------------------------------------------------------------------------
# Spec-loading unit test
# ---------------------------------------------------------------------------

class TestSpecLoader:
    def test_kpi_overview_json_has_required_keys(self):
        """Loading kpi_overview.json returns a dict with expected top-level keys."""
        templates_dir = os.path.join(
            os.path.dirname(__file__), '..', 'gsheets_mcp', 'templates'
        )
        path = os.path.join(templates_dir, 'kpi_overview.json')
        with open(path) as f:
            spec = json.load(f)

        assert spec.get('name') == 'kpi_overview'
        assert 'description' in spec
        assert 'blocks' in spec
        assert isinstance(spec['blocks'], list)
        assert len(spec['blocks']) >= 1

    def test_sales_dashboard_json_has_required_keys(self):
        """Loading sales_dashboard.json returns a dict with expected top-level keys."""
        templates_dir = os.path.join(
            os.path.dirname(__file__), '..', 'gsheets_mcp', 'templates'
        )
        path = os.path.join(templates_dir, 'sales_dashboard.json')
        with open(path) as f:
            spec = json.load(f)

        assert spec.get('name') == 'sales_dashboard'
        assert 'description' in spec
        assert 'blocks' in spec
        assert isinstance(spec['blocks'], list)
        assert len(spec['blocks']) >= 1


# ---------------------------------------------------------------------------
# Unknown template returns error, no API call
# ---------------------------------------------------------------------------

class TestUnknownTemplate:
    def test_unknown_template_returns_error_dict(self, fake_ctx, mock_sheets_service):
        """apply_dashboard_template with unknown template_name returns error dict."""
        from gsheets_mcp.tools.dashboard import apply_dashboard_template

        result = apply_dashboard_template(
            spreadsheet_id='sid',
            sheet='Sheet1',
            template_name='does_not_exist',
            ctx=fake_ctx,
        )

        assert result['success'] is False
        assert 'does_not_exist' in result['message']

    def test_unknown_template_issues_no_batchupdate(self, fake_ctx, mock_sheets_service):
        """apply_dashboard_template with unknown template issues no batchUpdate call."""
        from gsheets_mcp.tools.dashboard import apply_dashboard_template

        apply_dashboard_template(
            spreadsheet_id='sid',
            sheet='Sheet1',
            template_name='no_such_template',
            ctx=fake_ctx,
        )

        # batchUpdate should not have been called
        kwargs = mock_sheets_service._last_call_kwargs.get('batchUpdate')
        assert kwargs is None, "batchUpdate must not be called for unknown templates"


# ---------------------------------------------------------------------------
# kpi_overview: single batchUpdate with expected request types
# ---------------------------------------------------------------------------

class TestKpiOverviewTemplate:
    @pytest.fixture(autouse=True)
    def _setup(self, mock_sheets_service):
        """Configure mock to return sheet metadata so _get_sheet_id resolves."""
        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}]
        })

    def test_issues_exactly_one_batchupdate(self, fake_ctx, mock_sheets_service):
        """apply_dashboard_template calls batchUpdate exactly once."""
        from gsheets_mcp.tools.dashboard import apply_dashboard_template

        result = apply_dashboard_template(
            spreadsheet_id='sid',
            sheet='Sheet1',
            template_name='kpi_overview',
            ctx=fake_ctx,
        )

        # batchUpdate must have been called
        kwargs = mock_sheets_service._last_call_kwargs.get('batchUpdate', {})
        assert kwargs, "batchUpdate was not called"
        assert result['success'] is True

    def test_requests_list_contains_merge_cells(self, fake_ctx, mock_sheets_service):
        """kpi_overview batchUpdate body includes mergeCells for title bar."""
        from gsheets_mcp.tools.dashboard import apply_dashboard_template

        apply_dashboard_template(
            spreadsheet_id='sid',
            sheet='Sheet1',
            template_name='kpi_overview',
            ctx=fake_ctx,
        )

        assert_batchupdate_body(mock_sheets_service, 'mergeCells')

    def test_requests_list_contains_repeat_cell(self, fake_ctx, mock_sheets_service):
        """kpi_overview batchUpdate body includes repeatCell (title/KPI card formatting)."""
        from gsheets_mcp.tools.dashboard import apply_dashboard_template

        apply_dashboard_template(
            spreadsheet_id='sid',
            sheet='Sheet1',
            template_name='kpi_overview',
            ctx=fake_ctx,
        )

        assert_batchupdate_body(mock_sheets_service, 'repeatCell')

    def test_requests_list_contains_add_banding(self, fake_ctx, mock_sheets_service):
        """kpi_overview batchUpdate body includes addBanding for the data table."""
        from gsheets_mcp.tools.dashboard import apply_dashboard_template

        apply_dashboard_template(
            spreadsheet_id='sid',
            sheet='Sheet1',
            template_name='kpi_overview',
            ctx=fake_ctx,
        )

        assert_batchupdate_body(mock_sheets_service, 'addBanding')

    def test_requests_list_contains_update_sheet_properties(self, fake_ctx, mock_sheets_service):
        """kpi_overview batchUpdate body includes updateSheetProperties (freeze)."""
        from gsheets_mcp.tools.dashboard import apply_dashboard_template

        apply_dashboard_template(
            spreadsheet_id='sid',
            sheet='Sheet1',
            template_name='kpi_overview',
            ctx=fake_ctx,
        )

        assert_batchupdate_body(mock_sheets_service, 'updateSheetProperties')

    def test_requests_list_contains_add_chart(self, fake_ctx, mock_sheets_service):
        """kpi_overview batchUpdate body includes addChart."""
        from gsheets_mcp.tools.dashboard import apply_dashboard_template

        apply_dashboard_template(
            spreadsheet_id='sid',
            sheet='Sheet1',
            template_name='kpi_overview',
            ctx=fake_ctx,
        )

        assert_batchupdate_body(mock_sheets_service, 'addChart')

    def test_requests_list_contains_conditional_format(self, fake_ctx, mock_sheets_service):
        """kpi_overview batchUpdate body includes addConditionalFormatRule."""
        from gsheets_mcp.tools.dashboard import apply_dashboard_template

        apply_dashboard_template(
            spreadsheet_id='sid',
            sheet='Sheet1',
            template_name='kpi_overview',
            ctx=fake_ctx,
        )

        assert_batchupdate_body(mock_sheets_service, 'addConditionalFormatRule')

    def test_return_value_structure(self, fake_ctx, mock_sheets_service):
        """apply_dashboard_template returns expected success dict."""
        from gsheets_mcp.tools.dashboard import apply_dashboard_template

        result = apply_dashboard_template(
            spreadsheet_id='sid',
            sheet='Sheet1',
            template_name='kpi_overview',
            ctx=fake_ctx,
        )

        assert result['success'] is True
        assert result['template'] == 'kpi_overview'
        assert result['sheet'] == 'Sheet1'
        assert 'blocks_applied' in result
        assert 'request_count' in result
        assert result['spreadsheetId'] == 'sid'
        assert result['request_count'] > 0

    def test_blocks_applied_lists_block_types(self, fake_ctx, mock_sheets_service):
        """blocks_applied in return value lists the block types processed."""
        from gsheets_mcp.tools.dashboard import apply_dashboard_template

        result = apply_dashboard_template(
            spreadsheet_id='sid',
            sheet='Sheet1',
            template_name='kpi_overview',
            ctx=fake_ctx,
        )

        applied = result['blocks_applied']
        assert 'title_bar' in applied
        assert 'banded_table' in applied
        assert 'freeze' in applied
        assert 'chart' in applied


# ---------------------------------------------------------------------------
# Title override flows into repeatCell string value
# ---------------------------------------------------------------------------

class TestTitleOverride:
    @pytest.fixture(autouse=True)
    def _setup(self, mock_sheets_service):
        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}]
        })

    def test_title_override_stored_in_result(self, fake_ctx, mock_sheets_service):
        """When title is provided, the return value reflects the custom title."""
        from gsheets_mcp.tools.dashboard import apply_dashboard_template

        result = apply_dashboard_template(
            spreadsheet_id='sid',
            sheet='Sheet1',
            template_name='kpi_overview',
            title='My Custom KPI Dashboard',
            ctx=fake_ctx,
        )

        assert result['success'] is True
        # title should appear somewhere in the result or be reflected in requests
        requests = _get_batchupdate_requests(mock_sheets_service)
        # The title bar repeatCell should have the custom title text
        repeat_cells = [r for r in requests if 'repeatCell' in r]
        cell_values = []
        for rc in repeat_cells:
            cell = rc['repeatCell'].get('cell', {})
            uef = cell.get('userEnteredFormat', {})
            # Also check userEnteredValue path if stored there
            uev = cell.get('userEnteredValue', {})
            cell_values.append(uev.get('stringValue', ''))

        # At least one repeatCell should carry the title string
        assert any('My Custom KPI Dashboard' in v for v in cell_values), (
            f"Custom title not found in repeatCell userEnteredValue. Cells: {cell_values}"
        )


# ---------------------------------------------------------------------------
# data_range flows into chart source range
# ---------------------------------------------------------------------------

class TestDataRangeFlowsToChart:
    @pytest.fixture(autouse=True)
    def _setup(self, mock_sheets_service):
        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}]
        })

    def test_data_range_arg_reflected_in_chart_source(self, fake_ctx, mock_sheets_service):
        """data_range argument flows into addChart sourceRange indices."""
        from gsheets_mcp.tools.dashboard import apply_dashboard_template

        # Provide an explicit data_range; expect the chart source to use those indices.
        # A7:F20 -> startRow=6, endRow=20, startCol=0, endCol=6 (0-based)
        result = apply_dashboard_template(
            spreadsheet_id='sid',
            sheet='Sheet1',
            template_name='kpi_overview',
            data_range='A7:F20',
            ctx=fake_ctx,
        )

        assert result['success'] is True
        requests = _get_batchupdate_requests(mock_sheets_service)
        chart_requests = [r for r in requests if 'addChart' in r]
        assert chart_requests, "No addChart request found"

        # Dig into the first chart's domain sourceRange
        chart = chart_requests[0]['addChart']['chart']
        domains = chart['spec']['basicChart']['domains']
        sources = domains[0]['domain']['sourceRange']['sources']
        assert sources[0]['startRowIndex'] == 6   # A7 -> row index 6
        assert sources[0]['endRowIndex'] == 20     # F20 -> end row 20 exclusive


# ---------------------------------------------------------------------------
# sales_dashboard template registers correctly
# ---------------------------------------------------------------------------

class TestSalesDashboardTemplate:
    @pytest.fixture(autouse=True)
    def _setup(self, mock_sheets_service):
        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}]
        })

    def test_sales_dashboard_succeeds(self, fake_ctx, mock_sheets_service):
        """apply_dashboard_template with sales_dashboard returns success."""
        from gsheets_mcp.tools.dashboard import apply_dashboard_template

        result = apply_dashboard_template(
            spreadsheet_id='sid',
            sheet='Sheet1',
            template_name='sales_dashboard',
            ctx=fake_ctx,
        )

        assert result['success'] is True
        assert result['template'] == 'sales_dashboard'

    def test_sales_dashboard_has_charts(self, fake_ctx, mock_sheets_service):
        """sales_dashboard batchUpdate includes at least one addChart."""
        from gsheets_mcp.tools.dashboard import apply_dashboard_template

        apply_dashboard_template(
            spreadsheet_id='sid',
            sheet='Sheet1',
            template_name='sales_dashboard',
            ctx=fake_ctx,
        )

        assert_batchupdate_body(mock_sheets_service, 'addChart')


# ---------------------------------------------------------------------------
# kpi_card split-mode: label_range + value_range + value_formula
# ---------------------------------------------------------------------------

class TestKpiCardSplitMode:
    """Tests for kpi_card blocks that include value_range and value_formula."""

    @pytest.fixture(autouse=True)
    def _setup(self, mock_sheets_service):
        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}]
        })

    def _run_minimal_split_template(self, fake_ctx, mock_sheets_service):
        """Apply a minimal in-memory template with one split-mode kpi_card."""
        import unittest.mock as mock
        from gsheets_mcp.tools import dashboard as dash_module

        fake_spec = {
            'name': 'test_split',
            'description': 'Test split kpi',
            'blocks': [
                {
                    'type': 'kpi_card',
                    'range': 'A3:B5',
                    'label': 'Total Revenue',
                    'label_range': 'A3:B3',
                    'value_range': 'A4:B5',
                    'value_formula': '=SUM(B8:B19)',
                    'background_color': {'red': 0.18, 'green': 0.52, 'blue': 0.73},
                    'text_format': {
                        'bold': True,
                        'foreground_color': {'red': 1.0, 'green': 1.0, 'blue': 1.0},
                    },
                }
            ],
        }

        with mock.patch.object(dash_module, '_load_template', return_value=fake_spec):
            from gsheets_mcp.tools.dashboard import apply_dashboard_template
            result = apply_dashboard_template(
                spreadsheet_id='sid',
                sheet='Sheet1',
                template_name='test_split',
                ctx=fake_ctx,
            )
        return result

    def test_split_mode_emits_formula_value_in_repeat_cell(self, fake_ctx, mock_sheets_service):
        """Split kpi_card emits a repeatCell whose cell has formulaValue equal to the formula."""
        self._run_minimal_split_template(fake_ctx, mock_sheets_service)

        kwargs = mock_sheets_service._last_call_kwargs.get('batchUpdate', {})
        requests = kwargs.get('body', {}).get('requests', [])
        repeat_cells = [r['repeatCell'] for r in requests if 'repeatCell' in r]

        formula_values = [
            rc['cell']['userEnteredValue'].get('formulaValue')
            for rc in repeat_cells
            if 'userEnteredValue' in rc.get('cell', {})
        ]
        assert '=SUM(B8:B19)' in formula_values, (
            f"Expected formulaValue '=SUM(B8:B19)' in repeatCell cells. Got: {formula_values}"
        )

    def test_split_mode_fields_mask_contains_user_entered_value(self, fake_ctx, mock_sheets_service):
        """Split kpi_card value repeatCell has 'userEnteredValue' in its fields mask."""
        self._run_minimal_split_template(fake_ctx, mock_sheets_service)

        kwargs = mock_sheets_service._last_call_kwargs.get('batchUpdate', {})
        requests = kwargs.get('body', {}).get('requests', [])
        repeat_cells = [r['repeatCell'] for r in requests if 'repeatCell' in r]

        # Find the repeatCell that contains the formula
        formula_rcs = [
            rc for rc in repeat_cells
            if rc.get('cell', {}).get('userEnteredValue', {}).get('formulaValue') == '=SUM(B8:B19)'
        ]
        assert formula_rcs, "No repeatCell with formulaValue found"
        fields = formula_rcs[0].get('fields', '')
        assert 'userEnteredValue' in fields, (
            f"'userEnteredValue' not in fields mask: {fields}"
        )

    def test_split_mode_emits_two_merge_cells(self, fake_ctx, mock_sheets_service):
        """Split kpi_card emits exactly two mergeCells requests (label_range and value_range)."""
        self._run_minimal_split_template(fake_ctx, mock_sheets_service)

        kwargs = mock_sheets_service._last_call_kwargs.get('batchUpdate', {})
        requests = kwargs.get('body', {}).get('requests', [])
        merges = [r['mergeCells'] for r in requests if 'mergeCells' in r]

        assert len(merges) == 2, (
            f"Expected 2 mergeCells requests for split kpi_card, got {len(merges)}: {merges}"
        )

    def test_split_mode_merge_ranges_match_label_and_value_ranges(self, fake_ctx, mock_sheets_service):
        """Split kpi_card merge ranges correspond to label_range A3:B3 and value_range A4:B5."""
        self._run_minimal_split_template(fake_ctx, mock_sheets_service)

        kwargs = mock_sheets_service._last_call_kwargs.get('batchUpdate', {})
        requests = kwargs.get('body', {}).get('requests', [])
        merges = [r['mergeCells']['range'] for r in requests if 'mergeCells' in r]

        # A3:B3 -> startRow=2, endRow=3, startCol=0, endCol=2
        label_range = {'sheetId': 0, 'startRowIndex': 2, 'endRowIndex': 3, 'startColumnIndex': 0, 'endColumnIndex': 2}
        # A4:B5 -> startRow=3, endRow=5, startCol=0, endCol=2
        value_range = {'sheetId': 0, 'startRowIndex': 3, 'endRowIndex': 5, 'startColumnIndex': 0, 'endColumnIndex': 2}

        assert label_range in merges, f"label_range merge not found in {merges}"
        assert value_range in merges, f"value_range merge not found in {merges}"

    def test_split_mode_number_format_flows_into_repeat_cell(self, fake_ctx, mock_sheets_service):
        """value_number_format dict flows into userEnteredFormat.numberFormat of value repeatCell."""
        import unittest.mock as mock
        from gsheets_mcp.tools import dashboard as dash_module

        fake_spec = {
            'name': 'test_split_nf',
            'description': 'Test number format',
            'blocks': [
                {
                    'type': 'kpi_card',
                    'range': 'A3:B5',
                    'label': 'Total Revenue',
                    'label_range': 'A3:B3',
                    'value_range': 'A4:B5',
                    'value_formula': '=SUM(B8:B19)',
                    'value_number_format': {'type': 'CURRENCY', 'pattern': '$#,##0'},
                    'background_color': {'red': 0.18, 'green': 0.52, 'blue': 0.73},
                }
            ],
        }

        with mock.patch.object(dash_module, '_load_template', return_value=fake_spec):
            from gsheets_mcp.tools.dashboard import apply_dashboard_template
            apply_dashboard_template(
                spreadsheet_id='sid',
                sheet='Sheet1',
                template_name='test_split_nf',
                ctx=fake_ctx,
            )

        kwargs = mock_sheets_service._last_call_kwargs.get('batchUpdate', {})
        requests = kwargs.get('body', {}).get('requests', [])
        repeat_cells = [r['repeatCell'] for r in requests if 'repeatCell' in r]

        formula_rcs = [
            rc for rc in repeat_cells
            if rc.get('cell', {}).get('userEnteredValue', {}).get('formulaValue') == '=SUM(B8:B19)'
        ]
        assert formula_rcs, "No formula repeatCell found"
        cell_fmt = formula_rcs[0].get('cell', {}).get('userEnteredFormat', {})
        assert 'numberFormat' in cell_fmt, f"numberFormat missing from cell format: {cell_fmt}"
        assert cell_fmt['numberFormat']['type'] == 'CURRENCY'
        assert cell_fmt['numberFormat']['pattern'] == '$#,##0'

        fields = formula_rcs[0].get('fields', '')
        assert 'numberFormat' in fields, f"numberFormat not in fields mask: {fields}"


# ---------------------------------------------------------------------------
# kpi_card legacy mode: backward compatibility
# ---------------------------------------------------------------------------

class TestKpiCardLegacyMode:
    """Verify that label-only kpi_card blocks still work exactly as before."""

    @pytest.fixture(autouse=True)
    def _setup(self, mock_sheets_service):
        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}]
        })

    def test_legacy_kpi_card_emits_one_merge_one_repeat_cell(self, fake_ctx, mock_sheets_service):
        """A label-only kpi_card emits exactly one mergeCells and one repeatCell."""
        import unittest.mock as mock
        from gsheets_mcp.tools import dashboard as dash_module

        fake_spec = {
            'name': 'test_legacy',
            'description': 'Test legacy kpi card',
            'blocks': [
                {
                    'type': 'kpi_card',
                    'range': 'A3:B5',
                    'label': 'My Label',
                    'background_color': {'red': 0.18, 'green': 0.52, 'blue': 0.73},
                }
            ],
        }

        with mock.patch.object(dash_module, '_load_template', return_value=fake_spec):
            from gsheets_mcp.tools.dashboard import apply_dashboard_template
            apply_dashboard_template(
                spreadsheet_id='sid',
                sheet='Sheet1',
                template_name='test_legacy',
                ctx=fake_ctx,
            )

        kwargs = mock_sheets_service._last_call_kwargs.get('batchUpdate', {})
        requests = kwargs.get('body', {}).get('requests', [])
        merges = [r for r in requests if 'mergeCells' in r]
        repeat_cells = [r for r in requests if 'repeatCell' in r]

        assert len(merges) == 1, f"Expected 1 merge for legacy kpi_card, got {len(merges)}"
        assert len(repeat_cells) == 1, f"Expected 1 repeatCell for legacy kpi_card, got {len(repeat_cells)}"

    def test_legacy_kpi_card_has_string_value_no_formula(self, fake_ctx, mock_sheets_service):
        """A label-only kpi_card repeatCell has stringValue and no formulaValue."""
        import unittest.mock as mock
        from gsheets_mcp.tools import dashboard as dash_module

        fake_spec = {
            'name': 'test_legacy2',
            'description': 'Test legacy kpi card no formula',
            'blocks': [
                {
                    'type': 'kpi_card',
                    'range': 'A3:B5',
                    'label': 'My Label',
                }
            ],
        }

        with mock.patch.object(dash_module, '_load_template', return_value=fake_spec):
            from gsheets_mcp.tools.dashboard import apply_dashboard_template
            apply_dashboard_template(
                spreadsheet_id='sid',
                sheet='Sheet1',
                template_name='test_legacy2',
                ctx=fake_ctx,
            )

        kwargs = mock_sheets_service._last_call_kwargs.get('batchUpdate', {})
        requests = kwargs.get('body', {}).get('requests', [])
        repeat_cells = [r['repeatCell'] for r in requests if 'repeatCell' in r]

        assert repeat_cells, "No repeatCell found"
        uev = repeat_cells[0].get('cell', {}).get('userEnteredValue', {})
        assert 'stringValue' in uev, f"stringValue not in userEnteredValue: {uev}"
        assert 'formulaValue' not in uev, f"formulaValue must not appear in legacy mode: {uev}"
        assert uev['stringValue'] == 'My Label'
