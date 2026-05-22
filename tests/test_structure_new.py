"""
TDD tests for new structure tools: insert_rows, insert_columns,
delete_columns, freeze_dimensions, set_dimension_size,
group_dimensions, ungroup_dimensions, sort_range.

Each test asserts the exact batchUpdate request body built by the tool.
"""

import pytest

import server  # noqa: F401 - ensures all tools are registered
from tests.conftest import assert_batchupdate_body


# ---------------------------------------------------------------------------
# insert_rows
# ---------------------------------------------------------------------------

class TestInsertRows:
    def test_insert_rows_dimension_and_indices(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import insert_rows

        result = insert_rows(
            spreadsheet_id='sid',
            sheet='Sheet1',
            start_index=3,
            count=2,
            inherit_from_before=True,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'insertDimension')
        req = matched[0]['insertDimension']
        assert req['range']['dimension'] == 'ROWS'
        assert req['range']['startIndex'] == 3
        assert req['range']['endIndex'] == 5
        assert req['inheritFromBefore'] is True

    def test_insert_rows_inherit_false(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import insert_rows

        insert_rows(
            spreadsheet_id='sid',
            sheet='Sheet1',
            start_index=0,
            count=1,
            inherit_from_before=False,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'insertDimension')
        req = matched[0]['insertDimension']
        assert req['inheritFromBefore'] is False

    def test_insert_rows_unknown_sheet_returns_error(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import insert_rows

        result = insert_rows(
            spreadsheet_id='sid',
            sheet='NoSuchSheet',
            start_index=0,
            count=1,
            ctx=fake_ctx,
        )

        assert 'error' in result or result.get('success') is False


# ---------------------------------------------------------------------------
# insert_columns
# ---------------------------------------------------------------------------

class TestInsertColumns:
    def test_insert_columns_dimension_and_indices(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import insert_columns

        insert_columns(
            spreadsheet_id='sid',
            sheet='Sheet1',
            start_index=1,
            count=3,
            inherit_from_before=True,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'insertDimension')
        req = matched[0]['insertDimension']
        assert req['range']['dimension'] == 'COLUMNS'
        assert req['range']['startIndex'] == 1
        assert req['range']['endIndex'] == 4
        assert req['inheritFromBefore'] is True

    def test_insert_columns_default_inherit(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import insert_columns

        insert_columns(
            spreadsheet_id='sid',
            sheet='Sheet1',
            start_index=5,
            count=1,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'insertDimension')
        req = matched[0]['insertDimension']
        # Default inherit_from_before is True
        assert req['inheritFromBefore'] is True


# ---------------------------------------------------------------------------
# delete_columns
# ---------------------------------------------------------------------------

class TestDeleteColumns:
    def test_delete_columns_dimension_and_indices(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import delete_columns

        result = delete_columns(
            spreadsheet_id='sid',
            sheet='Sheet1',
            start_index=2,
            end_index=5,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'deleteDimension')
        req = matched[0]['deleteDimension']
        assert req['range']['dimension'] == 'COLUMNS'
        assert req['range']['startIndex'] == 2
        assert req['range']['endIndex'] == 5

    def test_delete_columns_returns_success(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import delete_columns

        result = delete_columns(
            spreadsheet_id='sid',
            sheet='Sheet1',
            start_index=0,
            end_index=1,
            ctx=fake_ctx,
        )

        assert result.get('success') is True


# ---------------------------------------------------------------------------
# freeze_dimensions
# ---------------------------------------------------------------------------

class TestFreezeDimensions:
    def test_freeze_rows_only(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import freeze_dimensions

        freeze_dimensions(
            spreadsheet_id='sid',
            sheet='Sheet1',
            frozen_rows=2,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'updateSheetProperties')
        req = matched[0]['updateSheetProperties']
        assert 'frozenRowCount' in req['properties']['gridProperties']
        assert req['properties']['gridProperties']['frozenRowCount'] == 2
        assert 'frozenRowCount' in req['fields']

    def test_freeze_columns_only(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import freeze_dimensions

        freeze_dimensions(
            spreadsheet_id='sid',
            sheet='Sheet1',
            frozen_columns=3,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'updateSheetProperties')
        req = matched[0]['updateSheetProperties']
        assert 'frozenColumnCount' in req['properties']['gridProperties']
        assert req['properties']['gridProperties']['frozenColumnCount'] == 3
        assert 'frozenColumnCount' in req['fields']

    def test_freeze_both(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import freeze_dimensions

        freeze_dimensions(
            spreadsheet_id='sid',
            sheet='Sheet1',
            frozen_rows=1,
            frozen_columns=2,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'updateSheetProperties')
        req = matched[0]['updateSheetProperties']
        gp = req['properties']['gridProperties']
        assert gp['frozenRowCount'] == 1
        assert gp['frozenColumnCount'] == 2
        assert 'frozenRowCount' in req['fields']
        assert 'frozenColumnCount' in req['fields']

    def test_freeze_neither_returns_error(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import freeze_dimensions

        result = freeze_dimensions(
            spreadsheet_id='sid',
            sheet='Sheet1',
            ctx=fake_ctx,
        )

        assert 'error' in result or result.get('success') is False


# ---------------------------------------------------------------------------
# set_dimension_size
# ---------------------------------------------------------------------------

class TestSetDimensionSize:
    def test_set_column_pixel_size(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import set_dimension_size

        set_dimension_size(
            spreadsheet_id='sid',
            sheet='Sheet1',
            dimension='COLUMNS',
            start_index=0,
            end_index=3,
            pixel_size=150,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'updateDimensionProperties')
        req = matched[0]['updateDimensionProperties']
        assert req['range']['dimension'] == 'COLUMNS'
        assert req['range']['startIndex'] == 0
        assert req['range']['endIndex'] == 3
        assert req['properties']['pixelSize'] == 150
        assert 'pixelSize' in req['fields']

    def test_set_row_pixel_size(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import set_dimension_size

        set_dimension_size(
            spreadsheet_id='sid',
            sheet='Sheet1',
            dimension='ROWS',
            start_index=1,
            end_index=5,
            pixel_size=30,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'updateDimensionProperties')
        req = matched[0]['updateDimensionProperties']
        assert req['range']['dimension'] == 'ROWS'
        assert req['properties']['pixelSize'] == 30


# ---------------------------------------------------------------------------
# group_dimensions
# ---------------------------------------------------------------------------

class TestGroupDimensions:
    def test_group_rows(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import group_dimensions

        group_dimensions(
            spreadsheet_id='sid',
            sheet='Sheet1',
            dimension='ROWS',
            start_index=2,
            end_index=6,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'addDimensionGroup')
        req = matched[0]['addDimensionGroup']
        assert req['range']['dimension'] == 'ROWS'
        assert req['range']['startIndex'] == 2
        assert req['range']['endIndex'] == 6

    def test_group_columns(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import group_dimensions

        group_dimensions(
            spreadsheet_id='sid',
            sheet='Sheet1',
            dimension='COLUMNS',
            start_index=0,
            end_index=4,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'addDimensionGroup')
        req = matched[0]['addDimensionGroup']
        assert req['range']['dimension'] == 'COLUMNS'


# ---------------------------------------------------------------------------
# ungroup_dimensions
# ---------------------------------------------------------------------------

class TestUngroupDimensions:
    def test_ungroup_rows(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import ungroup_dimensions

        ungroup_dimensions(
            spreadsheet_id='sid',
            sheet='Sheet1',
            dimension='ROWS',
            start_index=2,
            end_index=6,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'deleteDimensionGroup')
        req = matched[0]['deleteDimensionGroup']
        assert req['range']['dimension'] == 'ROWS'
        assert req['range']['startIndex'] == 2
        assert req['range']['endIndex'] == 6

    def test_ungroup_columns(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import ungroup_dimensions

        ungroup_dimensions(
            spreadsheet_id='sid',
            sheet='Sheet1',
            dimension='COLUMNS',
            start_index=1,
            end_index=3,
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'deleteDimensionGroup')
        req = matched[0]['deleteDimensionGroup']
        assert req['range']['dimension'] == 'COLUMNS'


# ---------------------------------------------------------------------------
# sort_range
# ---------------------------------------------------------------------------

class TestSortRange:
    def test_sort_range_single_spec(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import sort_range

        sort_range(
            spreadsheet_id='sid',
            sheet='Sheet1',
            range='A1:D10',
            sort_specs=[{'dimension_index': 0, 'sort_order': 'ASCENDING'}],
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'sortRange')
        req = matched[0]['sortRange']
        assert 'range' in req
        assert len(req['sortSpecs']) == 1
        assert req['sortSpecs'][0]['dimensionIndex'] == 0
        assert req['sortSpecs'][0]['sortOrder'] == 'ASCENDING'

    def test_sort_range_multiple_specs(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import sort_range

        sort_range(
            spreadsheet_id='sid',
            sheet='Sheet1',
            range='B2:E20',
            sort_specs=[
                {'dimension_index': 1, 'sort_order': 'DESCENDING'},
                {'dimension_index': 0, 'sort_order': 'ASCENDING'},
            ],
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'sortRange')
        req = matched[0]['sortRange']
        assert len(req['sortSpecs']) == 2
        assert req['sortSpecs'][0]['sortOrder'] == 'DESCENDING'
        assert req['sortSpecs'][1]['dimensionIndex'] == 0

    def test_sort_range_uses_sheet_id_in_grid_range(self, fake_ctx, mock_sheets_service):
        from gsheets_mcp.tools.structure import sort_range

        sort_range(
            spreadsheet_id='sid',
            sheet='Sheet1',
            range='A1:A5',
            sort_specs=[{'dimension_index': 0, 'sort_order': 'ASCENDING'}],
            ctx=fake_ctx,
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'sortRange')
        req = matched[0]['sortRange']
        # sheetId=0 comes from the mock's execute_return
        assert req['range']['sheetId'] == 0
