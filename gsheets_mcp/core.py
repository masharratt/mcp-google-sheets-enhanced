"""
Google Spreadsheet MCP Server - Core module.

Contains the FastMCP instance, SpreadsheetContext, lifespan, constants,
shared helpers used across multiple tool modules, and main().
"""

import base64
import os
import sys
from typing import List, Dict, Any, Optional
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
    # Email of the authenticated principal (service account). Used where the
    # Sheets API forbids removing the requester, e.g. updateProtectedRange.
    requesting_user_email: Optional[str] = None


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
            folder_id=DRIVE_FOLDER_ID if DRIVE_FOLDER_ID else None,
            requesting_user_email=getattr(creds, 'service_account_email', None)
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


# ===== Shared Helper Functions =====
# Used across multiple tool modules. Conditional-formatting-only helpers
# (_normalize_condition_type, _build_condition_values, _build_gradient_rule)
# live in gsheets_mcp/tools/conditional.py instead.

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


def _map_text_format_keys(tf: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a caller-supplied text_format dict (snake_case keys) into the
    camelCase shape expected by the Google Sheets API textFormat object.

    Supported input keys and their API equivalents:
        bold             -> bold  (unchanged)
        italic           -> italic  (unchanged)
        underline        -> underline  (unchanged)
        strikethrough    -> strikethrough  (unchanged)
        font_family      -> fontFamily
        font_size        -> fontSize
        foreground_color -> foregroundColor
        background_color -> backgroundColor  (nested inside textFormat when
                           caller places it here; top-level background_color
                           is handled separately as userEnteredFormat.backgroundColor)
    """
    key_map = {
        'font_family': 'fontFamily',
        'font_size': 'fontSize',
        'foreground_color': 'foregroundColor',
        'background_color': 'backgroundColor',
    }
    result = {}
    for k, v in tf.items():
        result[key_map.get(k, k)] = v
    return result


def _get_format_fields(cell_format: Dict[str, Any]) -> List[str]:
    """
    Return a list of 'userEnteredFormat.<field>' strings for every top-level
    key present in cell_format.  Used to build the repeatCell.fields mask.
    """
    known_fields = [
        'textFormat',
        'backgroundColor',
        'horizontalAlignment',
        'verticalAlignment',
        'wrapStrategy',
        'borders',
        'numberFormat',
    ]

    fields = []
    for field in known_fields:
        if field in cell_format:
            fields.append(f'userEnteredFormat.{field}')

    return fields


def _build_cell_format(format_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a userEnteredFormat dict from a caller-supplied format_dict.

    Handles:
        text_format       -> textFormat  (sub-keys camelCased via _map_text_format_keys)
        background_color  -> backgroundColor
        borders           -> borders

    alignment and number_format are intentionally NOT handled here because
    apply_cell_formatting maps them inline; this keeps the function backward-
    compatible with conditional.py which only relies on the three keys above.
    """
    cell_format = {}

    if 'text_format' in format_dict:
        cell_format['textFormat'] = _map_text_format_keys(format_dict['text_format'])

    if 'background_color' in format_dict:
        cell_format['backgroundColor'] = format_dict['background_color']

    if 'borders' in format_dict:
        cell_format['borders'] = format_dict['borders']

    return cell_format


def _a1_to_grid_range(sheet_id: int, range_str: str) -> Dict[str, Any]:
    """
    Convert an A1 notation range string (e.g. 'A1:D10') to a GridRange dict.
    Rows are 0-based, end indices are exclusive.
    """
    import re
    match = re.match(r'^([A-Za-z]+)(\d+):([A-Za-z]+)(\d+)$', range_str.strip())
    if not match:
        raise ValueError(f"Invalid A1 range: {range_str!r}")

    start_col = _col_to_num(match.group(1).upper()) - 1  # 0-based
    start_row = int(match.group(2)) - 1                  # 0-based
    end_col = _col_to_num(match.group(3).upper())        # exclusive
    end_row = int(match.group(4))                        # exclusive

    return {
        "sheetId": sheet_id,
        "startRowIndex": start_row,
        "endRowIndex": end_row,
        "startColumnIndex": start_col,
        "endColumnIndex": end_col,
    }


def main():
    # Run the server
    transport = "stdio"
    for i, arg in enumerate(sys.argv):
        if arg == "--transport" and i + 1 < len(sys.argv):
            transport = sys.argv[i + 1]
            break

    mcp.run(transport=transport)
