"""
Structure tools: add/delete rows, columns, and auto-resize dimensions.
"""

from typing import Dict, Any, List, Optional

from mcp.server.fastmcp import Context

from gsheets_mcp.core import mcp, _get_sheet_id, _col_to_num, _a1_to_grid_range
from gsheets_mcp.builders import build_freeze_request


@mcp.tool()
def add_rows(spreadsheet_id: str,
             sheet: str,
             count: int,
             start_row: Optional[int] = None,
             ctx: Context = None) -> Dict[str, Any]:
    """
    Add rows to sheet (insertDimension).

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet: Sheet name
        count: Number of rows to add
        start_row: 0-based row index. Omit to add at beginning.
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    # Get sheet ID
    spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_id = None

    for s in spreadsheet['sheets']:
        if s['properties']['title'] == sheet:
            sheet_id = s['properties']['sheetId']
            break

    if sheet_id is None:
        return {"error": f"Sheet '{sheet}' not found"}

    # Prepare the insert rows request
    request_body = {
        "requests": [
            {
                "insertDimension": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": start_row if start_row is not None else 0,
                        "endIndex": (start_row if start_row is not None else 0) + count
                    },
                    "inheritFromBefore": start_row is not None and start_row > 0
                }
            }
        ]
    }

    # Execute the request
    result = sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=request_body
    ).execute()

    return result


@mcp.tool()
def add_columns(spreadsheet_id: str,
                sheet: str,
                count: int,
                start_column: Optional[int] = None,
                ctx: Context = None) -> Dict[str, Any]:
    """
    Add columns to sheet (insertDimension).

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet: Sheet name
        count: Number of columns to add
        start_column: 0-based column index. Omit to add at beginning.
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    # Get sheet ID
    spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_id = None

    for s in spreadsheet['sheets']:
        if s['properties']['title'] == sheet:
            sheet_id = s['properties']['sheetId']
            break

    if sheet_id is None:
        return {"error": f"Sheet '{sheet}' not found"}

    # Prepare the insert columns request
    request_body = {
        "requests": [
            {
                "insertDimension": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": start_column if start_column is not None else 0,
                        "endIndex": (start_column if start_column is not None else 0) + count
                    },
                    "inheritFromBefore": start_column is not None and start_column > 0
                }
            }
        ]
    }

    # Execute the request
    result = sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=request_body
    ).execute()

    return result


@mcp.tool()
def delete_rows_columns(spreadsheet_id: str,
                        sheet_name: str,
                        dimension: str,
                        start_index: int,
                        end_index: int,
                        ctx: Context = None) -> Dict[str, Any]:
    """
    Delete rows or columns (deleteDimension).

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet_name: Sheet name (case-sensitive)
        dimension: 'ROWS' or 'COLUMNS'
        start_index: 0-based start index (inclusive)
        end_index: 0-based end index (exclusive)
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)

        request_body = {
            "requests": [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": dimension.upper(),
                            "startIndex": start_index,
                            "endIndex": end_index
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
            "message": f"Deleted {dimension} from {start_index} to {end_index}",
            "dimension": dimension,
            "start_index": start_index,
            "end_index": end_index
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error deleting {dimension}: {str(e)}"
        }


@mcp.tool()
def auto_resize_dimensions(spreadsheet_id: str,
                           sheet_name: str,
                           dimensions: Dict[str, Any],
                           ctx: Context = None) -> Dict[str, Any]:
    """
    Auto-fit row and/or column sizes (autoResizeDimensions).

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet_name: Sheet name (case-sensitive)
        dimensions: Dict with 'columns' and/or 'rows' keys, each: {startIndex, endIndex}.
            Example: {"columns": {"startIndex": 0, "endIndex": 10}, "rows": {"startIndex": 0, "endIndex": 20}}
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)

        requests = []

        # Process column dimensions
        if 'columns' in dimensions:
            col_dim = dimensions['columns']
            requests.append({
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": col_dim.get('startIndex', 0),
                        "endIndex": col_dim.get('endIndex', col_dim.get('startIndex', 0) + 1)
                    }
                }
            })

        # Process row dimensions
        if 'rows' in dimensions:
            row_dim = dimensions['rows']
            requests.append({
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": row_dim.get('startIndex', 0),
                        "endIndex": row_dim.get('endIndex', row_dim.get('startIndex', 0) + 1)
                    }
                }
            })

        request_body = {"requests": requests}

        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()

        return {
            "success": True,
            "message": f"Auto-resized dimensions in {sheet_name}",
            "dimensions": dimensions
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error auto-resizing dimensions: {str(e)}"
        }


# ---------------------------------------------------------------------------
# New tools
# ---------------------------------------------------------------------------

@mcp.tool()
def insert_rows(spreadsheet_id: str,
                sheet: str,
                start_index: int,
                count: int,
                inherit_from_before: bool = True,
                ctx: Context = None) -> Dict[str, Any]:
    """
    Insert N rows at 0-based index (insertDimension).

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet: Sheet name
        start_index: 0-based row index for insertion
        count: Number of rows to insert
        inherit_from_before: Inherit formatting from row above (default True)
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet)

        request_body = {
            "requests": [
                {
                    "insertDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": start_index,
                            "endIndex": start_index + count,
                        },
                        "inheritFromBefore": inherit_from_before,
                    }
                }
            ]
        }

        result = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()

        return result

    except Exception as e:
        return {"error": str(e), "success": False}


@mcp.tool()
def insert_columns(spreadsheet_id: str,
                   sheet: str,
                   start_index: int,
                   count: int,
                   inherit_from_before: bool = True,
                   ctx: Context = None) -> Dict[str, Any]:
    """
    Insert N columns at 0-based index (insertDimension).

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet: Sheet name
        start_index: 0-based column index for insertion
        count: Number of columns to insert
        inherit_from_before: Inherit formatting from column before (default True)
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet)

        request_body = {
            "requests": [
                {
                    "insertDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": start_index,
                            "endIndex": start_index + count,
                        },
                        "inheritFromBefore": inherit_from_before,
                    }
                }
            ]
        }

        result = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()

        return result

    except Exception as e:
        return {"error": str(e), "success": False}


@mcp.tool()
def delete_columns(spreadsheet_id: str,
                   sheet: str,
                   start_index: int,
                   end_index: int,
                   ctx: Context = None) -> Dict[str, Any]:
    """
    Delete columns (deleteDimension, column-only wrapper).

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet: Sheet name (case-sensitive)
        start_index: 0-based start column index (inclusive)
        end_index: 0-based end column index (exclusive)
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet)

        request_body = {
            "requests": [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": start_index,
                            "endIndex": end_index,
                        }
                    }
                }
            ]
        }

        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()

        return {
            "success": True,
            "message": f"Deleted COLUMNS from {start_index} to {end_index}",
            "start_index": start_index,
            "end_index": end_index,
        }

    except Exception as e:
        return {"success": False, "message": f"Error deleting columns: {str(e)}"}


@mcp.tool()
def freeze_dimensions(spreadsheet_id: str,
                      sheet: str,
                      frozen_rows: Optional[int] = None,
                      frozen_columns: Optional[int] = None,
                      ctx: Context = None) -> Dict[str, Any]:
    """
    Freeze rows and/or columns (updateSheetProperties). At least one of frozen_rows/frozen_columns required.

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet: Sheet name (case-sensitive)
        frozen_rows: Rows to freeze (omit to leave unchanged)
        frozen_columns: Columns to freeze (omit to leave unchanged)
    """
    if frozen_rows is None and frozen_columns is None:
        return {"error": "At least one of frozen_rows or frozen_columns must be specified", "success": False}

    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet)

        request_body = {
            "requests": [
                build_freeze_request(
                    sheet_id=sheet_id,
                    frozen_rows=frozen_rows,
                    frozen_cols=frozen_columns,
                )
            ]
        }

        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()

        return {
            "success": True,
            "message": f"Frozen rows={frozen_rows}, columns={frozen_columns} in {sheet}",
        }

    except Exception as e:
        return {"success": False, "message": f"Error freezing dimensions: {str(e)}"}


@mcp.tool()
def set_dimension_size(spreadsheet_id: str,
                       sheet: str,
                       dimension: str,
                       start_index: int,
                       end_index: int,
                       pixel_size: int,
                       ctx: Context = None) -> Dict[str, Any]:
    """
    Set row/column size to exact pixel size (updateDimensionProperties).

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet: Sheet name (case-sensitive)
        dimension: 'ROWS' or 'COLUMNS'
        start_index: 0-based start index (inclusive)
        end_index: 0-based end index (exclusive)
        pixel_size: Target pixel size
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet)

        request_body = {
            "requests": [
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": dimension.upper(),
                            "startIndex": start_index,
                            "endIndex": end_index,
                        },
                        "properties": {
                            "pixelSize": pixel_size,
                        },
                        "fields": "pixelSize",
                    }
                }
            ]
        }

        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()

        return {
            "success": True,
            "message": f"Set {dimension} pixel size to {pixel_size} for indices {start_index}:{end_index}",
        }

    except Exception as e:
        return {"success": False, "message": f"Error setting dimension size: {str(e)}"}


@mcp.tool()
def group_dimensions(spreadsheet_id: str,
                     sheet: str,
                     dimension: str,
                     start_index: int,
                     end_index: int,
                     ctx: Context = None) -> Dict[str, Any]:
    """
    Group rows or columns (addDimensionGroup, creates collapsible group).

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet: Sheet name (case-sensitive)
        dimension: 'ROWS' or 'COLUMNS'
        start_index: 0-based start index (inclusive)
        end_index: 0-based end index (exclusive)
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet)

        request_body = {
            "requests": [
                {
                    "addDimensionGroup": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": dimension.upper(),
                            "startIndex": start_index,
                            "endIndex": end_index,
                        }
                    }
                }
            ]
        }

        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()

        return {
            "success": True,
            "message": f"Grouped {dimension} from {start_index} to {end_index} in {sheet}",
        }

    except Exception as e:
        return {"success": False, "message": f"Error grouping dimensions: {str(e)}"}


@mcp.tool()
def ungroup_dimensions(spreadsheet_id: str,
                       sheet: str,
                       dimension: str,
                       start_index: int,
                       end_index: int,
                       ctx: Context = None) -> Dict[str, Any]:
    """
    Ungroup rows or columns (deleteDimensionGroup).

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet: Sheet name (case-sensitive)
        dimension: 'ROWS' or 'COLUMNS'
        start_index: 0-based start index (inclusive)
        end_index: 0-based end index (exclusive)
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet)

        request_body = {
            "requests": [
                {
                    "deleteDimensionGroup": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": dimension.upper(),
                            "startIndex": start_index,
                            "endIndex": end_index,
                        }
                    }
                }
            ]
        }

        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()

        return {
            "success": True,
            "message": f"Ungrouped {dimension} from {start_index} to {end_index} in {sheet}",
        }

    except Exception as e:
        return {"success": False, "message": f"Error ungrouping dimensions: {str(e)}"}



@mcp.tool()
def sort_range(spreadsheet_id: str,
               sheet: str,
               range: str,
               sort_specs: List[Dict[str, Any]],
               ctx: Context = None) -> Dict[str, Any]:
    """
    Sort range by one or more columns (sortRange).

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet: Sheet name (case-sensitive)
        range: A1 range to sort (e.g. 'A1:D10')
        sort_specs: List of {dimension_index: int (0-based col), sort_order: 'ASCENDING'|'DESCENDING'}
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet)

        grid_range = _a1_to_grid_range(sheet_id, range)

        api_sort_specs = [
            {
                "dimensionIndex": spec["dimension_index"],
                "sortOrder": spec["sort_order"],
            }
            for spec in sort_specs
        ]

        request_body = {
            "requests": [
                {
                    "sortRange": {
                        "range": grid_range,
                        "sortSpecs": api_sort_specs,
                    }
                }
            ]
        }

        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()

        return {
            "success": True,
            "message": f"Sorted range {range} in {sheet}",
        }

    except Exception as e:
        return {"success": False, "message": f"Error sorting range: {str(e)}"}
