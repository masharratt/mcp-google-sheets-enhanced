"""
Protection tools: protect ranges/sheets, set permissions, remove protection.
"""

from typing import Annotated, List, Dict, Any, Optional

from pydantic import Field

from mcp.server.fastmcp import Context

from gsheets_mcp.core import mcp, _get_sheet_id, _parse_row_col


@mcp.tool()
def protect_sheet_range(spreadsheet_id: str,
                        sheet_name: str,
                        range: Annotated[Optional[str], Field(description="A1 range to protect, e.g. 'A1:C10'. Omit to protect entire sheet.")] = None,
                        protection_description: Optional[str] = None,
                        warning_only: bool = True,
                        requesting_users_can_edit: bool = False,
                        editor_emails: Optional[List[str]] = None,
                        ctx: Context = None) -> Dict[str, Any]:
    """Protect a sheet or range from editing; warning_only=True shows a warning instead of blocking."""
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
                         users: Optional[List[str]] = None,
                         roles: Optional[List[str]] = None,
                         ctx: Context = None) -> Dict[str, Any]:
    """Update the editor list on an existing protected range; always keeps the requesting user in the list."""
    lifespan = ctx.request_context.lifespan_context
    sheets_service = lifespan.sheets_service
    requesting_user_email = getattr(lifespan, 'requesting_user_email', None)

    try:
        # First, get the protected range info to ensure it exists
        spreadsheet = sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields='sheets.properties,sheets.protectedRanges'
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

        # Separate user emails from domain entries.
        user_emails = [u for u in (users or []) if '@' in u]

        # The Sheets API rejects any updateProtectedRange that removes the
        # requesting account (the service account) from the editors list
        # ("You can't remove yourself as an editor."). Always keep the
        # requester present.
        if requesting_user_email and requesting_user_email not in user_emails:
            user_emails.append(requesting_user_email)

        request_body = {
            "requests": [
                {
                    "updateProtectedRange": {
                        "protectedRange": {
                            "protectedRangeId": int(protection_id),
                            "editors": {
                                "users": user_emails,
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
    """Remove a protection rule from a spreadsheet by its ID."""
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
