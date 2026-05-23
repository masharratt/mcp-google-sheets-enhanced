"""
Filter tools: create, apply criteria to, and clear filters, plus named filter views.
"""

from typing import Annotated, Dict, Any, Optional

from pydantic import Field

from mcp.server.fastmcp import Context

from gsheets_mcp.core import mcp, _get_sheet_id, _parse_row_col


@mcp.tool()
def create_filter(spreadsheet_id: str,
                  sheet_name: str,
                  range: Annotated[str, Field(description="A1 range, e.g. 'A1:C10'")],
                  ctx: Context = None) -> Dict[str, Any]:
    """Apply a basic filter (setBasicFilter) to a range so columns show filter dropdowns."""
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
                          criteria: Annotated[Dict[str, Any], Field(description='Dict mapping column-index string to filter criteria. Example: {"0": {"condition": {"type": "NUMBER_GREATER", "values": [{"userEnteredValue": "100"}]}}}')],
                          filter_view_id: Annotated[Optional[int], Field(description="ID of filter view to update. Omit to target the basic filter.")] = None,
                          ctx: Context = None) -> Dict[str, Any]:
    """Set filter criteria on a basic filter (omit filter_view_id) or a named filter view (provide filter_view_id)."""
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
    """Remove the basic filter from a sheet (clearBasicFilter)."""
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
                       range: Annotated[str, Field(description="A1 range, e.g. 'A1:D10'")],
                       title: str,
                       criteria: Annotated[Optional[Dict[str, Any]], Field(description='Optional dict mapping column-index string to filter criteria. Example: {"0": {"condition": {"type": "NUMBER_GREATER", "values": [{"userEnteredValue": "100"}]}}}')] = None,
                       ctx: Context = None) -> Dict[str, Any]:
    """Create a named, saved filter view over a range (addFilterView); use apply_filter_criteria to set its criteria."""
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
    """Delete a named filter view by its integer ID (deleteFilterView)."""
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
