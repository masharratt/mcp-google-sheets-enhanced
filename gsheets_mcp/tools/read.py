"""
Read tools: fetch data and metadata from Google Spreadsheets.
"""

from typing import Annotated, List, Dict, Any, Literal, Optional

from pydantic import Field

from mcp.server.fastmcp import Context

from gsheets_mcp.core import mcp


@mcp.tool()
def get_sheet_data(spreadsheet_id: str,
                   sheet: str,
                   range: Annotated[Optional[str], Field(description="A1 range, e.g. 'A1:C10'. Omit for all data.")] = None,
                   include_grid_data: Annotated[bool, Field(description="True includes cell formatting/metadata (much larger response). Default False returns values only.")] = False,
                   ctx: Context = None) -> Dict[str, Any]:
    """Get cell values (or full grid data) from a sheet; use batch_get_values for multiple ranges in one call."""
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    # Construct the range - keep original API behavior
    if range:
        full_range = f"{sheet}!{range}"
    else:
        full_range = sheet

    if include_grid_data:
        # Use full API to get all grid data including formatting
        result = sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            ranges=[full_range],
            includeGridData=True
        ).execute()
    else:
        # Use values API to get cell values only (more efficient)
        values_result = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=full_range
        ).execute()

        # Format the response to match expected structure
        result = {
            'spreadsheetId': spreadsheet_id,
            'valueRanges': [{
                'range': full_range,
                'values': values_result.get('values', [])
            }]
        }

    return result


@mcp.tool()
def get_sheet_formulas(spreadsheet_id: str,
                       sheet: str,
                       range: Annotated[Optional[str], Field(description="A1 range, e.g. 'A1:C10'. Omit for all formulas in sheet.")] = None,
                       ctx: Context = None) -> List[List[Any]]:
    """Get raw formula text (FORMULA render option) from a sheet instead of computed values."""
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    # Construct the range
    if range:
        full_range = f"{sheet}!{range}"
    else:
        full_range = sheet  # Get all formulas in the specified sheet

    # Call the Sheets API
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=full_range,
        valueRenderOption='FORMULA'  # Request formulas
    ).execute()

    # Get the formulas from the response
    formulas = result.get('values', [])
    return formulas


@mcp.tool()
def get_multiple_sheet_data(queries: Annotated[List[Dict[str, str]], Field(description='List of dicts with keys: spreadsheet_id, sheet, range. Example: [{"spreadsheet_id": "abc", "sheet": "Sheet1", "range": "A1:B5"}]')],
                            ctx: Context = None) -> List[Dict[str, Any]]:
    """Get data from multiple ranges across multiple spreadsheets; use batch_get_values for multiple ranges in one spreadsheet."""
    sheets_service = ctx.request_context.lifespan_context.sheets_service
    results = []

    for query in queries:
        spreadsheet_id = query.get('spreadsheet_id')
        sheet = query.get('sheet')
        range_str = query.get('range')

        if not all([spreadsheet_id, sheet, range_str]):
            results.append({**query, 'error': 'Missing required keys (spreadsheet_id, sheet, range)'})
            continue

        try:
            # Construct the range
            full_range = f"{sheet}!{range_str}"

            # Call the Sheets API
            result = sheets_service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=full_range
            ).execute()

            # Get the values from the response
            values = result.get('values', [])
            results.append({**query, 'data': values})

        except Exception as e:
            results.append({**query, 'error': str(e)})

    return results


@mcp.tool()
def get_multiple_spreadsheet_summary(spreadsheet_ids: List[str],
                                   rows_to_fetch: Annotated[int, Field(description="Rows to fetch per sheet including header (default 5)")] = 5,
                                   ctx: Context = None) -> List[Dict[str, Any]]:
    """Get a compact summary (title, sheet names, headers, first N rows) for multiple spreadsheets at once."""
    sheets_service = ctx.request_context.lifespan_context.sheets_service
    summaries = []

    for spreadsheet_id in spreadsheet_ids:
        summary_data = {
            'spreadsheet_id': spreadsheet_id,
            'title': None,
            'sheets': [],
            'error': None
        }
        try:
            # Get spreadsheet metadata
            spreadsheet = sheets_service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                fields='properties.title,sheets(properties(title,sheetId))'
            ).execute()

            summary_data['title'] = spreadsheet.get('properties', {}).get('title', 'Unknown Title')

            sheet_summaries = []
            for sheet in spreadsheet.get('sheets', []):
                sheet_title = sheet.get('properties', {}).get('title')
                sheet_id = sheet.get('properties', {}).get('sheetId')
                sheet_summary = {
                    'title': sheet_title,
                    'sheet_id': sheet_id,
                    'headers': [],
                    'first_rows': [],
                    'error': None
                }

                if not sheet_title:
                    sheet_summary['error'] = 'Sheet title not found'
                    sheet_summaries.append(sheet_summary)
                    continue

                try:
                    # Fetch the first few rows (e.g., A1:Z5)
                    # Adjust range if fewer rows are requested
                    max_row = max(1, rows_to_fetch) # Ensure at least 1 row is fetched
                    range_to_get = f"{sheet_title}!A1:{max_row}" # Fetch all columns up to max_row

                    result = sheets_service.spreadsheets().values().get(
                        spreadsheetId=spreadsheet_id,
                        range=range_to_get
                    ).execute()

                    values = result.get('values', [])

                    if values:
                        sheet_summary['headers'] = values[0]
                        if len(values) > 1:
                            sheet_summary['first_rows'] = values[1:max_row]
                    else:
                        # Handle empty sheets or sheets with less data than requested
                        sheet_summary['headers'] = []
                        sheet_summary['first_rows'] = []

                except Exception as sheet_e:
                    sheet_summary['error'] = f'Error fetching data for sheet {sheet_title}: {sheet_e}'

                sheet_summaries.append(sheet_summary)

            summary_data['sheets'] = sheet_summaries

        except Exception as e:
            summary_data['error'] = f'Error fetching spreadsheet {spreadsheet_id}: {e}'

        summaries.append(summary_data)

    return summaries


@mcp.tool()
def get_spreadsheet_metadata(spreadsheet_id: str,
                             include_sheet_properties: Annotated[bool, Field(description="True (default) includes per-sheet properties (sheetId, title, index, sheetType, hidden, gridProperties). False returns top-level properties only (title, locale, timeZone, autoRecalc, defaultFormat).")] = True,
                             ctx: Context = None) -> Dict[str, Any]:
    """Get spreadsheet-level metadata (title, locale, sheet list) without fetching cell data."""
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    if include_sheet_properties:
        fields = (
            'spreadsheetId,'
            'properties(title,locale,timeZone,autoRecalc,defaultFormat),'
            'sheets(properties(sheetId,title,index,sheetType,hidden,gridProperties))'
        )
    else:
        fields = 'spreadsheetId,properties(title,locale,timeZone,autoRecalc,defaultFormat)'

    result = sheets_service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields=fields
    ).execute()

    return result


@mcp.tool()
def batch_get_values(spreadsheet_id: str,
                     ranges: Annotated[List[str], Field(description="A1 range strings, e.g. ['Sheet1!A1:B5', 'Data!C1:C10']")],
                     value_render_option: Literal['FORMATTED_VALUE', 'UNFORMATTED_VALUE', 'FORMULA'] = 'FORMATTED_VALUE',
                     major_dimension: Literal['ROWS', 'COLUMNS'] = 'ROWS',
                     ctx: Context = None) -> List[Dict[str, Any]]:
    """Read multiple A1 ranges from one spreadsheet in a single batchGet; use get_multiple_sheet_data for cross-spreadsheet reads."""
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    response = sheets_service.spreadsheets().values().batchGet(
        spreadsheetId=spreadsheet_id,
        ranges=ranges,
        valueRenderOption=value_render_option,
        majorDimension=major_dimension
    ).execute()

    return [
        {
            'range': vr.get('range', ''),
            'values': vr.get('values', [])
        }
        for vr in response.get('valueRanges', [])
    ]


@mcp.tool()
def list_sheets(spreadsheet_id: str, ctx: Context = None) -> List[str]:
    """List all sheet tab names in a spreadsheet."""
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    # Get spreadsheet metadata
    spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()

    # Extract sheet names
    sheet_names = [sheet['properties']['title'] for sheet in spreadsheet['sheets']]

    return sheet_names
