"""
Pivot table tools: create and delete pivot tables in Google Sheets.

Pivot tables are written by placing a PivotTable spec on an anchor cell
via the spreadsheets.batchUpdate updateCells request.
"""

from typing import Dict, Any, List, Optional

from mcp.server.fastmcp import Context

from gsheets_mcp.core import mcp, _get_sheet_id, _parse_row_col


@mcp.tool()
def create_pivot_table(spreadsheet_id: str,
                       source_sheet: str,
                       source_range: str,
                       anchor_sheet: str,
                       anchor_row: int,
                       anchor_col: int,
                       rows: List[Dict[str, Any]],
                       values: List[Dict[str, Any]],
                       columns: Optional[List[Dict[str, Any]]] = None,
                       ctx: Context = None) -> Dict[str, Any]:
    """
    Create pivot table via updateCells on anchor cell.

    Args:
        spreadsheet_id: Spreadsheet ID
        source_sheet: Sheet with source data
        source_range: A1 range of source data (e.g. 'A1:C100')
        anchor_sheet: Sheet where pivot table is placed
        anchor_row: 0-based row index of anchor cell
        anchor_col: 0-based column index of anchor cell
        rows: Row groupings, each: {source_column_offset: int, show_totals: bool, sort_order: str}
        values: Value fields, each: {source_column_offset: int, summarize_function: str}
        columns: Optional column groupings (same shape as rows)
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        source_sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, source_sheet)
        anchor_sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, anchor_sheet)

        range_info = _parse_row_col(source_range)

        source_grid_range = {
            "sheetId": source_sheet_id,
            "startRowIndex": range_info["start_row"] - 1,
            "endRowIndex": range_info["end_row"],
            "startColumnIndex": range_info["start_col"] - 1,
            "endColumnIndex": range_info["end_col"]
        }

        pivot_rows = [
            {
                "sourceColumnOffset": r["source_column_offset"],
                "showTotals": r["show_totals"],
                "sortOrder": r["sort_order"]
            }
            for r in rows
        ]

        pivot_values = [
            {
                "sourceColumnOffset": v["source_column_offset"],
                "summarizeFunction": v["summarize_function"]
            }
            for v in values
        ]

        pivot_table_spec: Dict[str, Any] = {
            "source": source_grid_range,
            "rows": pivot_rows,
            "values": pivot_values
        }

        if columns:
            pivot_table_spec["columns"] = [
                {
                    "sourceColumnOffset": c["source_column_offset"],
                    "showTotals": c["show_totals"],
                    "sortOrder": c["sort_order"]
                }
                for c in columns
            ]

        request_body = {
            "requests": [
                {
                    "updateCells": {
                        "rows": [
                            {
                                "values": [
                                    {
                                        "pivotTable": pivot_table_spec
                                    }
                                ]
                            }
                        ],
                        "start": {
                            "sheetId": anchor_sheet_id,
                            "rowIndex": anchor_row,
                            "columnIndex": anchor_col
                        },
                        "fields": "pivotTable"
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
            "message": "Pivot table created successfully",
            "anchor_sheet": anchor_sheet,
            "anchor_row": anchor_row,
            "anchor_col": anchor_col
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error creating pivot table: {str(e)}"
        }


@mcp.tool()
def delete_pivot_table(spreadsheet_id: str,
                       anchor_sheet: str,
                       anchor_row: int,
                       anchor_col: int,
                       ctx: Context = None) -> Dict[str, Any]:
    """
    Delete pivot table by writing empty cell at anchor position.

    Args:
        spreadsheet_id: Spreadsheet ID
        anchor_sheet: Sheet containing pivot table
        anchor_row: 0-based row index of anchor cell
        anchor_col: 0-based column index of anchor cell
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        anchor_sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, anchor_sheet)

        request_body = {
            "requests": [
                {
                    "updateCells": {
                        "rows": [
                            {
                                "values": [{}]
                            }
                        ],
                        "start": {
                            "sheetId": anchor_sheet_id,
                            "rowIndex": anchor_row,
                            "columnIndex": anchor_col
                        },
                        "fields": "pivotTable"
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
            "message": "Pivot table deleted successfully",
            "anchor_sheet": anchor_sheet,
            "anchor_row": anchor_row,
            "anchor_col": anchor_col
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error deleting pivot table: {str(e)}"
        }
