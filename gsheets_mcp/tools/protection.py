"""
Protection tools: protect ranges/sheets, set permissions, remove protection.
"""

from typing import List, Dict, Any, Optional

from mcp.server.fastmcp import Context

from gsheets_mcp.core import mcp, _get_sheet_id, _parse_row_col


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
