"""
Named range tools: create, list, and update named ranges.
"""

from typing import Dict, Any

from mcp.server.fastmcp import Context

import re

from gsheets_mcp.core import mcp, _get_sheet_id
from gsheets_mcp.tools.structure import _a1_to_grid_range


def _resolve_grid_range(sheets_service, spreadsheet_id: str, range_str: str) -> dict:
    """
    Convert an A1 notation range (with or without a 'SheetName!' prefix) into a
    GridRange dict required by the Sheets API.

    If the range includes a sheet prefix (e.g. 'Sheet1!A2:A4'), that sheet's ID is
    looked up and the prefix is stripped before parsing. Otherwise the first sheet
    in the spreadsheet is used.
    """
    sheet_name = None
    cell_range = range_str

    # Strip optional 'SheetName!' prefix
    match = re.match(r"^(.+)!(.+)$", range_str)
    if match:
        sheet_name = match.group(1)
        cell_range = match.group(2)

    if sheet_name:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)
    else:
        # Use the first sheet's ID from the spreadsheet metadata
        meta = sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields='sheets.properties'
        ).execute()
        sheets = meta.get('sheets', [])
        if not sheets:
            raise ValueError("No sheets found in spreadsheet")
        sheet_id = sheets[0]['properties']['sheetId']

    return _a1_to_grid_range(sheet_id, cell_range)


@mcp.tool()
def create_named_range(spreadsheet_id: str,
                       name: str,
                       range: str,
                       ctx: Context = None) -> Dict[str, Any]:
    """
    Define named ranges for easier reference.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        name: Name for the named range
        range: Cell range in A1 notation (e.g., 'Sheet1!A1:C10')

    Returns:
        Dictionary with success status and named range details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        grid_range = _resolve_grid_range(sheets_service, spreadsheet_id, range)

        request_body = {
            "requests": [
                {
                    "addNamedRange": {
                        "namedRange": {
                            "name": name,
                            "range": grid_range
                        }
                    }
                }
            ]
        }

        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()

        named_range_id = response.get('replies', [{}])[0].get('addNamedRange', {}).get('namedRange', {}).get('namedRangeId')

        return {
            "success": True,
            "message": f"Named range '{name}' created successfully",
            "name": name,
            "range": range,
            "named_range_id": named_range_id
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error creating named range: {str(e)}"
        }


@mcp.tool()
def list_named_ranges(spreadsheet_id: str,
                      ctx: Context = None) -> Dict[str, Any]:
    """
    Get all named ranges in a spreadsheet.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet

    Returns:
        Dictionary with success status and list of named ranges
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        spreadsheet = sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields='namedRanges'
        ).execute()

        named_ranges = []
        for named_range in spreadsheet.get('namedRanges', []):
            named_ranges.append({
                'name': named_range.get('name'),
                'named_range_id': named_range.get('namedRangeId'),
                'range': named_range.get('range'),
                'sheet_id': named_range.get('range', {}).get('sheetId')
            })

        return {
            "success": True,
            "message": f"Found {len(named_ranges)} named ranges",
            "named_ranges": named_ranges
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error listing named ranges: {str(e)}"
        }


@mcp.tool()
def update_named_range(spreadsheet_id: str,
                       name: str,
                       new_range: str,
                       ctx: Context = None) -> Dict[str, Any]:
    """
    Modify existing named ranges.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        name: Current name of the named range
        new_range: New cell range in A1 notation

    Returns:
        Dictionary with success status and updated named range details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        # First, get existing named ranges to find the one to update
        spreadsheet = sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields='namedRanges'
        ).execute()

        named_range_id = None
        for named_range in spreadsheet.get('namedRanges', []):
            if named_range.get('name') == name:
                named_range_id = named_range.get('namedRangeId')
                break

        if not named_range_id:
            return {
                "success": False,
                "message": f"Named range '{name}' not found"
            }

        grid_range = _resolve_grid_range(sheets_service, spreadsheet_id, new_range)

        request_body = {
            "requests": [
                {
                    "updateNamedRange": {
                        "namedRange": {
                            "namedRangeId": named_range_id,
                            "name": name,
                            "range": grid_range
                        },
                        "fields": "range"
                    }
                }
            ]
        }

        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()

        return {
            "success": True,
            "message": f"Named range '{name}' updated successfully",
            "name": name,
            "new_range": new_range,
            "named_range_id": named_range_id
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error updating named range: {str(e)}"
        }
