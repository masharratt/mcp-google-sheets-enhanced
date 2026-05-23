"""
Format tools: apply cell, text, number formatting, borders, merge cells, move ranges, banding.
"""

from typing import Annotated, Dict, Any, Literal, Optional

from pydantic import Field
from mcp.server.fastmcp import Context

from gsheets_mcp.core import mcp, _get_sheet_id, _parse_row_col, _get_format_fields, _build_cell_format, _map_text_format_keys
from gsheets_mcp.builders import build_repeat_cell_request, build_merge_request, build_banding_request


@mcp.tool()
def apply_cell_formatting(spreadsheet_id: str,
                        sheet_name: str,
                        range: Annotated[str, Field(description="A1 range, e.g. 'A1:C10'")],
                        formatting: Annotated[Dict[str, Any], Field(description="Dict with any of: text_format {bold,italic,underline,strikethrough,font_family,font_size,foreground_color,background_color}, alignment {horizontal: LEFT|CENTER|RIGHT, vertical: TOP|MIDDLE|BOTTOM, wrap_strategy: OVERFLOW_CELL|CLIP|WRAP}, background_color {red,green,blue,alpha}, borders {top/bottom/left/right: {style,color}}, number_format {type,pattern}")],
                        ctx: Context = None) -> Dict[str, Any]:
    """Apply combined cell formatting to a range; prefer apply_text_formatting or add_cell_borders for single-concern edits."""
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
            grid_range = {
                'sheetId': _get_sheet_id(sheets_service, spreadsheet_id, sheet_name),
                'startRowIndex': range_info['start_row'] - 1,
                'endRowIndex': range_info['end_row'],
                'startColumnIndex': range_info['start_col'] - 1,
                'endColumnIndex': range_info['end_col'],
            }
            request = build_repeat_cell_request(
                grid_range=grid_range,
                cell_format=cell_format,
                fields=_get_format_fields(cell_format),
            )
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
                      range: Annotated[str, Field(description="A1 range, e.g. 'A1:C10'")],
                      number_format: Literal['TEXT', 'NUMBER', 'CURRENCY', 'PERCENT', 'DATE', 'TIME', 'DATE_TIME', 'SCIENTIFIC'],
                      pattern: Annotated[Optional[str], Field(description="Custom format pattern, e.g. '$#,##0.00'. Overrides number_format when provided.")] = None,
                      ctx: Context = None) -> Dict[str, Any]:
    """Set a built-in or custom number format on a cell range."""
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
                     range: Annotated[str, Field(description="A1 range, e.g. 'A1:C10'")],
                     borders: Annotated[Dict[str, Any], Field(description='Dict with any of top/bottom/left/right keys, each: {"style": "SOLID", "color": {"red": 0, "green": 0, "blue": 0}}. Styles: NONE, SOLID, SOLID_MEDIUM, SOLID_THICK, DOTTED, DASHED, DOUBLE')],
                     ctx: Context = None) -> Dict[str, Any]:
    """Add borders to a cell range; use this instead of apply_cell_formatting when only borders are needed."""
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
                          range: Annotated[str, Field(description="A1 range, e.g. 'A1:C10'")],
                          text_formatting: Annotated[Dict[str, Any], Field(description="Dict with any of: font_family (str), font_size (int), bold (bool), italic (bool), underline (bool), strikethrough (bool), foreground_color ({red,green,blue}), background_color ({red,green,blue}), horizontal_alignment (LEFT|CENTER|RIGHT), vertical_alignment (TOP|MIDDLE|BOTTOM), wrap_text (bool)")],
                          ctx: Context = None) -> Dict[str, Any]:
    """Apply font and text formatting to a cell range; use instead of apply_cell_formatting when only text style is needed."""
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
                range: Annotated[str, Field(description="A1 range, e.g. 'A1:C10'")],
                merge_type: Literal['MERGE_ALL', 'MERGE_COLUMNS', 'MERGE_ROWS', 'UNMERGE'] = "MERGE_ALL",
                ctx: Context = None) -> Dict[str, Any]:
    """Merge or unmerge a cell range; UNMERGE removes existing merges."""
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

        grid_range = {
            "sheetId": sheet_id,
            "startRowIndex": range_info['start_row'] - 1,
            "endRowIndex": range_info['end_row'],
            "startColumnIndex": range_info['start_col'] - 1,
            "endColumnIndex": range_info['end_col'],
        }
        request_body = {
            "requests": [
                build_merge_request(grid_range=grid_range, merge_type=actual_merge_type)
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
               source_range: Annotated[str, Field(description="A1 source range, e.g. 'A1:C10'")],
               destination: Annotated[Dict[str, Any], Field(description='Destination dict: {"sheetId": 0, "rowIndex": 5, "columnIndex": 2}')],
               ctx: Context = None) -> Dict[str, Any]:
    """Move a data range to a new row position via moveDimension."""
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
                range: Annotated[str, Field(description="A1 range, e.g. 'A1:D10'")],
                first_band_color: Annotated[Dict[str, float], Field(description='RGB float dict for odd bands, e.g. {"red": 1.0, "green": 1.0, "blue": 1.0}')],
                second_band_color: Annotated[Dict[str, float], Field(description="RGB float dict for even bands")],
                header_color: Optional[Dict[str, float]] = None,
                apply_to: Literal['ROWS', 'COLUMNS'] = 'ROWS',
                ctx: Context = None) -> Dict[str, Any]:
    """Apply alternating color bands (addBanding) over a range; choose ROWS or COLUMNS banding direction."""
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet)
        range_info = _parse_row_col(range)

        grid_range = {
            "sheetId": sheet_id,
            "startRowIndex": range_info['start_row'] - 1,
            "endRowIndex": range_info['end_row'],
            "startColumnIndex": range_info['start_col'] - 1,
            "endColumnIndex": range_info['end_col'],
        }
        request_body = {
            "requests": [
                build_banding_request(
                    grid_range=grid_range,
                    header_color=header_color,
                    first_band_color=first_band_color,
                    second_band_color=second_band_color,
                    apply_to=apply_to,
                )
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
    """Remove alternating color banding by its numeric ID (deleteBanding)."""
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
