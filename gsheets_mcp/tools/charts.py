"""
Chart tools: create, update, and move/resize charts.
"""

from typing import Dict, Any, Optional

from mcp.server.fastmcp import Context

from gsheets_mcp.core import mcp, _get_sheet_id, _parse_row_col


@mcp.tool()
def create_chart(spreadsheet_id: str,
                 sheet_name: str,
                 chart_type: str,
                 data_range: str,
                 position: Dict[str, Any],
                 title: str = None,
                 ctx: Context = None) -> Dict[str, Any]:
    """
    Create charts in Google Sheets.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        chart_type: Type of chart ('COLUMN', 'BAR', 'LINE', 'PIE', 'SCATTER', 'AREA')
        data_range: Data range for the chart (e.g., 'A1:C10')
        position: Dictionary with chart position. Example:
            {
                "sheetId": 0,
                "rowIndex": 10,
                "columnIndex": 5
            }
        title: Optional chart title

    Returns:
        Dictionary with success status and chart details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)
        range_info = _parse_row_col(data_range)

        # Chart type mapping
        chart_type_mapping = {
            'COLUMN': 'COLUMN',
            'BAR': 'BAR',
            'LINE': 'LINE',
            'PIE': 'PIE',
            'SCATTER': 'SCATTER',
            'AREA': 'AREA'
        }

        actual_chart_type = chart_type_mapping.get(chart_type.upper(), 'COLUMN')

        # Build chart specification
        chart_spec = {
            "title": title or f"{chart_type} Chart",
            "basicChart": {
                "chartType": actual_chart_type,
                "axis": [
                    {
                        "position": "BOTTOM_AXIS",
                        "title": "Categories"
                    },
                    {
                        "position": "LEFT_AXIS",
                        "title": "Values"
                    }
                ],
                "domains": [
                    {
                        "domain": {
                            "sourceRange": {
                                "sources": [
                                    {
                                        "sheetId": sheet_id,
                                        "startRowIndex": range_info['start_row'] - 1,
                                        "endRowIndex": range_info['end_row'],
                                        "startColumnIndex": range_info['start_col'] - 1,
                                        "endColumnIndex": range_info['start_col']
                                    }
                                ]
                            }
                        }
                    }
                ],
                "series": [
                    {
                        "series": {
                            "sourceRange": {
                                "sources": [
                                    {
                                        "sheetId": sheet_id,
                                        "startRowIndex": range_info['start_row'] - 1,
                                        "endRowIndex": range_info['end_row'],
                                        "startColumnIndex": range_info['start_col'],
                                        "endColumnIndex": range_info['end_col']
                                    }
                                ]
                            }
                        },
                        "targetAxis": "LEFT_AXIS"
                    }
                ],
                "headerCount": 1
            }
        }

        # Ensure position has sheetId
        if 'sheetId' not in position:
            position['sheetId'] = sheet_id

        request_body = {
            "requests": [
                {
                    "addChart": {
                        "chart": {
                            "spec": chart_spec,
                            "position": {
                                "overlayPosition": {
                                    "anchorCell": {
                                        "sheetId": position.get('sheetId', sheet_id),
                                        "rowIndex": position.get('rowIndex', 0),
                                        "columnIndex": position.get('columnIndex', 0)
                                    },
                                    "offsetXPixels": position.get('offsetXPixels', 0),
                                    "offsetYPixels": position.get('offsetYPixels', 0)
                                }
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

        chart_id = response.get('replies', [{}])[0].get('addChart', {}).get('chart', {}).get('chartId')

        return {
            "success": True,
            "message": f"Chart created successfully",
            "chart_id": chart_id,
            "chart_type": chart_type,
            "data_range": data_range,
            "title": title
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error creating chart: {str(e)}"
        }


@mcp.tool()
def update_chart(spreadsheet_id: str,
                 sheet_name: str,
                 chart_id: int,
                 properties: Dict[str, Any],
                 ctx: Context = None) -> Dict[str, Any]:
    """
    Modify chart properties.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        chart_id: ID of the chart to update
        properties: Dictionary with chart properties to update. Example:
            {
                "title": "New Chart Title",
                "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9}
            }

    Returns:
        Dictionary with success status and updated chart details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        request_body = {
            "requests": [
                {
                    "updateChartSpec": {
                        "chartId": chart_id,
                        "spec": properties
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
            "message": f"Chart {chart_id} updated successfully",
            "chart_id": chart_id,
            "properties": properties
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error updating chart: {str(e)}"
        }


@mcp.tool()
def delete_chart(spreadsheet_id: str,
                 chart_id: int,
                 ctx: Context = None) -> Dict[str, Any]:
    """
    Delete a chart from a Google Spreadsheet.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        chart_id: ID of the chart (embedded object) to delete

    Returns:
        Dictionary with success status and chart_id
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        request_body = {
            "requests": [
                {
                    "deleteEmbeddedObject": {
                        "objectId": chart_id
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
            "message": f"Chart {chart_id} deleted successfully",
            "chart_id": chart_id
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error deleting chart: {str(e)}"
        }


@mcp.tool()
def move_resize_chart(spreadsheet_id: str,
                      sheet_name: str,
                      chart_id: int,
                      position: Dict[str, Any],
                      ctx: Context = None) -> Dict[str, Any]:
    """
    Position and resize charts.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        chart_id: ID of the chart to move/resize
        position: Dictionary with new position. Example:
            {
                "rowIndex": 15,
                "columnIndex": 8,
                "offsetXPixels": 10,
                "offsetYPixels": 10
            }

    Returns:
        Dictionary with success status and position details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)

        request_body = {
            "requests": [
                {
                    "updateChartPosition": {
                        "chartId": chart_id,
                        "position": {
                            "overlayPosition": {
                                "anchorCell": {
                                    "sheetId": sheet_id,
                                    "rowIndex": position.get('rowIndex', 0),
                                    "columnIndex": position.get('columnIndex', 0)
                                },
                                "offsetXPixels": position.get('offsetXPixels', 0),
                                "offsetYPixels": position.get('offsetYPixels', 0)
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
            "message": f"Chart {chart_id} moved/resized successfully",
            "chart_id": chart_id,
            "position": position
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error moving/resizing chart: {str(e)}"
        }
