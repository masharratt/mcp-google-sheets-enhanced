"""
Write tools: update cell values in Google Spreadsheets.
"""

from typing import List, Dict, Any, Optional

from mcp.server.fastmcp import Context

from gsheets_mcp.core import mcp, _get_sheet_id


@mcp.tool()
def update_cells(spreadsheet_id: str,
                sheet: str,
                range: str,
                data: List[List[Any]],
                ctx: Context = None) -> Dict[str, Any]:
    """
    Write values to cell range (USER_ENTERED mode, parses formulas/dates).

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet: Sheet name
        range: A1 range (e.g. 'A1:C10')
        data: 2D array of values
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    # Construct the range
    full_range = f"{sheet}!{range}"

    # Prepare the value range object
    value_range_body = {
        'values': data
    }

    # Call the Sheets API to update values
    result = sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=full_range,
        valueInputOption='USER_ENTERED',
        body=value_range_body
    ).execute()

    return result


@mcp.tool()
def batch_update_cells(spreadsheet_id: str,
                       sheet: str,
                       ranges: Dict[str, List[List[Any]]],
                       ctx: Context = None) -> Dict[str, Any]:
    """
    Write values to multiple ranges in one batchUpdate call (USER_ENTERED mode).

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet: Sheet name
        ranges: Dict mapping A1 range strings to 2D value arrays.
            Example: {"A1:B2": [[1, 2], [3, 4]], "D1:E2": [["a", "b"]]}
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    # Prepare the batch update request
    data = []
    for range_str, values in ranges.items():
        full_range = f"{sheet}!{range_str}"
        data.append({
            'range': full_range,
            'values': values
        })

    batch_body = {
        'valueInputOption': 'USER_ENTERED',
        'data': data
    }

    # Call the Sheets API to perform batch update
    result = sheets_service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=batch_body
    ).execute()

    return result


@mcp.tool()
def append_data(spreadsheet_id: str,
                sheet: str,
                data: List[List[Any]],
                range: Optional[str] = None,
                value_input_option: str = 'USER_ENTERED',
                insert_data_option: str = 'INSERT_ROWS',
                ctx: Context = None) -> Dict[str, Any]:
    """
    Append rows after last row with data in range.

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet: Sheet name
        data: 2D array of values to append
        range: A1 range anchor (e.g. 'A1'). Omit to target whole sheet.
        value_input_option: 'USER_ENTERED' (default, parses formulas/dates) or 'RAW' (literal values)
        insert_data_option: 'INSERT_ROWS' (default, inserts rows) or 'OVERWRITE' (overwrites at table end)
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    # Construct the range: whole sheet if no range given, otherwise sheet!range
    if range:
        full_range = f"{sheet}!{range}"
    else:
        full_range = sheet

    body = {'values': data}

    result = sheets_service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=full_range,
        valueInputOption=value_input_option,
        insertDataOption=insert_data_option,
        body=body
    ).execute()

    return result


@mcp.tool()
def batch_clear_values(spreadsheet_id: str,
                       ranges: List[str],
                       ctx: Context = None) -> List[str]:
    """
    Clear multiple ranges in one batchClear call.

    Args:
        spreadsheet_id: Spreadsheet ID
        ranges: A1 ranges to clear (e.g. ['Sheet1!A1:B2', 'Sheet2!C3:D4'])
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    body = {'ranges': ranges}

    result = sheets_service.spreadsheets().values().batchClear(
        spreadsheetId=spreadsheet_id,
        body=body
    ).execute()

    return result.get('clearedRanges', [])


@mcp.tool()
def find_replace(spreadsheet_id: str,
                 find: str,
                 replacement: str,
                 sheet: Optional[str] = None,
                 match_case: bool = False,
                 match_entire_cell: bool = False,
                 search_by_regex: bool = False,
                 include_formulas: bool = False,
                 ctx: Context = None) -> Dict[str, Any]:
    """
    Find and replace text in spreadsheet or single sheet.

    Args:
        spreadsheet_id: Spreadsheet ID
        find: Value to search for
        replacement: Replacement value
        sheet: Sheet name to restrict search. Omit to search all sheets.
        match_case: Case-sensitive search (default False)
        match_entire_cell: Match only cells whose entire value equals find (default False)
        search_by_regex: Treat find as regex (default False)
        include_formulas: Search formula text instead of computed values (default False)
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    find_replace_request: Dict[str, Any] = {
        'find': find,
        'replacement': replacement,
        'matchCase': match_case,
        'matchEntireCell': match_entire_cell,
        'searchByRegex': search_by_regex,
        'includeFormulas': include_formulas,
    }

    if sheet is not None:
        # Restrict to a single sheet by sheetId
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet)
        find_replace_request['sheetId'] = sheet_id
    else:
        find_replace_request['allSheets'] = True

    body = {
        'requests': [{'findReplace': find_replace_request}]
    }

    result = sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=body
    ).execute()

    replies = result.get('replies', [])
    find_replace_reply = replies[0].get('findReplace', {}) if replies else {}

    return {
        'occurrencesChanged': find_replace_reply.get('occurrencesChanged', 0),
        'valuesChanged': find_replace_reply.get('valuesChanged', 0),
    }
