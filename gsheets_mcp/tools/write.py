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
    Update cells in a Google Spreadsheet.

    Args:
        spreadsheet_id: The ID of the spreadsheet (found in the URL)
        sheet: The name of the sheet
        range: Cell range in A1 notation (e.g., 'A1:C10')
        data: 2D array of values to update

    Returns:
        Result of the update operation
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
    Batch update multiple ranges in a Google Spreadsheet.

    Args:
        spreadsheet_id: The ID of the spreadsheet (found in the URL)
        sheet: The name of the sheet
        ranges: Dictionary mapping range strings to 2D arrays of values
               e.g., {'A1:B2': [[1, 2], [3, 4]], 'D1:E2': [['a', 'b'], ['c', 'd']]}

    Returns:
        Result of the batch update operation
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
    Append rows after the last row with data in a range.

    Args:
        spreadsheet_id: The ID of the spreadsheet (found in the URL)
        sheet: The name of the sheet
        data: 2D array of values to append
        range: Cell range in A1 notation (e.g., 'A1'). If not provided, targets the whole sheet.
        value_input_option: How the input data should be interpreted.
            'USER_ENTERED' (default) parses values as if typed by a user.
            'RAW' stores values exactly as provided.
        insert_data_option: How existing data is changed when new data is input.
            'INSERT_ROWS' (default) inserts new rows for the appended data.
            'OVERWRITE' overwrites existing data starting at the end of the table.

    Returns:
        API response containing an updates summary with counts of updated rows, columns, and cells.
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
    Clear multiple ranges in one API call.

    Args:
        spreadsheet_id: The ID of the spreadsheet (found in the URL)
        ranges: List of ranges in A1 notation to clear (e.g., ['Sheet1!A1:B2', 'Sheet2!C3:D4'])

    Returns:
        List of ranges that were cleared.
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
    Find and replace text across a spreadsheet or a specific sheet.

    Args:
        spreadsheet_id: The ID of the spreadsheet (found in the URL)
        find: The value to search for
        replacement: The value to replace matches with
        sheet: Sheet name to restrict the search to. If omitted, searches all sheets.
        match_case: If True, the search is case-sensitive. Default False.
        match_entire_cell: If True, only matches cells whose entire value matches find. Default False.
        search_by_regex: If True, treats find as a regular expression. Default False.
        include_formulas: If True, searches formula text instead of computed values. Default False.

    Returns:
        Dictionary with occurrencesChanged and valuesChanged counts from the API response.
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
