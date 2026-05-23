"""
Structure tools: add/delete rows, columns, and auto-resize dimensions.
"""

from typing import Annotated, Dict, Any, List, Literal, Optional

from pydantic import Field
from mcp.server.fastmcp import Context

from gsheets_mcp.core import mcp, _get_sheet_id, _col_to_num, _a1_to_grid_range
from gsheets_mcp.builders import build_freeze_request


@mcp.tool()
def add_rows(spreadsheet_id: str,
             sheet: str,
             count: int,
             start_row: Annotated[Optional[int], Field(description="0-based row index. Omit to add at beginning.")] = None,
             ctx: Context = None) -> Dict[str, Any]:
    """Add rows to a sheet via insertDimension."""
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
                start_column: Annotated[Optional[int], Field(description="0-based column index. Omit to add at beginning.")] = None,
                ctx: Context = None) -> Dict[str, Any]:
    """Add columns to a sheet via insertDimension."""
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
                        dimension: Literal['ROWS', 'COLUMNS'],
                        start_index: Annotated[int, Field(description="0-based start index (inclusive)")],
                        end_index: Annotated[int, Field(description="0-based end index (exclusive)")],
                        ctx: Context = None) -> Dict[str, Any]:
    """Delete rows or columns by dimension and 0-based index range (deleteDimension)."""
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
                           dimensions: Annotated[Dict[str, Any], Field(description='Dict with "columns" and/or "rows" keys, each: {startIndex, endIndex}. Example: {"columns": {"startIndex": 0, "endIndex": 10}}')],
                           ctx: Context = None) -> Dict[str, Any]:
    """Auto-fit row and/or column sizes to content (autoResizeDimensions)."""
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
                start_index: Annotated[int, Field(description="0-based row index for insertion")],
                count: int,
                inherit_from_before: bool = True,
                ctx: Context = None) -> Dict[str, Any]:
    """Insert N rows at a 0-based index, optionally inheriting formatting from the row above (insertDimension)."""
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
                   start_index: Annotated[int, Field(description="0-based column index for insertion")],
                   count: int,
                   inherit_from_before: bool = True,
                   ctx: Context = None) -> Dict[str, Any]:
    """Insert N columns at a 0-based index, optionally inheriting formatting from the column before (insertDimension)."""
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
                   start_index: Annotated[int, Field(description="0-based start column index (inclusive)")],
                   end_index: Annotated[int, Field(description="0-based end column index (exclusive)")],
                   ctx: Context = None) -> Dict[str, Any]:
    """Delete columns by 0-based index range (deleteDimension, column-only wrapper)."""
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
                      frozen_rows: Annotated[Optional[int], Field(description="Number of rows to freeze. Omit to leave unchanged.")] = None,
                      frozen_columns: Annotated[Optional[int], Field(description="Number of columns to freeze. Omit to leave unchanged.")] = None,
                      ctx: Context = None) -> Dict[str, Any]:
    """Freeze rows and/or columns (updateSheetProperties); at least one of frozen_rows/frozen_columns required."""
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
                       dimension: Literal['ROWS', 'COLUMNS'],
                       start_index: Annotated[int, Field(description="0-based start index (inclusive)")],
                       end_index: Annotated[int, Field(description="0-based end index (exclusive)")],
                       pixel_size: Annotated[int, Field(description="Target pixel size in pixels")],
                       ctx: Context = None) -> Dict[str, Any]:
    """Set rows or columns to an exact pixel size (updateDimensionProperties)."""
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
                     dimension: Literal['ROWS', 'COLUMNS'],
                     start_index: Annotated[int, Field(description="0-based start index (inclusive)")],
                     end_index: Annotated[int, Field(description="0-based end index (exclusive)")],
                     ctx: Context = None) -> Dict[str, Any]:
    """Group rows or columns into a collapsible group (addDimensionGroup)."""
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
                       dimension: Literal['ROWS', 'COLUMNS'],
                       start_index: Annotated[int, Field(description="0-based start index (inclusive)")],
                       end_index: Annotated[int, Field(description="0-based end index (exclusive)")],
                       ctx: Context = None) -> Dict[str, Any]:
    """Remove a dimension group from rows or columns (deleteDimensionGroup)."""
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
               range: Annotated[str, Field(description="A1 range to sort, e.g. 'A1:D10'")],
               sort_specs: Annotated[List[Dict[str, Any]], Field(description="List of {dimension_index: int (0-based col), sort_order: 'ASCENDING'|'DESCENDING'}")],
               ctx: Context = None) -> Dict[str, Any]:
    """Sort a range by one or more columns (sortRange)."""
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
