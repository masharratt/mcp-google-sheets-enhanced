#!/usr/bin/env python
"""
Google Spreadsheet MCP Server
A Model Context Protocol (MCP) server built with FastMCP for interacting with Google Sheets.
"""

import base64
import os
import sys
from typing import List, Dict, Any, Optional, Union
import json
from dataclasses import dataclass
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

# MCP imports
from mcp.server.fastmcp import FastMCP, Context

# Google API imports
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import google.auth

# Constants
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
CREDENTIALS_CONFIG = os.environ.get('CREDENTIALS_CONFIG')
TOKEN_PATH = os.environ.get('TOKEN_PATH', 'token.json')
CREDENTIALS_PATH = os.environ.get('CREDENTIALS_PATH', 'credentials.json')
SERVICE_ACCOUNT_PATH = os.environ.get('SERVICE_ACCOUNT_PATH', 'service_account.json')
DRIVE_FOLDER_ID = os.environ.get('DRIVE_FOLDER_ID', '')  # Working directory in Google Drive

@dataclass
class SpreadsheetContext:
    """Context for Google Spreadsheet service"""
    sheets_service: Any
    drive_service: Any
    folder_id: Optional[str] = None


@asynccontextmanager
async def spreadsheet_lifespan(server: FastMCP) -> AsyncIterator[SpreadsheetContext]:
    """Manage Google Spreadsheet API connection lifecycle"""
    # Authenticate and build the service
    creds = None

    if CREDENTIALS_CONFIG:
        creds = service_account.Credentials.from_service_account_info(json.loads(base64.b64decode(CREDENTIALS_CONFIG)), scopes=SCOPES)
    
    # Check for explicit service account authentication first (custom SERVICE_ACCOUNT_PATH)
    if not creds and SERVICE_ACCOUNT_PATH and os.path.exists(SERVICE_ACCOUNT_PATH):
        try:
            # Regular service account authentication
            creds = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_PATH,
                scopes=SCOPES
            )
            print("Using service account authentication")
            print(f"Working with Google Drive folder ID: {DRIVE_FOLDER_ID or 'Not specified'}")
        except Exception as e:
            print(f"Error using service account authentication: {e}")
            creds = None
    
    # Fall back to OAuth flow if service account auth failed or not configured
    if not creds:
        print("Trying OAuth authentication flow")
        if os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, 'r') as token:
                creds = Credentials.from_authorized_user_info(json.load(token), SCOPES)
                
        # If credentials are not valid or don't exist, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
                    creds = flow.run_local_server(port=0)
                    
                    # Save the credentials for the next run
                    with open(TOKEN_PATH, 'w') as token:
                        token.write(creds.to_json())
                    print("Successfully authenticated using OAuth flow")
                except Exception as e:
                    print(f"Error with OAuth flow: {e}")
                    creds = None
    
    # Try Application Default Credentials if no creds thus far
    # This will automatically check GOOGLE_APPLICATION_CREDENTIALS, gcloud auth, and metadata service
    if not creds:
        try:
            print("Attempting to use Application Default Credentials (ADC)")
            print("ADC will check: GOOGLE_APPLICATION_CREDENTIALS, gcloud auth, and metadata service")
            creds, project = google.auth.default(
                scopes=SCOPES
            )
            print(f"Successfully authenticated using ADC for project: {project}")
        except Exception as e:
            print(f"Error using Application Default Credentials: {e}")
            raise Exception("All authentication methods failed. Please configure credentials.")
    
    # Build the services
    sheets_service = build('sheets', 'v4', credentials=creds)
    drive_service = build('drive', 'v3', credentials=creds)
    
    try:
        # Provide the service in the context
        yield SpreadsheetContext(
            sheets_service=sheets_service,
            drive_service=drive_service,
            folder_id=DRIVE_FOLDER_ID if DRIVE_FOLDER_ID else None
        )
    finally:
        # No explicit cleanup needed for Google APIs
        pass


# Initialize the MCP server with lifespan management
# Resolve host/port from environment variables with flexible names
_resolved_host = os.environ.get('HOST') or os.environ.get('FASTMCP_HOST') or "0.0.0.0"
_resolved_port_str = os.environ.get('PORT') or os.environ.get('FASTMCP_PORT') or "8000"
try:
    _resolved_port = int(_resolved_port_str)
except ValueError:
    _resolved_port = 8000

# Initialize the MCP server with explicit host/port to ensure binding as configured
mcp = FastMCP("Google Spreadsheet",
              dependencies=["google-auth", "google-auth-oauthlib", "google-api-python-client"],
              lifespan=spreadsheet_lifespan,
              host=_resolved_host,
              port=_resolved_port)


@mcp.tool()
def get_sheet_data(spreadsheet_id: str, 
                   sheet: str,
                   range: Optional[str] = None,
                   include_grid_data: bool = False,
                   ctx: Context = None) -> Dict[str, Any]:
    """
    Get data from a specific sheet in a Google Spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the spreadsheet (found in the URL)
        sheet: The name of the sheet
        range: Optional cell range in A1 notation (e.g., 'A1:C10'). If not provided, gets all data.
        include_grid_data: If True, includes cell formatting and other metadata in the response.
            Note: Setting this to True will significantly increase the response size and token usage
            when parsing the response, as it includes detailed cell formatting information.
            Default is False (returns values only, more efficient).
    
    Returns:
        Grid data structure with either full metadata or just values from Google Sheets API, depending on include_grid_data parameter
    """
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
                       range: Optional[str] = None,
                       ctx: Context = None) -> List[List[Any]]:
    """
    Get formulas from a specific sheet in a Google Spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the spreadsheet (found in the URL)
        sheet: The name of the sheet
        range: Optional cell range in A1 notation (e.g., 'A1:C10'). If not provided, gets all formulas from the sheet.
    
    Returns:
        A 2D array of the sheet formulas.
    """
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
def update_cells(spreadsheet_id: str,
                sheet: str,
                range: str,
                data: List[List[Any]],
                ctx: Context = None) -> Dict[str, Any]:
    """
    Update cells in a Google Spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the spreadsheet (found in the URL)
        sheet: The name of the sheet
        range: Cell range in A1 notation (e.g., 'A1:C10')
        data: 2D array of values to update
    
    Returns:
        Result of the update operation
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service
    
    # Construct the range
    full_range = f"{sheet}!{range}"
    
    # Prepare the value range object
    value_range_body = {
        'values': data
    }
    
    # Call the Sheets API to update values
    result = sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=full_range,
        valueInputOption='USER_ENTERED',
        body=value_range_body
    ).execute()
    
    return result


@mcp.tool()
def batch_update_cells(spreadsheet_id: str,
                       sheet: str,
                       ranges: Dict[str, List[List[Any]]],
                       ctx: Context = None) -> Dict[str, Any]:
    """
    Batch update multiple ranges in a Google Spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the spreadsheet (found in the URL)
        sheet: The name of the sheet
        ranges: Dictionary mapping range strings to 2D arrays of values
               e.g., {'A1:B2': [[1, 2], [3, 4]], 'D1:E2': [['a', 'b'], ['c', 'd']]}
    
    Returns:
        Result of the batch update operation
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service
    
    # Prepare the batch update request
    data = []
    for range_str, values in ranges.items():
        full_range = f"{sheet}!{range_str}"
        data.append({
            'range': full_range,
            'values': values
        })
    
    batch_body = {
        'valueInputOption': 'USER_ENTERED',
        'data': data
    }
    
    # Call the Sheets API to perform batch update
    result = sheets_service.spreadsheets().values().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=batch_body
    ).execute()
    
    return result


@mcp.tool()
def add_rows(spreadsheet_id: str,
             sheet: str,
             count: int,
             start_row: Optional[int] = None,
             ctx: Context = None) -> Dict[str, Any]:
    """
    Add rows to a sheet in a Google Spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the spreadsheet (found in the URL)
        sheet: The name of the sheet
        count: Number of rows to add
        start_row: 0-based row index to start adding. If not provided, adds at the beginning.
    
    Returns:
        Result of the operation
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
    Add columns to a sheet in a Google Spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the spreadsheet (found in the URL)
        sheet: The name of the sheet
        count: Number of columns to add
        start_column: 0-based column index to start adding. If not provided, adds at the beginning.
    
    Returns:
        Result of the operation
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
def list_sheets(spreadsheet_id: str, ctx: Context = None) -> List[str]:
    """
    List all sheets in a Google Spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the spreadsheet (found in the URL)
    
    Returns:
        List of sheet names
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service
    
    # Get spreadsheet metadata
    spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    
    # Extract sheet names
    sheet_names = [sheet['properties']['title'] for sheet in spreadsheet['sheets']]
    
    return sheet_names


@mcp.tool()
def copy_sheet(src_spreadsheet: str,
               src_sheet: str,
               dst_spreadsheet: str,
               dst_sheet: str,
               ctx: Context = None) -> Dict[str, Any]:
    """
    Copy a sheet from one spreadsheet to another.
    
    Args:
        src_spreadsheet: Source spreadsheet ID
        src_sheet: Source sheet name
        dst_spreadsheet: Destination spreadsheet ID
        dst_sheet: Destination sheet name
    
    Returns:
        Result of the operation
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service
    
    # Get source sheet ID
    src = sheets_service.spreadsheets().get(spreadsheetId=src_spreadsheet).execute()
    src_sheet_id = None
    
    for s in src['sheets']:
        if s['properties']['title'] == src_sheet:
            src_sheet_id = s['properties']['sheetId']
            break
            
    if src_sheet_id is None:
        return {"error": f"Source sheet '{src_sheet}' not found"}
    
    # Copy the sheet to destination spreadsheet
    copy_result = sheets_service.spreadsheets().sheets().copyTo(
        spreadsheetId=src_spreadsheet,
        sheetId=src_sheet_id,
        body={
            "destinationSpreadsheetId": dst_spreadsheet
        }
    ).execute()
    
    # If destination sheet name is different from the default copied name, rename it
    if 'title' in copy_result and copy_result['title'] != dst_sheet:
        # Get the ID of the newly copied sheet
        copy_sheet_id = copy_result['sheetId']
        
        # Rename the copied sheet
        rename_request = {
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": copy_sheet_id,
                            "title": dst_sheet
                        },
                        "fields": "title"
                    }
                }
            ]
        }
        
        rename_result = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=dst_spreadsheet,
            body=rename_request
        ).execute()
        
        return {
            "copy": copy_result,
            "rename": rename_result
        }
    
    return {"copy": copy_result}


@mcp.tool()
def rename_sheet(spreadsheet: str,
                 sheet: str,
                 new_name: str,
                 ctx: Context = None) -> Dict[str, Any]:
    """
    Rename a sheet in a Google Spreadsheet.
    
    Args:
        spreadsheet: Spreadsheet ID
        sheet: Current sheet name
        new_name: New sheet name
    
    Returns:
        Result of the operation
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service
    
    # Get sheet ID
    spreadsheet_data = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet).execute()
    sheet_id = None
    
    for s in spreadsheet_data['sheets']:
        if s['properties']['title'] == sheet:
            sheet_id = s['properties']['sheetId']
            break
            
    if sheet_id is None:
        return {"error": f"Sheet '{sheet}' not found"}
    
    # Prepare the rename request
    request_body = {
        "requests": [
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "title": new_name
                    },
                    "fields": "title"
                }
            }
        ]
    }
    
    # Execute the request
    result = sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet,
        body=request_body
    ).execute()
    
    return result


@mcp.tool()
def get_multiple_sheet_data(queries: List[Dict[str, str]], 
                            ctx: Context = None) -> List[Dict[str, Any]]:
    """
    Get data from multiple specific ranges in Google Spreadsheets.
    
    Args:
        queries: A list of dictionaries, each specifying a query. 
                 Each dictionary should have 'spreadsheet_id', 'sheet', and 'range' keys.
                 Example: [{'spreadsheet_id': 'abc', 'sheet': 'Sheet1', 'range': 'A1:B5'}, 
                           {'spreadsheet_id': 'xyz', 'sheet': 'Data', 'range': 'C1:C10'}]
    
    Returns:
        A list of dictionaries, each containing the original query parameters 
        and the fetched 'data' or an 'error'.
    """
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
                                   rows_to_fetch: int = 5, 
                                   ctx: Context = None) -> List[Dict[str, Any]]:
    """
    Get a summary of multiple Google Spreadsheets, including sheet names, 
    headers, and the first few rows of data for each sheet.
    
    Args:
        spreadsheet_ids: A list of spreadsheet IDs to summarize.
        rows_to_fetch: The number of rows (including header) to fetch for the summary (default: 5).
    
    Returns:
        A list of dictionaries, each representing a spreadsheet summary. 
        Includes spreadsheet title, sheet summaries (title, headers, first rows), or an error.
    """
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


@mcp.resource("spreadsheet://{spreadsheet_id}/info")
def get_spreadsheet_info(spreadsheet_id: str) -> str:
    """
    Get basic information about a Google Spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the spreadsheet
    
    Returns:
        JSON string with spreadsheet information
    """
    # Access the context through mcp.get_lifespan_context() for resources
    context = mcp.get_lifespan_context()
    sheets_service = context.sheets_service
    
    # Get spreadsheet metadata
    spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    
    # Extract relevant information
    info = {
        "title": spreadsheet.get('properties', {}).get('title', 'Unknown'),
        "sheets": [
            {
                "title": sheet['properties']['title'],
                "sheetId": sheet['properties']['sheetId'],
                "gridProperties": sheet['properties'].get('gridProperties', {})
            }
            for sheet in spreadsheet.get('sheets', [])
        ]
    }
    
    return json.dumps(info, indent=2)


@mcp.tool()
def create_spreadsheet(title: str, folder_id: Optional[str] = None, ctx: Context = None) -> Dict[str, Any]:
    """
    Create a new Google Spreadsheet.
    
    Args:
        title: The title of the new spreadsheet
        folder_id: Optional Google Drive folder ID where the spreadsheet should be created.
                  If not provided, uses the configured default folder or creates in root.
    
    Returns:
        Information about the newly created spreadsheet including its ID
    """
    drive_service = ctx.request_context.lifespan_context.drive_service
    # Use provided folder_id or fall back to configured default
    target_folder_id = folder_id or ctx.request_context.lifespan_context.folder_id

    # Create the spreadsheet
    file_body = {
        'name': title,
        'mimeType': 'application/vnd.google-apps.spreadsheet',
    }
    if target_folder_id:
        file_body['parents'] = [target_folder_id]
    
    spreadsheet = drive_service.files().create(
        supportsAllDrives=True,
        body=file_body,
        fields='id, name, parents'
    ).execute()

    spreadsheet_id = spreadsheet.get('id')
    parents = spreadsheet.get('parents')
    folder_info = f" in folder {target_folder_id}" if target_folder_id else " in root"
    print(f"Spreadsheet created with ID: {spreadsheet_id}{folder_info}")

    return {
        'spreadsheetId': spreadsheet_id,
        'title': spreadsheet.get('name', title),
        'folder': parents[0] if parents else 'root',
    }


@mcp.tool()
def create_sheet(spreadsheet_id: str, 
                title: str, 
                ctx: Context = None) -> Dict[str, Any]:
    """
    Create a new sheet tab in an existing Google Spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the spreadsheet
        title: The title for the new sheet
    
    Returns:
        Information about the newly created sheet
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service
    
    # Define the add sheet request
    request_body = {
        "requests": [
            {
                "addSheet": {
                    "properties": {
                        "title": title
                    }
                }
            }
        ]
    }
    
    # Execute the request
    result = sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=request_body
    ).execute()
    
    # Extract the new sheet information
    new_sheet_props = result['replies'][0]['addSheet']['properties']
    
    return {
        'sheetId': new_sheet_props['sheetId'],
        'title': new_sheet_props['title'],
        'index': new_sheet_props.get('index'),
        'spreadsheetId': spreadsheet_id
    }


@mcp.tool()
def list_spreadsheets(folder_id: Optional[str] = None, ctx: Context = None) -> List[Dict[str, str]]:
    """
    List all spreadsheets in the specified Google Drive folder.
    If no folder is specified, uses the configured default folder or lists from 'My Drive'.
    
    Args:
        folder_id: Optional Google Drive folder ID to search in.
                  If not provided, uses the configured default folder or searches 'My Drive'.
    
    Returns:
        List of spreadsheets with their ID and title
    """
    drive_service = ctx.request_context.lifespan_context.drive_service
    # Use provided folder_id or fall back to configured default
    target_folder_id = folder_id or ctx.request_context.lifespan_context.folder_id
    
    query = "mimeType='application/vnd.google-apps.spreadsheet'"
    
    # If a specific folder is provided or configured, search only in that folder
    if target_folder_id:
        query += f" and '{target_folder_id}' in parents"
        print(f"Searching for spreadsheets in folder: {target_folder_id}")
    else:
        print("Searching for spreadsheets in 'My Drive'")
    
    # List spreadsheets
    results = drive_service.files().list(
        q=query,
        spaces='drive',
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        fields='files(id, name)',
        orderBy='modifiedTime desc'
    ).execute()
    
    spreadsheets = results.get('files', [])
    
    return [{'id': sheet['id'], 'title': sheet['name']} for sheet in spreadsheets]


@mcp.tool()
def share_spreadsheet(spreadsheet_id: str, 
                      recipients: List[Dict[str, str]],
                      send_notification: bool = True,
                      ctx: Context = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Share a Google Spreadsheet with multiple users via email, assigning specific roles.
    
    Args:
        spreadsheet_id: The ID of the spreadsheet to share.
        recipients: A list of dictionaries, each containing 'email_address' and 'role'.
                    The role should be one of: 'reader', 'commenter', 'writer'.
                    Example: [
                        {'email_address': 'user1@example.com', 'role': 'writer'},
                        {'email_address': 'user2@example.com', 'role': 'reader'}
                    ]
        send_notification: Whether to send a notification email to the users. Defaults to True.

    Returns:
        A dictionary containing lists of 'successes' and 'failures'. 
        Each item in the lists includes the email address and the outcome.
    """
    drive_service = ctx.request_context.lifespan_context.drive_service
    successes = []
    failures = []
    
    for recipient in recipients:
        email_address = recipient.get('email_address')
        role = recipient.get('role', 'writer') # Default to writer if role is missing for an entry
        
        if not email_address:
            failures.append({
                'email_address': None,
                'error': 'Missing email_address in recipient entry.'
            })
            continue
            
        if role not in ['reader', 'commenter', 'writer']:
             failures.append({
                'email_address': email_address,
                'error': f"Invalid role '{role}'. Must be 'reader', 'commenter', or 'writer'."
            })
             continue

        permission = {
            'type': 'user',
            'role': role,
            'emailAddress': email_address
        }
        
        try:
            result = drive_service.permissions().create(
                fileId=spreadsheet_id,
                body=permission,
                sendNotificationEmail=send_notification,
                fields='id'
            ).execute()
            successes.append({
                'email_address': email_address, 
                'role': role, 
                'permissionId': result.get('id')
            })
        except Exception as e:
            # Try to provide a more informative error message
            error_details = str(e)
            if hasattr(e, 'content'):
                try:
                    error_content = json.loads(e.content)
                    error_details = error_content.get('error', {}).get('message', error_details)
                except json.JSONDecodeError:
                    pass # Keep the original error string
            failures.append({
                'email_address': email_address,
                'error': f"Failed to share: {error_details}"
            })
            
    return {"successes": successes, "failures": failures}


@mcp.tool()
def list_folders(parent_folder_id: Optional[str] = None, ctx: Context = None) -> List[Dict[str, str]]:
    """
    List all folders in the specified Google Drive folder.
    If no parent folder is specified, lists folders from 'My Drive' root.
    
    Args:
        parent_folder_id: Optional Google Drive folder ID to search within.
                         If not provided, searches the root of 'My Drive'.
    
    Returns:
        List of folders with their ID, name, and parent information
    """
    drive_service = ctx.request_context.lifespan_context.drive_service
    
    query = "mimeType='application/vnd.google-apps.folder'"
    
    # If a specific parent folder is provided, search only within that folder
    if parent_folder_id:
        query += f" and '{parent_folder_id}' in parents"
        print(f"Searching for folders in parent folder: {parent_folder_id}")
    else:
        # Search in root of My Drive (folders that don't have any parent folders)
        query += " and 'root' in parents"
        print("Searching for folders in 'My Drive' root")
    
    # List folders
    results = drive_service.files().list(
        q=query,
        spaces='drive',
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        fields='files(id, name, parents)',
        orderBy='name'
    ).execute()
    
    folders = results.get('files', [])
    
    return [
        {
            'id': folder['id'], 
            'name': folder['name'],
            'parent': folder.get('parents', ['root'])[0] if folder.get('parents') else 'root'
        } 
        for folder in folders
    ]


# ===== Enhanced Cell Formatting Tools =====

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

        # Text formatting
        if 'text_format' in formatting:
            cell_format['textFormat'] = formatting['text_format']

        # Alignment
        if 'alignment' in formatting:
            cell_format.update(formatting['alignment'])

        # Background color
        if 'background_color' in formatting:
            cell_format['backgroundColor'] = formatting['background_color']

        # Borders
        if 'borders' in formatting:
            cell_format['borders'] = formatting['borders']

        # Number format
        if 'number_format' in formatting:
            cell_format['numberFormat'] = formatting['number_format']

        # Create the repeat cell request
        if cell_format:
            request = {
                'repeatCell': {
                    'range': {
                        'sheetId': _get_sheet_id(sheets_service, spreadsheet_id, sheet_name),
                        'startRowIndex': _parse_row_col(range)['start_row'] - 1,
                        'endRowIndex': _parse_row_col(range)['end_row'],
                        'startColumnIndex': _parse_row_col(range)['start_col'] - 1,
                        'endColumnIndex': _parse_row_col(range)['end_col']
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


# Maps this tool's legacy lowercase condition aliases to valid Google
# Sheets BooleanCondition.type enums. Real Google enums pass through
# unchanged (see _normalize_condition_type).
_CONDITION_TYPE_ALIASES = {
    'greater_than': 'NUMBER_GREATER',
    'greater_than_or_equal': 'NUMBER_GREATER_THAN_EQ',
    'less_than': 'NUMBER_LESS',
    'less_than_or_equal': 'NUMBER_LESS_THAN_EQ',
    'equal_to': 'NUMBER_EQ',
    'not_equal_to': 'NUMBER_NOT_EQ',
    'between': 'NUMBER_BETWEEN',
    'not_between': 'NUMBER_NOT_BETWEEN',
    'text_contains': 'TEXT_CONTAINS',
    'text_not_contains': 'TEXT_NOT_CONTAINS',
    'text_equal': 'TEXT_EQ',
    'text_starts_with': 'TEXT_STARTS_WITH',
    'text_ends_with': 'TEXT_ENDS_WITH',
    'date_before': 'DATE_BEFORE',
    'date_after': 'DATE_AFTER',
    'formula_custom': 'CUSTOM_FORMULA',
    'is_blank': 'BLANK',
    'is_not_blank': 'NOT_BLANK',
}

# Google BooleanCondition.type values that take ZERO ConditionValues.
_ZERO_VALUE_CONDITIONS = {
    'BLANK', 'NOT_BLANK', 'IS_EMPTY', 'TEXT_IS_EMAIL', 'TEXT_IS_URL',
    'DATE_IS_VALID',
}

# Conditions that take exactly TWO ConditionValues.
_TWO_VALUE_CONDITIONS = {'NUMBER_BETWEEN', 'NUMBER_NOT_BETWEEN', 'DATE_BETWEEN'}


def _normalize_condition_type(condition_type: str) -> str:
    """Map a condition_type to a valid Google BooleanCondition.type enum.

    Accepts both this tool's legacy lowercase aliases ("less_than") and the
    real Google enum strings ("NUMBER_LESS"). Unknown values are upper-cased
    and passed through so new Google enums work without a code change.
    """
    if not condition_type:
        return condition_type
    key = condition_type.strip()
    if key in _CONDITION_TYPE_ALIASES:
        return _CONDITION_TYPE_ALIASES[key]
    lowered = key.lower()
    if lowered in _CONDITION_TYPE_ALIASES:
        return _CONDITION_TYPE_ALIASES[lowered]
    # Already a Google enum (or an unknown one) -> pass through upper-cased.
    return key.upper()


def _build_condition_values(google_type: str, values: List[Any]) -> List[Dict[str, str]]:
    """Build a Google ConditionValue list: [{'userEnteredValue': '<raw>'}, ...].

    No extra quoting. Zero-value conditions return []; two-value conditions
    (NUMBER_BETWEEN, etc.) use the first two values; everything else uses one.
    """
    if google_type in _ZERO_VALUE_CONDITIONS:
        return []
    if not values:
        return []
    if google_type in _TWO_VALUE_CONDITIONS:
        return [{'userEnteredValue': str(v)} for v in values[:2]]
    # Single-value conditions (incl. CUSTOM_FORMULA, which expects the
    # formula string as its sole ConditionValue).
    return [{'userEnteredValue': str(values[0])}]


def _build_gradient_rule(gradient_spec: Dict[str, Any]) -> Dict[str, Any]:
    """Build a Google GradientRule (color-scale / heatmap) dict.

    gradient_spec keys: minpoint, midpoint (optional), maxpoint. Each is an
    InterpolationPoint: {color: {red,green,blue[,alpha]}, type: <PointType>,
    value: <str optional>}. PointType: MIN, MAX, NUMBER, PERCENT, PERCENTILE.
    """
    def _point(p: Dict[str, Any]) -> Dict[str, Any]:
        point: Dict[str, Any] = {}
        if 'color' in p:
            point['color'] = p['color']
        if p.get('type'):
            point['type'] = str(p['type']).upper()
        if p.get('value') is not None:
            point['value'] = str(p['value'])
        return point

    rule: Dict[str, Any] = {}
    if 'minpoint' in gradient_spec:
        rule['minpoint'] = _point(gradient_spec['minpoint'])
    if 'midpoint' in gradient_spec and gradient_spec['midpoint']:
        rule['midpoint'] = _point(gradient_spec['midpoint'])
    if 'maxpoint' in gradient_spec:
        rule['maxpoint'] = _point(gradient_spec['maxpoint'])
    return rule


@mcp.tool()
def apply_conditional_formatting(spreadsheet_id: str,
                                sheet_name: str,
                                range: str,
                                rules: List[Dict[str, Any]],
                                ctx: Context = None) -> Dict[str, Any]:
    """
    Apply conditional formatting rules to a cell range.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        range: Cell range in A1 notation (e.g., "A1:C10")
        rules: List of conditional formatting rules. Two kinds are supported.

            BOOLEAN rules (highlight cells matching a condition):
            - condition_type: a Google BooleanCondition.type enum
                (NUMBER_LESS, NUMBER_LESS_THAN_EQ, NUMBER_GREATER,
                 NUMBER_GREATER_THAN_EQ, NUMBER_EQ, NUMBER_BETWEEN,
                 TEXT_CONTAINS, TEXT_NOT_CONTAINS, TEXT_EQ, TEXT_STARTS_WITH,
                 TEXT_ENDS_WITH, DATE_BEFORE, DATE_AFTER, CUSTOM_FORMULA,
                 NOT_BLANK, BLANK, ...). Legacy lowercase aliases
                 ("less_than", "greater_than", "equal_to", "text_contains",
                 "text_starts_with", "text_ends_with", "between",
                 "formula_custom") are also accepted and mapped.
            - values: List of raw values for the condition. Single-value
                conditions take one; NUMBER_BETWEEN takes two; CUSTOM_FORMULA
                takes the formula string (e.g. "=$M1<0"); BLANK/NOT_BLANK take
                none.
            - format: Dict with formatting to apply when condition is met
                * text_format: font styling
                * background_color: cell background color
                * borders: border formatting

            GRADIENT / color-scale rules (heatmaps): pass a 'gradient' (or
            'color_scale') key on the rule instead of condition_type. Each
            interpolation point is {color: {red,green,blue}, type: <PointType>,
            value: <str>} where PointType is MIN/MAX/NUMBER/PERCENT/PERCENTILE.
            Shape: {"minpoint": {...}, "midpoint": {...}, "maxpoint": {...}}.
            midpoint is optional.
    Returns:
        Dictionary with success status and applied rules count
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)
        range_info = _parse_row_col(range)

        # Create conditional format rules
        conditional_format_rules = []

        for i, rule in enumerate(rules):
            condition_type = rule.get('condition_type')
            values = rule.get('values', [])
            format_to_apply = rule.get('format', {})

            ranges = [{
                'sheetId': sheet_id,
                'startRowIndex': range_info['start_row'] - 1,
                'endRowIndex': range_info['end_row'],
                'startColumnIndex': range_info['start_col'] - 1,
                'endColumnIndex': range_info['end_col']
            }]

            # Gradient / color-scale rule (heatmaps). Triggered by a
            # 'gradient' or 'color_scale' key on the rule instead of a
            # boolean condition_type.
            gradient_spec = rule.get('gradient') or rule.get('color_scale')
            if gradient_spec:
                gradient_rule = _build_gradient_rule(gradient_spec)
                conditional_format_rules.append({
                    'ranges': ranges,
                    'gradientRule': gradient_rule
                })
                continue

            # Boolean rule. Normalize condition_type to a valid Google
            # BooleanCondition.type enum (accepts both this tool's legacy
            # lowercase aliases and real Google enum strings).
            google_type = _normalize_condition_type(condition_type)
            condition = {'type': google_type}

            # Build ConditionValue list as {'userEnteredValue': '<raw>'}.
            # No extra quoting. Zero-value conditions (BLANK/NOT_BLANK/
            # IS_EMPTY/etc.) carry no values; NUMBER_BETWEEN carries two.
            condition_values = _build_condition_values(google_type, values)
            if condition_values:
                condition['values'] = condition_values

            conditional_format_rule = {
                'ranges': ranges,
                'booleanRule': {
                    'condition': condition,
                    'format': _build_cell_format(format_to_apply)
                }
            }

            conditional_format_rules.append(conditional_format_rule)

        # Add the conditional formatting rules
        requests = [{
            'addConditionalFormatRule': {
                'index': 0,  # Insert at the beginning
                'rule': rule
            }
        } for rule in conditional_format_rules]

        body = {'requests': requests}
        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body
        ).execute()

        return {
            "success": True,
            "message": f"Successfully applied {len(conditional_format_rules)} conditional formatting rules to {sheet_name}!{range}",
            "rules_applied": len(conditional_format_rules)
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error applying conditional formatting: {str(e)}"
        }


@mcp.tool()
def set_data_validation(spreadsheet_id: str,
                        sheet_name: str,
                        range: str,
                        validation_rule: Dict[str, Any],
                        ctx: Context = None) -> Dict[str, Any]:
    """
    Set data validation rules for a cell range.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        range: Cell range in A1 notation (e.g., "A1:C10")
        validation_rule: Dictionary containing validation settings:
            - condition_type: "NUMBER_BETWEEN", "NUMBER_NOT_BETWEEN", "TEXT_CONTAINS",
                            "TEXT_NOT_CONTAINS", "TEXT_EQ", "TEXT_IS_VALID_URL",
                            "ONE_OF_RANGE", "ONE_OF_LIST", "NONE"
            - values: List of values for the validation condition
            - strict: bool - whether to reject invalid input
            - input_message: str - message to show when cell is selected
            - show_dropdown: bool - show dropdown for list validation

    Returns:
        Dictionary with success status and validation details
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
def protect_sheet_range(spreadsheet_id: str,
                        sheet_name: str,
                        range: str = None,
                        protection_description: str = None,
                        warning_only: bool = True,
                        requesting_users_can_edit: bool = False,
                        editor_emails: List[str] = None,
                        ctx: Context = None) -> Dict[str, Any]:
    """
    Protect a sheet or specific range from editing.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        range: Optional cell range in A1 notation. If not provided, protects entire sheet
        protection_description: Description of what is being protected
        warning_only: bool - if True, show warning instead of blocking edits
        requesting_users_can_edit: bool - if True, user who requested protection can edit
        editor_emails: List of email addresses that can edit the protected range

    Returns:
        Dictionary with success status and protection ID
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)

        # Build the protected range request
        protected_range = {
            'warningOnly': warning_only,
            'description': protection_description or f"Protected {sheet_name}"
        }

        # Add range if specified
        if range:
            range_info = _parse_row_col(range)
            protected_range['range'] = {
                'sheetId': sheet_id,
                'startRowIndex': range_info['start_row'] - 1,
                'endRowIndex': range_info['end_row'],
                'startColumnIndex': range_info['start_col'] - 1,
                'endColumnIndex': range_info['end_col']
            }
        else:
            # Protect entire sheet
            protected_range['range'] = {
                'sheetId': sheet_id
            }

        # Add editors if specified
        if editor_emails:
            protected_range['editors'] = {
                'users': editor_emails,
                'domainUsersCanEdit': False
            }

        # Create the protection request
        request = {
            'addProtectedRange': {
                'protectedRange': protected_range
            }
        }

        body = {'requests': [request]}
        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body
        ).execute()

        # Extract the protection ID from response
        protection_id = None
        if 'replies' in response and response['replies']:
            protection_id = response['replies'][0]['addProtectedRange']['protectedRange']['protectedRangeId']

        return {
            "success": True,
            "message": f"Successfully protected {range if range else 'entire sheet'} in {sheet_name}",
            "protection_id": str(protection_id) if protection_id else "Created successfully",
            "warning_only": warning_only
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error setting protection: {str(e)}"
        }


# ===== Helper Functions for Enhanced Formatting =====

def _get_sheet_id(sheets_service, spreadsheet_id: str, sheet_name: str) -> int:
    """Get the sheet ID from sheet name."""
    try:
        sheet_metadata = sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields='sheets.properties'
        ).execute()

        for sheet in sheet_metadata.get('sheets', []):
            if sheet['properties']['title'] == sheet_name:
                return sheet['properties']['sheetId']

        raise ValueError(f"Sheet '{sheet_name}' not found in spreadsheet")
    except Exception as e:
        raise ValueError(f"Error getting sheet ID: {str(e)}")


def _parse_row_col(range_str: str) -> Dict[str, int]:
    """Parse A1 notation range to row/column indices."""
    import re

    # Parse range like "A1:C10" or "A1:A1"
    match = re.match(r'^([A-Z]+)(\d+):([A-Z]+)(\d+)$', range_str.upper())
    if not match:
        raise ValueError(f"Invalid range format: {range_str}")

    start_col = _col_to_num(match.group(1))
    start_row = int(match.group(2))
    end_col = _col_to_num(match.group(3))
    end_row = int(match.group(4))

    return {
        'start_col': start_col,
        'start_row': start_row,
        'end_col': end_col,
        'end_row': end_row
    }


def _col_to_num(col: str) -> int:
    """Convert column letter to number (A=1, B=2, etc.)."""
    result = 0
    for c in col:
        result = result * 26 + (ord(c) - ord('A') + 1)
    return result


def _get_format_fields(cell_format: Dict[str, Any]) -> List[str]:
    """Get list of format field names for batch update."""
    field_mapping = {
        'textFormat': ['textFormat'],
        'backgroundColor': ['backgroundColor'],
        'horizontalAlignment': ['horizontalAlignment'],
        'verticalAlignment': ['verticalAlignment'],
        'wrapStrategy': ['wrapStrategy'],
        'borders': ['borders'],
        'numberFormat': ['numberFormat']
    }

    fields = []
    for key, field_list in field_mapping.items():
        if key in cell_format:
            fields.extend(field_list)

    return fields


def _build_cell_format(format_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Build cell format dictionary from format specifications."""
    cell_format = {}

    if 'text_format' in format_dict:
        cell_format['textFormat'] = format_dict['text_format']

    if 'background_color' in format_dict:
        cell_format['backgroundColor'] = format_dict['background_color']

    if 'borders' in format_dict:
        cell_format['borders'] = format_dict['borders']

    return cell_format


# ===== HIGH PRIORITY: Cell Formatting Extensions =====

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


# ===== HIGH PRIORITY: Data Validation Extensions =====

@mcp.tool()
def clear_data_validation(spreadsheet_id: str,
                          sheet_name: str,
                          range: str,
                          ctx: Context = None) -> Dict[str, Any]:
    """
    Remove data validation rules from a range of cells.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        range: Cell range in A1 notation (e.g., 'A1:C10')

    Returns:
        Dictionary with success status and validation details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)
        range_info = _parse_row_col(range)

        request_body = {
            "requests": [
                {
                    "deleteDataValidation": {
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


@mcp.tool()
def list_validation_rules(spreadsheet_id: str,
                          sheet_name: str = None,
                          ctx: Context = None) -> Dict[str, Any]:
    """
    List existing data validation rules in a sheet or spreadsheet.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Optional name of the sheet (case-sensitive). If not provided, returns all rules.

    Returns:
        Dictionary with success status and list of validation rules
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


# ===== HIGH PRIORITY: Conditional Formatting Extensions =====

@mcp.tool()
def update_conditional_formatting(spreadsheet_id: str,
                                  sheet_name: str,
                                  rule_id: int,
                                  rule: Dict[str, Any],
                                  ctx: Context = None) -> Dict[str, Any]:
    """
    Update an existing conditional formatting rule.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        rule_id: ID of the rule to update
        rule: Dictionary with new rule configuration. Example:
            {
                "ranges": [{"sheetId": 0, "startRowIndex": 1, "endRowIndex": 10, "startColumnIndex": 1, "endColumnIndex": 5}],
                "booleanRule": {
                    "condition": {"type": "NUMBER_GREATER", "values": [{"userEnteredValue": "100"}]},
                    "format": {"backgroundColor": {"red": 1, "green": 0, "blue": 0}}
                }
            }

    Returns:
        Dictionary with success status and updated rule details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)

        # Ensure sheetId is set in ranges
        if 'ranges' in rule:
            for r in rule['ranges']:
                if 'sheetId' not in r:
                    r['sheetId'] = sheet_id

        request_body = {
            "requests": [
                {
                    "updateConditionalFormatRule": {
                        "index": rule_id,
                        "rule": rule,
                        "newIndex": rule_id
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
            "message": f"Conditional formatting rule {rule_id} updated",
            "rule_id": rule_id,
            "rule": rule
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error updating conditional formatting: {str(e)}"
        }


@mcp.tool()
def clear_conditional_formatting(spreadsheet_id: str,
                                 sheet_name: str,
                                 rule_id: int = None,
                                 ctx: Context = None) -> Dict[str, Any]:
    """
    Remove specific conditional formatting rules or all rules from a sheet.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        rule_id: ID of the rule to remove. If not provided, removes all rules from the sheet.

    Returns:
        Dictionary with success status and removal details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)

        if rule_id is not None:
            # Remove specific rule
            request_body = {
                "requests": [
                    {
                        "deleteConditionalFormatRule": {
                            "index": rule_id,
                            "sheetId": sheet_id
                        }
                    }
                ]
            }
            message = f"Conditional formatting rule {rule_id} removed"
        else:
            # Remove all rules from sheet
            request_body = {
                "requests": [
                    {
                        "deleteConditionalFormatRule": {
                            "sheetId": sheet_id
                        }
                    }
                ]
            }
            message = f"All conditional formatting rules removed from {sheet_name}"

        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()

        return {
            "success": True,
            "message": message,
            "sheet_name": sheet_name
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error clearing conditional formatting: {str(e)}"
        }


# ===== HIGH PRIORITY: Sheet Protection Extensions =====

@mcp.tool()
def set_edit_permissions(spreadsheet_id: str,
                         protection_id: str,
                         users: List[str] = None,
                         roles: List[str] = None,
                         ctx: Context = None) -> Dict[str, Any]:
    """
    Configure protection permissions for protected ranges.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        protection_id: ID of the protection rule to modify
        users: List of email addresses to grant permissions
        roles: List of roles for the users (e.g., ['editor'])

    Returns:
        Dictionary with success status and permission details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        # First, get the protected range info to ensure it exists
        spreadsheet = sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields='sheets.properties,protectedRanges'
        ).execute()

        protection_found = False
        for sheet in spreadsheet.get('sheets', []):
            protected_ranges = sheet.get('protectedRanges', [])
            for protected_range in protected_ranges:
                if str(protected_range.get('protectedRangeId')) == protection_id:
                    protection_found = True
                    break
            if protection_found:
                break

        if not protection_found:
            return {
                "success": False,
                "message": f"Protection ID {protection_id} not found"
            }

        # Build editors list
        editors = []
        if users:
            for user in users:
                if '@' in user:
                    editors.append({"userEmail": user})
                else:
                    editors.append({"domain": user})

        request_body = {
            "requests": [
                {
                    "updateProtectedRange": {
                        "protectedRange": {
                            "protectedRangeId": int(protection_id),
                            "editors": {
                                "users": users if users else [],
                                "domainUsersCanEdit": False
                            }
                        },
                        "fields": "editors"
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
            "message": f"Edit permissions updated for protection {protection_id}",
            "protection_id": protection_id,
            "users": users,
            "roles": roles
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error setting edit permissions: {str(e)}"
        }


@mcp.tool()
def remove_protection(spreadsheet_id: str,
                      protection_id: str,
                      ctx: Context = None) -> Dict[str, Any]:
    """
    Remove protection rules from a spreadsheet.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        protection_id: ID of the protection rule to remove

    Returns:
        Dictionary with success status and removal details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        request_body = {
            "requests": [
                {
                    "deleteProtectedRange": {
                        "protectedRangeId": int(protection_id)
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
            "message": f"Protection {protection_id} removed",
            "protection_id": protection_id
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error removing protection: {str(e)}"
        }


# ===== MEDIUM PRIORITY: Chart Management =====

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


# ===== MEDIUM PRIORITY: Named Range Management =====

@mcp.tool()
def create_named_range(spreadsheet_id: str,
                       name: str,
                       range: str,
                       ctx: Context = None) -> Dict[str, Any]:
    """
    Define named ranges for easier reference.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        name: Name for the named range
        range: Cell range in A1 notation (e.g., 'Sheet1!A1:C10')

    Returns:
        Dictionary with success status and named range details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        request_body = {
            "requests": [
                {
                    "addNamedRange": {
                        "namedRange": {
                            "name": name,
                            "range": range
                        }
                    }
                }
            ]
        }

        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()

        named_range_id = response.get('replies', [{}])[0].get('addNamedRange', {}).get('namedRange', {}).get('namedRangeId')

        return {
            "success": True,
            "message": f"Named range '{name}' created successfully",
            "name": name,
            "range": range,
            "named_range_id": named_range_id
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error creating named range: {str(e)}"
        }


@mcp.tool()
def list_named_ranges(spreadsheet_id: str,
                      ctx: Context = None) -> Dict[str, Any]:
    """
    Get all named ranges in a spreadsheet.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet

    Returns:
        Dictionary with success status and list of named ranges
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        spreadsheet = sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields='namedRanges'
        ).execute()

        named_ranges = []
        for named_range in spreadsheet.get('namedRanges', []):
            named_ranges.append({
                'name': named_range.get('name'),
                'named_range_id': named_range.get('namedRangeId'),
                'range': named_range.get('range'),
                'sheet_id': named_range.get('range', {}).get('sheetId')
            })

        return {
            "success": True,
            "message": f"Found {len(named_ranges)} named ranges",
            "named_ranges": named_ranges
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error listing named ranges: {str(e)}"
        }


@mcp.tool()
def update_named_range(spreadsheet_id: str,
                       name: str,
                       new_range: str,
                       ctx: Context = None) -> Dict[str, Any]:
    """
    Modify existing named ranges.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        name: Current name of the named range
        new_range: New cell range in A1 notation

    Returns:
        Dictionary with success status and updated named range details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        # First, get existing named ranges to find the one to update
        spreadsheet = sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields='namedRanges'
        ).execute()

        named_range_id = None
        for named_range in spreadsheet.get('namedRanges', []):
            if named_range.get('name') == name:
                named_range_id = named_range.get('namedRangeId')
                break

        if not named_range_id:
            return {
                "success": False,
                "message": f"Named range '{name}' not found"
            }

        request_body = {
            "requests": [
                {
                    "updateNamedRange": {
                        "namedRange": {
                            "namedRangeId": named_range_id,
                            "name": name,
                            "range": new_range
                        },
                        "fields": "range"
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
            "message": f"Named range '{name}' updated successfully",
            "name": name,
            "new_range": new_range,
            "named_range_id": named_range_id
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error updating named range: {str(e)}"
        }


# ===== MEDIUM PRIORITY: Advanced Range Operations =====

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
def delete_rows_columns(spreadsheet_id: str,
                        sheet_name: str,
                        dimension: str,
                        start_index: int,
                        end_index: int,
                        ctx: Context = None) -> Dict[str, Any]:
    """
    Delete rows or columns.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        dimension: 'ROWS' or 'COLUMNS'
        start_index: Zero-based start index
        end_index: Zero-based end index (exclusive)

    Returns:
        Dictionary with success status and deletion details
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
    Auto-fit row and column sizes.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        dimensions: Dictionary with dimensions to resize. Example:
            {
                "columns": {
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 10
                },
                "rows": {
                    "dimension": "ROWS",
                    "startIndex": 0,
                    "endIndex": 20
                }
            }

    Returns:
        Dictionary with success status and resize details
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


# ===== MEDIUM PRIORITY: Filter Operations =====

@mcp.tool()
def create_filter(spreadsheet_id: str,
                  sheet_name: str,
                  range: str,
                  ctx: Context = None) -> Dict[str, Any]:
    """
    Apply filters to a range.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        range: Cell range in A1 notation (e.g., 'A1:C10')

    Returns:
        Dictionary with success status and filter details
    """
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
            "range": range
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error creating filter: {str(e)}"
        }


@mcp.tool()
def apply_filter_criteria(spreadsheet_id: str,
                          sheet_name: str,
                          filter_id: int,
                          criteria: Dict[str, Any],
                          ctx: Context = None) -> Dict[str, Any]:
    """
    Set filter conditions.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        filter_id: ID of the filter to modify
        criteria: Dictionary with filter criteria. Example:
            {
                "0": {  # Column index
                    "condition": {
                        "type": "NUMBER_GREATER",
                        "values": [{"userEnteredValue": "100"}]
                    }
                }
            }

    Returns:
        Dictionary with success status and filter criteria details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        request_body = {
            "requests": [
                {
                    "updateFilterView": {
                        "filter": {
                            "filterViewId": filter_id,
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
            "message": f"Filter criteria updated for filter {filter_id}",
            "filter_id": filter_id,
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
    """
    Remove filters from a sheet.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)

    Returns:
        Dictionary with success status and clear operation details
    """
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


def main():
    # Run the server
    transport = "stdio"
    for i, arg in enumerate(sys.argv):
        if arg == "--transport" and i + 1 < len(sys.argv):
            transport = sys.argv[i + 1]
            break

    mcp.run(transport=transport)
