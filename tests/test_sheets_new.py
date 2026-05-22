"""
TDD tests for new tools added to gsheets_mcp/tools/sheets.py:
  - duplicate_sheet
  - set_sheet_visibility
  - reorder_sheet
  - move_spreadsheet_to_folder
  - trash_spreadsheet
"""

import pytest

# Ensure all tools are registered before tests run.
import server  # noqa: F401

from tests.conftest import assert_batchupdate_body


# ---------------------------------------------------------------------------
# duplicate_sheet
# ---------------------------------------------------------------------------

class TestDuplicateSheet:
    def test_sends_duplicateSheet_request(self, fake_ctx, mock_sheets_service):
        """duplicate_sheet calls batchUpdate with a duplicateSheet request."""
        from gsheets_mcp.tools.sheets import duplicate_sheet

        # Mock: spreadsheets().get() returns sheet metadata so _get_sheet_id resolves.
        # Mock: batchUpdate returns a reply with the new sheet properties.
        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}],
            'replies': [{'duplicateSheet': {'properties': {'sheetId': 99, 'title': 'Sheet1 Copy', 'index': 1}}}]
        })

        result = duplicate_sheet(
            spreadsheet_id='sid',
            source_sheet='Sheet1',
            new_sheet_name='Sheet1 Copy',
            ctx=fake_ctx
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'duplicateSheet')
        req = matched[0]['duplicateSheet']
        assert req['sourceSheetId'] == 0
        assert req['newSheetName'] == 'Sheet1 Copy'

    def test_insert_index_is_forwarded(self, fake_ctx, mock_sheets_service):
        """duplicate_sheet passes insert_index into the request when provided."""
        from gsheets_mcp.tools.sheets import duplicate_sheet

        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}],
            'replies': [{'duplicateSheet': {'properties': {'sheetId': 99, 'title': 'Copy', 'index': 2}}}]
        })

        duplicate_sheet(
            spreadsheet_id='sid',
            source_sheet='Sheet1',
            new_sheet_name='Copy',
            insert_index=2,
            ctx=fake_ctx
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'duplicateSheet')
        req = matched[0]['duplicateSheet']
        assert req.get('insertSheetIndex') == 2

    def test_returns_new_sheet_properties(self, fake_ctx, mock_sheets_service):
        """duplicate_sheet returns sheetId, title, and index of the new sheet."""
        from gsheets_mcp.tools.sheets import duplicate_sheet

        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Data', 'sheetId': 5}}],
            'replies': [{'duplicateSheet': {'properties': {'sheetId': 77, 'title': 'Data Copy', 'index': 1}}}]
        })

        result = duplicate_sheet(
            spreadsheet_id='sid',
            source_sheet='Data',
            new_sheet_name='Data Copy',
            ctx=fake_ctx
        )

        assert result['sheetId'] == 77
        assert result['title'] == 'Data Copy'
        assert result['spreadsheetId'] == 'sid'

    def test_sheet_not_found_returns_error(self, fake_ctx, mock_sheets_service):
        """duplicate_sheet returns an error dict when the source sheet does not exist."""
        from gsheets_mcp.tools.sheets import duplicate_sheet

        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Other', 'sheetId': 1}}]
        })

        result = duplicate_sheet(
            spreadsheet_id='sid',
            source_sheet='Missing',
            new_sheet_name='Copy',
            ctx=fake_ctx
        )

        assert 'error' in result


# ---------------------------------------------------------------------------
# set_sheet_visibility
# ---------------------------------------------------------------------------

class TestSetSheetVisibility:
    def test_sends_updateSheetProperties_hidden_true(self, fake_ctx, mock_sheets_service):
        """set_sheet_visibility sends updateSheetProperties with hidden=True and fields mask."""
        from gsheets_mcp.tools.sheets import set_sheet_visibility

        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}]
        })

        set_sheet_visibility(
            spreadsheet_id='sid',
            sheet='Sheet1',
            hidden=True,
            ctx=fake_ctx
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'updateSheetProperties')
        req = matched[0]['updateSheetProperties']
        assert req['properties']['hidden'] is True
        assert req['properties']['sheetId'] == 0
        assert 'hidden' in req['fields']

    def test_sends_updateSheetProperties_hidden_false(self, fake_ctx, mock_sheets_service):
        """set_sheet_visibility sends updateSheetProperties with hidden=False."""
        from gsheets_mcp.tools.sheets import set_sheet_visibility

        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}]
        })

        set_sheet_visibility(
            spreadsheet_id='sid',
            sheet='Sheet1',
            hidden=False,
            ctx=fake_ctx
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'updateSheetProperties')
        req = matched[0]['updateSheetProperties']
        assert req['properties']['hidden'] is False

    def test_returns_spreadsheet_id_and_sheet(self, fake_ctx, mock_sheets_service):
        """set_sheet_visibility returns spreadsheetId, sheet name, and hidden state."""
        from gsheets_mcp.tools.sheets import set_sheet_visibility

        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}]
        })

        result = set_sheet_visibility(
            spreadsheet_id='sid',
            sheet='Sheet1',
            hidden=True,
            ctx=fake_ctx
        )

        assert result['spreadsheetId'] == 'sid'
        assert result['sheet'] == 'Sheet1'
        assert result['hidden'] is True

    def test_sheet_not_found_returns_error(self, fake_ctx, mock_sheets_service):
        """set_sheet_visibility returns error dict when sheet name is not found."""
        from gsheets_mcp.tools.sheets import set_sheet_visibility

        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Other', 'sheetId': 1}}]
        })

        result = set_sheet_visibility(
            spreadsheet_id='sid',
            sheet='NoSuchSheet',
            hidden=True,
            ctx=fake_ctx
        )

        assert 'error' in result


# ---------------------------------------------------------------------------
# reorder_sheet
# ---------------------------------------------------------------------------

class TestReorderSheet:
    def test_sends_updateSheetProperties_index(self, fake_ctx, mock_sheets_service):
        """reorder_sheet sends updateSheetProperties with index and correct fields mask."""
        from gsheets_mcp.tools.sheets import reorder_sheet

        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}]
        })

        reorder_sheet(
            spreadsheet_id='sid',
            sheet='Sheet1',
            new_index=3,
            ctx=fake_ctx
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'updateSheetProperties')
        req = matched[0]['updateSheetProperties']
        assert req['properties']['index'] == 3
        assert req['properties']['sheetId'] == 0
        assert 'index' in req['fields']

    def test_index_zero_is_valid(self, fake_ctx, mock_sheets_service):
        """reorder_sheet accepts 0 as a valid new_index (first position)."""
        from gsheets_mcp.tools.sheets import reorder_sheet

        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}]
        })

        reorder_sheet(
            spreadsheet_id='sid',
            sheet='Sheet1',
            new_index=0,
            ctx=fake_ctx
        )

        matched = assert_batchupdate_body(mock_sheets_service, 'updateSheetProperties')
        req = matched[0]['updateSheetProperties']
        assert req['properties']['index'] == 0

    def test_returns_spreadsheet_id_and_new_index(self, fake_ctx, mock_sheets_service):
        """reorder_sheet returns spreadsheetId, sheet name, and new_index."""
        from gsheets_mcp.tools.sheets import reorder_sheet

        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}]
        })

        result = reorder_sheet(
            spreadsheet_id='sid',
            sheet='Sheet1',
            new_index=2,
            ctx=fake_ctx
        )

        assert result['spreadsheetId'] == 'sid'
        assert result['sheet'] == 'Sheet1'
        assert result['new_index'] == 2

    def test_sheet_not_found_returns_error(self, fake_ctx, mock_sheets_service):
        """reorder_sheet returns error dict when sheet is not found."""
        from gsheets_mcp.tools.sheets import reorder_sheet

        mock_sheets_service.set_execute_return({
            'sheets': [{'properties': {'title': 'Other', 'sheetId': 1}}]
        })

        result = reorder_sheet(
            spreadsheet_id='sid',
            sheet='Ghost',
            new_index=0,
            ctx=fake_ctx
        )

        assert 'error' in result


# ---------------------------------------------------------------------------
# move_spreadsheet_to_folder
# ---------------------------------------------------------------------------

class TestMoveSpreadsheetToFolder:
    def test_calls_files_update_with_addParents(self, fake_ctx, mock_drive_service):
        """move_spreadsheet_to_folder calls drive files().update() with addParents."""
        from gsheets_mcp.tools.sheets import move_spreadsheet_to_folder

        mock_drive_service.set_execute_return({
            'id': 'file-id',
            'name': 'My Sheet',
            'parents': ['new-folder-id']
        })

        move_spreadsheet_to_folder(
            spreadsheet_id='file-id',
            target_folder_id='new-folder-id',
            ctx=fake_ctx
        )

        kwargs = mock_drive_service._last_call_kwargs.get('update', {})
        assert kwargs.get('addParents') == 'new-folder-id'

    def test_remove_from_current_default_true(self, fake_ctx, mock_drive_service, mock_sheets_service):
        """move_spreadsheet_to_folder fetches current parents and removes them by default."""
        from gsheets_mcp.tools.sheets import move_spreadsheet_to_folder

        # First execute() call is files().get() to fetch current parents.
        # Second execute() call is files().update().
        # _ChainableMock returns the same value for all execute() calls,
        # so we set a value that works for both: include 'parents' and 'id'.
        mock_drive_service.set_execute_return({
            'id': 'file-id',
            'name': 'My Sheet',
            'parents': ['old-folder-id'],
        })

        move_spreadsheet_to_folder(
            spreadsheet_id='file-id',
            target_folder_id='new-folder-id',
            remove_from_current=True,
            ctx=fake_ctx
        )

        kwargs = mock_drive_service._last_call_kwargs.get('update', {})
        assert kwargs.get('addParents') == 'new-folder-id'
        # When removing current parents, removeParents should be set.
        assert kwargs.get('removeParents') is not None

    def test_remove_from_current_false_skips_removeParents(self, fake_ctx, mock_drive_service):
        """move_spreadsheet_to_folder does not set removeParents when remove_from_current=False."""
        from gsheets_mcp.tools.sheets import move_spreadsheet_to_folder

        mock_drive_service.set_execute_return({
            'id': 'file-id',
            'name': 'My Sheet',
            'parents': ['old-folder-id'],
        })

        move_spreadsheet_to_folder(
            spreadsheet_id='file-id',
            target_folder_id='new-folder-id',
            remove_from_current=False,
            ctx=fake_ctx
        )

        kwargs = mock_drive_service._last_call_kwargs.get('update', {})
        # removeParents should be absent or empty when remove_from_current=False.
        assert not kwargs.get('removeParents')

    def test_returns_spreadsheet_id_and_folder(self, fake_ctx, mock_drive_service):
        """move_spreadsheet_to_folder returns spreadsheetId and target_folder_id."""
        from gsheets_mcp.tools.sheets import move_spreadsheet_to_folder

        mock_drive_service.set_execute_return({
            'id': 'file-id',
            'name': 'My Sheet',
            'parents': ['new-folder-id'],
        })

        result = move_spreadsheet_to_folder(
            spreadsheet_id='file-id',
            target_folder_id='new-folder-id',
            ctx=fake_ctx
        )

        assert result['spreadsheetId'] == 'file-id'
        assert result['target_folder_id'] == 'new-folder-id'


# ---------------------------------------------------------------------------
# trash_spreadsheet
# ---------------------------------------------------------------------------

class TestTrashSpreadsheet:
    def test_calls_files_update_with_trashed_true(self, fake_ctx, mock_drive_service):
        """trash_spreadsheet calls drive files().update() with body trashed=True."""
        from gsheets_mcp.tools.sheets import trash_spreadsheet

        mock_drive_service.set_execute_return({
            'id': 'file-id',
            'name': 'Doomed Sheet',
            'trashed': True,
        })

        trash_spreadsheet(spreadsheet_id='file-id', ctx=fake_ctx)

        kwargs = mock_drive_service._last_call_kwargs.get('update', {})
        assert kwargs.get('fileId') == 'file-id'
        body = kwargs.get('body', {})
        assert body.get('trashed') is True

    def test_returns_spreadsheet_id_and_trashed_flag(self, fake_ctx, mock_drive_service):
        """trash_spreadsheet returns spreadsheetId and trashed=True."""
        from gsheets_mcp.tools.sheets import trash_spreadsheet

        mock_drive_service.set_execute_return({
            'id': 'file-id',
            'name': 'Doomed Sheet',
            'trashed': True,
        })

        result = trash_spreadsheet(spreadsheet_id='file-id', ctx=fake_ctx)

        assert result['spreadsheetId'] == 'file-id'
        assert result['trashed'] is True

    def test_docstring_mentions_recoverable(self):
        """trash_spreadsheet docstring must state this is recoverable (not permanent deletion)."""
        from gsheets_mcp.tools.sheets import trash_spreadsheet

        doc = trash_spreadsheet.__doc__ or ''
        # Must contain some indication the action is recoverable.
        assert any(word in doc.lower() for word in ('recover', 'trash', 'reversible', 'not permanent', 'not permanently'))
