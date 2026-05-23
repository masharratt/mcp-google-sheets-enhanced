"""
Data validation tools: set, list, and clear data validation rules.
"""

from typing import Dict, Any, Optional

from mcp.server.fastmcp import Context

from gsheets_mcp.core import mcp, _get_sheet_id, _parse_row_col


@mcp.tool()
def set_data_validation(spreadsheet_id: str,
                        sheet_name: str,
                        range: str,
                        validation_rule: Dict[str, Any],
                        ctx: Context = None) -> Dict[str, Any]:
    """
    Set data validation rule on cell range.

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet_name: Sheet name (case-sensitive)
        range: A1 range (e.g. "A1:C10")
        validation_rule: Dict with:
            - condition_type: 'NUMBER_BETWEEN', 'NUMBER_NOT_BETWEEN', 'TEXT_CONTAINS',
                'TEXT_NOT_CONTAINS', 'TEXT_EQ', 'TEXT_IS_VALID_URL', 'ONE_OF_RANGE', 'ONE_OF_LIST', 'NONE'
            - values: Condition values (NUMBER_BETWEEN takes 2; ONE_OF_LIST takes N; ONE_OF_RANGE takes range string)
            - strict: bool, reject invalid input (default False)
            - input_message: str, shown when cell selected
            - show_dropdown: bool, show dropdown for list validation (default True)
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)
        range_info = _parse_row_col(range)

        # Build the data validation rule
        condition_type = validation_rule.get('condition_type', 'NONE')
        values = validation_rule.get('values', [])

        condition = {
            'type': condition_type
        }

        # Add values based on condition type
        if condition_type in ['NUMBER_BETWEEN', 'NUMBER_NOT_BETWEEN'] and len(values) >= 2:
            condition['values'] = [
                {'userEnteredValue': str(values[0])},
                {'userEnteredValue': str(values[1])}
            ]
        elif condition_type in ['TEXT_EQ', 'TEXT_CONTAINS', 'TEXT_NOT_CONTAINS'] and values:
            condition['values'] = [
                {'userEnteredValue': str(values[0])}
            ]
        elif condition_type == 'ONE_OF_RANGE' and values:
            condition['values'] = [
                {'userEnteredValue': values[0]}  # Range like "Sheet1!A1:A10"
            ]
        elif condition_type == 'ONE_OF_LIST' and values:
            condition['values'] = [
                {'userEnteredValue': str(v)} for v in values
            ]

        # Create the data validation request
        request = {
            'setDataValidation': {
                'range': {
                    'sheetId': sheet_id,
                    'startRowIndex': range_info['start_row'] - 1,
                    'endRowIndex': range_info['end_row'],
                    'startColumnIndex': range_info['start_col'] - 1,
                    'endColumnIndex': range_info['end_col']
                },
                'rule': {
                    'condition': condition,
                    'inputMessage': validation_rule.get('input_message', ''),
                    'strict': validation_rule.get('strict', False),
                    'showCustomUi': validation_rule.get('show_dropdown', True)
                }
            }
        }

        body = {'requests': [request]}
        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body
        ).execute()

        return {
            "success": True,
            "message": f"Successfully set data validation for {sheet_name}!{range}",
            "validation_type": condition_type,
            "cells_covered": (range_info['end_row'] - range_info['start_row'] + 1) * \
                           (range_info['end_col'] - range_info['start_col'] + 1)
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error setting data validation: {str(e)}"
        }


@mcp.tool()
def list_validation_rules(spreadsheet_id: str,
                          sheet_name: str = None,
                          ctx: Context = None) -> Dict[str, Any]:
    """
    List data validation rules in sheet or spreadsheet.

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet_name: Sheet name (case-sensitive). Omit to return rules from all sheets.
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        if sheet_name:
            sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)
            ranges = [f"{sheet_name}!A1:ZZ"]
        else:
            ranges = []

        spreadsheet_metadata = sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            ranges=ranges,
            fields='sheets(data(rowData(values(dataValidation,formattedValue,userEnteredValue))),properties)'
        ).execute()

        validation_rules = []

        for sheet in spreadsheet_metadata.get('sheets', []):
            sheet_title = sheet['properties']['title']
            if sheet_name and sheet_title != sheet_name:
                continue

            sheet_data = sheet.get('data', [])
            for row_data in sheet_data:
                for row in row_data.get('rowData', []):
                    for cell in row.get('values', []):
                        if 'dataValidation' in cell:
                            validation_rules.append({
                                'sheet': sheet_title,
                                'cell_reference': f"Sheet row/column - {cell}",
                                'validation': cell['dataValidation']
                            })

        return {
            "success": True,
            "message": f"Found {len(validation_rules)} validation rules",
            "validation_rules": validation_rules
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error listing validation rules: {str(e)}"
        }


@mcp.tool()
def clear_data_validation(spreadsheet_id: str,
                          sheet_name: str,
                          range: str,
                          ctx: Context = None) -> Dict[str, Any]:
    """
    Clear data validation from cell range (setDataValidation with no rule).

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet_name: Sheet name (case-sensitive)
        range: A1 range (e.g. 'A1:C10')
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)
        range_info = _parse_row_col(range)

        # 'deleteDataValidation' is not a valid Sheets API request type.
        # The documented way to clear validation is setDataValidation with
        # the 'rule' key omitted entirely.
        request_body = {
            "requests": [
                {
                    "setDataValidation": {
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
            "message": f"Data validation cleared from {range}",
            "range": range
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error clearing data validation: {str(e)}"
        }
