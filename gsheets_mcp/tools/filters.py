"""
Filter tools: create, apply criteria to, and clear filters, plus named filter views.
"""

from typing import Dict, Any, Optional

from mcp.server.fastmcp import Context

from gsheets_mcp.core import mcp, _get_sheet_id, _parse_row_col


@mcp.tool()
def create_filter(spreadsheet_id: str,
                  sheet_name: str,
                  range: str,
                  ctx: Context = None) -> Dict[str, Any]:
    """
    Apply basic filter (setBasicFilter) to range.

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet_name: Sheet name (case-sensitive)
        range: A1 range (e.g. 'A1:C10')
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)
        range_info = _parse_row_col(range)

        request_body = {
            "requests": [
                {
                    "setBasicFilter": {
                        "filter": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": range_info['start_row'] - 1,
                                "endRowIndex": range_info['end_row'],
                                "startColumnIndex": range_info['start_col'] - 1,
                                "endColumnIndex": range_info['end_col']
                            }
                        }
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
            "message": f"Filter applied to {range}",
            "range": range,
            "sheet_id": sheet_id
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error creating filter: {str(e)}"
        }


@mcp.tool()
def apply_filter_criteria(spreadsheet_id: str,
                          sheet_name: str,
                          criteria: Dict[str, Any],
                          filter_view_id: Optional[int] = None,
                          ctx: Context = None) -> Dict[str, Any]:
    """
    Set filter criteria on basic filter or named filter view.

    filter_view_id absent: applies to basic filter via setBasicFilter (use after create_filter).
    filter_view_id provided: applies to named filter view via updateFilterView (use after create_filter_view).

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet_name: Sheet name (case-sensitive)
        criteria: Dict mapping column-index string to filter criteria.
            Example: {"0": {"condition": {"type": "NUMBER_GREATER", "values": [{"userEnteredValue": "100"}]}}}
        filter_view_id: ID of filter view to update. Omit to target basic filter.
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        if filter_view_id is None:
            # Basic filter path: use setBasicFilter with the full filter body
            # including criteria so the Sheets API accepts it.
            sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)
            request_body = {
                "requests": [
                    {
                        "setBasicFilter": {
                            "filter": {
                                "range": {
                                    "sheetId": sheet_id
                                },
                                "criteria": criteria
                            }
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
                "message": f"Basic filter criteria updated on {sheet_name}",
                "sheet_name": sheet_name,
                "criteria": criteria
            }
        else:
            # Named filter-view path: updateFilterView
            request_body = {
                "requests": [
                    {
                        "updateFilterView": {
                            "filter": {
                                "filterViewId": filter_view_id,
                                "criteria": criteria
                            },
                            "fields": "criteria"
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
                "message": f"Filter criteria updated for filter view {filter_view_id}",
                "filter_view_id": filter_view_id,
                "criteria": criteria
            }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error applying filter criteria: {str(e)}"
        }


@mcp.tool()
def clear_filter(spreadsheet_id: str,
                 sheet_name: str,
                 ctx: Context = None) -> Dict[str, Any]:
    """
    Remove basic filter from sheet (clearBasicFilter).

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet_name: Sheet name (case-sensitive)
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)

        request_body = {
            "requests": [
                {
                    "clearBasicFilter": {
                        "sheetId": sheet_id
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
            "message": f"Filter cleared from {sheet_name}",
            "sheet_name": sheet_name
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error clearing filter: {str(e)}"
        }


@mcp.tool()
def create_filter_view(spreadsheet_id: str,
                       sheet: str,
                       range: str,
                       title: str,
                       criteria: Optional[Dict[str, Any]] = None,
                       ctx: Context = None) -> Dict[str, Any]:
    """
    Create named saved filter view over range (addFilterView).

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet: Sheet name (case-sensitive)
        range: A1 range (e.g. 'A1:D10')
        title: Display name for filter view
        criteria: Optional dict mapping column-index string to filter criteria.
            Example: {"0": {"condition": {"type": "NUMBER_GREATER", "values": [{"userEnteredValue": "100"}]}}}
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet)
        range_info = _parse_row_col(range)

        filter_spec = {
            "title": title,
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": range_info['start_row'] - 1,
                "endRowIndex": range_info['end_row'],
                "startColumnIndex": range_info['start_col'] - 1,
                "endColumnIndex": range_info['end_col']
            }
        }

        if criteria is not None:
            filter_spec["criteria"] = criteria

        request_body = {
            "requests": [
                {
                    "addFilterView": {
                        "filter": filter_spec
                    }
                }
            ]
        }

        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()

        replies = response.get('replies', [{}])
        filter_view_id = (
            replies[0]
            .get('addFilterView', {})
            .get('filter', {})
            .get('filterViewId')
        )

        return {
            "success": True,
            "message": f"Filter view '{title}' created over {range}",
            "filter_view_id": filter_view_id,
            "title": title
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error creating filter view: {str(e)}"
        }


@mcp.tool()
def delete_filter_view(spreadsheet_id: str,
                       filter_view_id: int,
                       ctx: Context = None) -> Dict[str, Any]:
    """
    Delete named filter view by ID (deleteFilterView).

    Args:
        spreadsheet_id: Spreadsheet ID
        filter_view_id: Integer ID of filter view to delete
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        request_body = {
            "requests": [
                {
                    "deleteFilterView": {
                        "filterId": filter_view_id
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
            "message": f"Filter view {filter_view_id} deleted",
            "filter_view_id": filter_view_id
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error deleting filter view: {str(e)}"
        }
