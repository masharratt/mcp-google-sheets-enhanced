"""
Format tools: apply cell, text, number formatting, borders, merge cells, move ranges, banding.
"""

from typing import Dict, Any, Optional

from mcp.server.fastmcp import Context

from gsheets_mcp.core import mcp, _get_sheet_id, _parse_row_col, _get_format_fields, _build_cell_format, _map_text_format_keys


@mcp.tool()
def apply_cell_formatting(spreadsheet_id: str,
                        sheet_name: str,
                        range: str,
                        formatting: Dict[str, Any],
                        ctx: Context = None) -> Dict[str, Any]:
    """
    Apply comprehensive cell formatting to a range of cells.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        range: Cell range in A1 notation (e.g., "A1:C10")
        formatting: Dictionary containing formatting options:
            - text_format: Dict with font formatting
                * bold: bool
                * italic: bool
                * underline: bool
                * strikethrough: bool
                * font_family: str
                * font_size: int
                * foreground_color: Dict (red, green, blue, alpha)
                * background_color: Dict (red, green, blue, alpha)
            - alignment: Dict with alignment options
                * horizontal: "LEFT", "CENTER", "RIGHT"
                * vertical: "TOP", "MIDDLE", "BOTTOM"
                * wrap_strategy: "OVERFLOW_CELL", "CLIP", "WRAP"
            - borders: Dict with border formatting
                * top/bottom/left/right: Dict with style and color
    Returns:
        Dictionary with success status and details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        # Build the request body for cell formatting
        requests = []

        # Prepare cell format request
        cell_format = {}

        # Text formatting: camelCase sub-keys via helper
        if 'text_format' in formatting:
            cell_format['textFormat'] = _map_text_format_keys(formatting['text_format'])

        # Alignment: each key maps to a sibling camelCase field in userEnteredFormat
        if 'alignment' in formatting:
            alignment = formatting['alignment']
            if 'horizontal' in alignment:
                cell_format['horizontalAlignment'] = alignment['horizontal']
            if 'vertical' in alignment:
                cell_format['verticalAlignment'] = alignment['vertical']
            if 'wrap_strategy' in alignment:
                cell_format['wrapStrategy'] = alignment['wrap_strategy']

        # Background color
        if 'background_color' in formatting:
            cell_format['backgroundColor'] = formatting['background_color']

        # Borders (passed through as-is)
        if 'borders' in formatting:
            cell_format['borders'] = formatting['borders']

        # Number format (passed through as-is)
        if 'number_format' in formatting:
            cell_format['numberFormat'] = formatting['number_format']

        # Create the repeat cell request
        if cell_format:
            range_info = _parse_row_col(range)
            request = {
                'repeatCell': {
                    'range': {
                        'sheetId': _get_sheet_id(sheets_service, spreadsheet_id, sheet_name),
                        'startRowIndex': range_info['start_row'] - 1,
                        'endRowIndex': range_info['end_row'],
                        'startColumnIndex': range_info['start_col'] - 1,
                        'endColumnIndex': range_info['end_col']
                    },
                    'cell': {
                        'userEnteredFormat': cell_format
                    },
                    'fields': ','.join(_get_format_fields(cell_format))
                }
            }
            requests.append(request)

        # Execute the batch update
        if requests:
            body = {'requests': requests}
            response = sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=body
            ).execute()

            return {
                "success": True,
                "message": f"Successfully applied formatting to {sheet_name}!{range}",
                "applied_fields": list(cell_format.keys()),
                "updated_cells": _parse_row_col(range)['end_row'] - _parse_row_col(range)['start_row'] + 1
            }
        else:
            return {
                "success": False,
                "message": "No valid formatting options provided"
            }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error applying formatting: {str(e)}"
        }


@mcp.tool()
def set_number_format(spreadsheet_id: str,
                      sheet_name: str,
                      range: str,
                      number_format: str,
                      pattern: str = None,
                      ctx: Context = None) -> Dict[str, Any]:
    """
    Set number format for cells (currency, dates, percentages, etc.).

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        range: Cell range in A1 notation (e.g., 'A1:C10')
        number_format: Number format type ('TEXT', 'NUMBER', 'CURRENCY', 'PERCENT', 'DATE', 'TIME', 'DATE_TIME', 'SCIENTIFIC')
        pattern: Custom format pattern (optional, overrides number_format)

    Returns:
        Dictionary with success status and updated range information
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)
        range_info = _parse_row_col(range)

        # Build number format
        number_format_dict = {}
        if pattern:
            number_format_dict = {
                "type": "CUSTOM",
                "pattern": pattern
            }
        else:
            format_mapping = {
                'TEXT': {'type': 'TEXT', 'pattern': '@'},
                'NUMBER': {'type': 'NUMBER', 'pattern': '#,##0.###'},
                'CURRENCY': {'type': 'NUMBER', 'pattern': '$#,##0.00'},
                'PERCENT': {'type': 'NUMBER', 'pattern': '0.00%'},
                'DATE': {'type': 'DATE', 'pattern': 'mm/dd/yyyy'},
                'TIME': {'type': 'TIME', 'pattern': 'hh:mm:ss'},
                'DATE_TIME': {'type': 'DATE_TIME', 'pattern': 'mm/dd/yyyy hh:mm:ss'},
                'SCIENTIFIC': {'type': 'NUMBER', 'pattern': '0.00E+00'}
            }
            number_format_dict = format_mapping.get(number_format.upper(), format_mapping['NUMBER'])

        request_body = {
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": range_info['start_row'] - 1,
                            "endRowIndex": range_info['end_row'],
                            "startColumnIndex": range_info['start_col'] - 1,
                            "endColumnIndex": range_info['end_col']
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": number_format_dict
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat"
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
            "message": f"Number format applied to {range}",
            "range": range,
            "format": number_format_dict,
            "updated_cells": response.get('replies', [{}])[0].get('repeatCell', {}).get('cells', [])
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error setting number format: {str(e)}"
        }


@mcp.tool()
def add_cell_borders(spreadsheet_id: str,
                     sheet_name: str,
                     range: str,
                     borders: Dict[str, Any],
                     ctx: Context = None) -> Dict[str, Any]:
    """
    Add borders to cells with customizable styles and colors.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        range: Cell range in A1 notation (e.g., 'A1:C10')
        borders: Dictionary defining border styles. Example:
            {
                "top": {"style": "SOLID", "color": {"red": 0, "green": 0, "blue": 0}},
                "bottom": {"style": "SOLID", "color": {"red": 0, "green": 0, "blue": 0}},
                "left": {"style": "SOLID", "color": {"red": 0, "green": 0, "blue": 0}},
                "right": {"style": "SOLID", "color": {"red": 0, "green": 0, "blue": 0}}
            }
            Styles: NONE, SOLID, SOLID_MEDIUM, DOTTED, DASHED, DOUBLE, SOLID_THICK

    Returns:
        Dictionary with success status and border details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)
        range_info = _parse_row_col(range)

        # Build border format
        border_format = {}
        border_positions = ['top', 'bottom', 'left', 'right']

        for position in border_positions:
            if position in borders:
                border_config = borders[position]
                border_format[position] = {
                    'style': border_config.get('style', 'SOLID'),
                    'color': border_config.get('color', {'red': 0, 'green': 0, 'blue': 0})
                }

        request_body = {
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": range_info['start_row'] - 1,
                            "endRowIndex": range_info['end_row'],
                            "startColumnIndex": range_info['start_col'] - 1,
                            "endColumnIndex": range_info['end_col']
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "borders": border_format
                            }
                        },
                        "fields": "userEnteredFormat.borders"
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
            "message": f"Borders applied to {range}",
            "range": range,
            "borders": border_format,
            "updated_cells": response.get('replies', [{}])[0].get('repeatCell', {}).get('cells', [])
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error adding borders: {str(e)}"
        }


@mcp.tool()
def apply_text_formatting(spreadsheet_id: str,
                          sheet_name: str,
                          range: str,
                          text_formatting: Dict[str, Any],
                          ctx: Context = None) -> Dict[str, Any]:
    """
    Apply text formatting to cells (font styles, alignment, colors).

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        range: Cell range in A1 notation (e.g., 'A1:C10')
        text_formatting: Dictionary with formatting options:
            {
                "font_family": "Arial",
                "font_size": 12,
                "bold": true,
                "italic": false,
                "underline": false,
                "strikethrough": false,
                "foreground_color": {"red": 1, "green": 0, "blue": 0},
                "background_color": {"red": 1, "green": 1, "blue": 0},
                "horizontal_alignment": "CENTER",
                "vertical_alignment": "MIDDLE",
                "wrap_text": true
            }
            horizontal_alignment: LEFT, CENTER, RIGHT
            vertical_alignment: TOP, MIDDLE, BOTTOM

    Returns:
        Dictionary with success status and formatting details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)
        range_info = _parse_row_col(range)

        # Build text format
        text_format = {}
        if 'font_family' in text_formatting:
            text_format['fontFamily'] = text_formatting['font_family']
        if 'font_size' in text_formatting:
            text_format['fontSize'] = text_formatting['font_size']
        if 'bold' in text_formatting:
            text_format['bold'] = text_formatting['bold']
        if 'italic' in text_formatting:
            text_format['italic'] = text_formatting['italic']
        if 'underline' in text_formatting:
            text_format['underline'] = text_formatting['underline']
        if 'strikethrough' in text_formatting:
            text_format['strikethrough'] = text_formatting['strikethrough']

        # Build cell format
        cell_format = {"textFormat": text_format} if text_format else {}

        if 'foreground_color' in text_formatting:
            if 'textFormat' not in cell_format:
                cell_format['textFormat'] = {}
            cell_format['textFormat']['foregroundColor'] = text_formatting['foreground_color']

        if 'background_color' in text_formatting:
            cell_format['backgroundColor'] = text_formatting['background_color']

        if 'horizontal_alignment' in text_formatting:
            cell_format['horizontalAlignment'] = text_formatting['horizontal_alignment']

        if 'vertical_alignment' in text_formatting:
            cell_format['verticalAlignment'] = text_formatting['vertical_alignment']

        if 'wrap_text' in text_formatting:
            cell_format['wrapStrategy'] = 'WRAP' if text_formatting['wrap_text'] else 'OVERFLOW'

        request_body = {
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": range_info['start_row'] - 1,
                            "endRowIndex": range_info['end_row'],
                            "startColumnIndex": range_info['start_col'] - 1,
                            "endColumnIndex": range_info['end_col']
                        },
                        "cell": {
                            "userEnteredFormat": cell_format
                        },
                        "fields": "userEnteredFormat(" + ",".join(_get_format_fields(cell_format)) + ")"
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
            "message": f"Text formatting applied to {range}",
            "range": range,
            "formatting": text_formatting,
            "updated_cells": response.get('replies', [{}])[0].get('repeatCell', {}).get('cells', [])
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error applying text formatting: {str(e)}"
        }


@mcp.tool()
def merge_cells(spreadsheet_id: str,
                sheet_name: str,
                range: str,
                merge_type: str = "MERGE_ALL",
                ctx: Context = None) -> Dict[str, Any]:
    """
    Merge or unmerge cells.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        range: Cell range in A1 notation (e.g., 'A1:C10')
        merge_type: Type of merge ('MERGE_ALL', 'MERGE_COLUMNS', 'MERGE_ROWS', 'UNMERGE')

    Returns:
        Dictionary with success status and merge details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)
        range_info = _parse_row_col(range)

        merge_type_mapping = {
            'MERGE_ALL': 'MERGE_ALL',
            'MERGE_COLUMNS': 'MERGE_COLUMNS',
            'MERGE_ROWS': 'MERGE_ROWS',
            'UNMERGE': 'UNMERGE'
        }

        actual_merge_type = merge_type_mapping.get(merge_type.upper(), 'MERGE_ALL')

        request_body = {
            "requests": [
                {
                    "mergeCells": {
                        "mergeType": actual_merge_type,
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": range_info['start_row'] - 1,
                            "endRowIndex": range_info['end_row'],
                            "startColumnIndex": range_info['start_col'] - 1,
                            "endColumnIndex": range_info['end_col']
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
            "message": f"Cells {range} merged with type {merge_type}",
            "range": range,
            "merge_type": merge_type
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error merging cells: {str(e)}"
        }


@mcp.tool()
def move_range(spreadsheet_id: str,
               sheet_name: str,
               source_range: str,
               destination: Dict[str, Any],
               ctx: Context = None) -> Dict[str, Any]:
    """
    Move data ranges.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        source_range: Source range in A1 notation (e.g., 'A1:C10')
        destination: Dictionary with destination position. Example:
            {
                "sheetId": 0,
                "rowIndex": 5,
                "columnIndex": 2
            }

    Returns:
        Dictionary with success status and move details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)
        source_range_info = _parse_row_col(source_range)

        request_body = {
            "requests": [
                {
                    "moveDimension": {
                        "source": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": source_range_info['start_row'] - 1,
                            "endIndex": source_range_info['end_row']
                        },
                        "destinationIndex": destination.get('rowIndex', 0)
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
            "message": f"Range {source_range} moved successfully",
            "source_range": source_range,
            "destination": destination
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error moving range: {str(e)}"
        }


@mcp.tool()
def add_banding(spreadsheet_id: str,
                sheet: str,
                range: str,
                first_band_color: Dict[str, float],
                second_band_color: Dict[str, float],
                header_color: Optional[Dict[str, float]] = None,
                apply_to: str = 'ROWS',
                ctx: Context = None) -> Dict[str, Any]:
    """
    Apply alternating row or column color bands over a range (addBanding).

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet: Name of the sheet (case-sensitive)
        range: Cell range in A1 notation (e.g., 'A1:D10')
        first_band_color: RGB dict (0-1 floats) for odd bands. Example: {"red": 1.0, "green": 1.0, "blue": 1.0}
        second_band_color: RGB dict (0-1 floats) for even bands.
        header_color: Optional RGB dict (0-1 floats) for the header row/column.
        apply_to: 'ROWS' (default) or 'COLUMNS'

    Returns:
        Dictionary with success status and banded_range_id
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet)
        range_info = _parse_row_col(range)

        band_properties = {
            "firstBandColor": first_band_color,
            "secondBandColor": second_band_color
        }

        if header_color is not None:
            band_properties["headerColor"] = header_color

        use_columns = apply_to.upper() == 'COLUMNS'
        properties_key = 'columnProperties' if use_columns else 'rowProperties'

        banded_range = {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": range_info['start_row'] - 1,
                "endRowIndex": range_info['end_row'],
                "startColumnIndex": range_info['start_col'] - 1,
                "endColumnIndex": range_info['end_col']
            },
            properties_key: band_properties
        }

        request_body = {
            "requests": [
                {
                    "addBanding": {
                        "bandedRange": banded_range
                    }
                }
            ]
        }

        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()

        replies = response.get('replies', [{}])
        banded_range_id = (
            replies[0]
            .get('addBanding', {})
            .get('bandedRange', {})
            .get('bandedRangeId')
        )

        return {
            "success": True,
            "message": f"Banding applied to {range}",
            "banded_range_id": banded_range_id,
            "apply_to": apply_to.upper()
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error adding banding: {str(e)}"
        }


@mcp.tool()
def remove_banding(spreadsheet_id: str,
                   banded_range_id: int,
                   ctx: Context = None) -> Dict[str, Any]:
    """
    Remove alternating color banding by its ID (deleteBanding).

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        banded_range_id: Integer ID of the banded range to delete

    Returns:
        Dictionary with success status and banded_range_id
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        request_body = {
            "requests": [
                {
                    "deleteBanding": {
                        "bandedRangeId": banded_range_id
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
            "message": f"Banding {banded_range_id} removed",
            "banded_range_id": banded_range_id
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error removing banding: {str(e)}"
        }
