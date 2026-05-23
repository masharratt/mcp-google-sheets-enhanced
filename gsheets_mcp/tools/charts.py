"""
Chart tools: create, update, and move/resize charts.
"""

from typing import Dict, Any, Optional

from mcp.server.fastmcp import Context

from gsheets_mcp.core import mcp, _get_sheet_id, _parse_row_col
from gsheets_mcp.builders import build_chart_spec, build_chart_request


@mcp.tool()
def create_chart(spreadsheet_id: str,
                 sheet_name: str,
                 chart_type: str,
                 data_range: str,
                 position: Dict[str, Any],
                 title: str = None,
                 ctx: Context = None) -> Dict[str, Any]:
    """
    Create chart in Google Sheets.

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet_name: Sheet name (case-sensitive)
        chart_type: 'COLUMN', 'BAR', 'LINE', 'PIE', 'SCATTER', or 'AREA'
        data_range: A1 range for chart data (e.g. 'A1:C10')
        position: Anchor position dict: {"sheetId": 0, "rowIndex": 10, "columnIndex": 5}
        title: Optional chart title
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

        # Build chart specification via builder
        chart_spec = build_chart_spec(
            chart_type=actual_chart_type,
            title=title or f"{chart_type} Chart",
            sheet_id=sheet_id,
            start_row=range_info['start_row'] - 1,
            end_row=range_info['end_row'],
            start_col=range_info['start_col'] - 1,
            end_col=range_info['end_col'],
        )

        # Ensure position has sheetId
        if 'sheetId' not in position:
            position['sheetId'] = sheet_id

        anchor = {
            "sheetId": position.get('sheetId', sheet_id),
            "rowIndex": position.get('rowIndex', 0),
            "columnIndex": position.get('columnIndex', 0),
            "offsetXPixels": position.get('offsetXPixels', 0),
            "offsetYPixels": position.get('offsetYPixels', 0),
        }
        request_body = {
            "requests": [
                build_chart_request(chart_spec=chart_spec, anchor=anchor)
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
    Update chart properties. Reads existing spec, merges changes, sends complete merged chartSpec
    (preserves required chart-type body: basicChart, pieChart, etc.).

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet_name: Sheet name (case-sensitive)
        chart_id: ID of chart to update
        properties: Chart spec properties to update, e.g. {"title": "New Title", "backgroundColor": {...}}
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        # Fetch the existing spreadsheet to retrieve the current chart spec.
        spreadsheet = sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="sheets.charts"
        ).execute()

        existing_spec: Dict[str, Any] = {}
        for sheet in spreadsheet.get("sheets", []):
            for chart in sheet.get("charts", []):
                if chart.get("chartId") == chart_id:
                    existing_spec = dict(chart.get("spec", {}))
                    break

        # Merge requested changes into the existing spec so the chart-type
        # body (basicChart / pieChart / etc.) is always present.
        merged_spec = {**existing_spec, **properties}

        request_body = {
            "requests": [
                {
                    "updateChartSpec": {
                        "chartId": chart_id,
                        "spec": merged_spec
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
    Delete chart (embedded object) from spreadsheet.

    Args:
        spreadsheet_id: Spreadsheet ID
        chart_id: ID of chart to delete
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
    Move and/or resize chart.

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet_name: Sheet name (case-sensitive)
        chart_id: ID of chart to move/resize
        position: New position dict: {"rowIndex": 15, "columnIndex": 8, "offsetXPixels": 10,
            "offsetYPixels": 10, "widthPixels": 600, "heightPixels": 400} (widthPixels/heightPixels optional)
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)

        overlay: Dict[str, Any] = {
            "anchorCell": {
                "sheetId": position.get('sheetId', sheet_id),
                "rowIndex": position.get('rowIndex', 0),
                "columnIndex": position.get('columnIndex', 0)
            },
            "offsetXPixels": position.get('offsetXPixels', 0),
            "offsetYPixels": position.get('offsetYPixels', 0)
        }
        if 'widthPixels' in position:
            overlay['widthPixels'] = position['widthPixels']
        if 'heightPixels' in position:
            overlay['heightPixels'] = position['heightPixels']

        request_body = {
            "requests": [
                {
                    "updateEmbeddedObjectPosition": {
                        "objectId": chart_id,
                        "newPosition": {
                            "overlayPosition": overlay
                        },
                        "fields": "anchorCell,offsetXPixels,offsetYPixels,widthPixels,heightPixels"
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
