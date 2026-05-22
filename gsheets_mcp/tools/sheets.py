"""
Sheets management tools: create, list, rename, copy spreadsheets and sheets,
manage folders, and share.
"""

import json
from typing import List, Dict, Any, Optional

from mcp.server.fastmcp import Context

from gsheets_mcp.core import mcp, _get_sheet_id


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
def duplicate_sheet(spreadsheet_id: str,
                    source_sheet: str,
                    new_sheet_name: str,
                    insert_index: Optional[int] = None,
                    ctx: Context = None) -> Dict[str, Any]:
    """
    Duplicate a sheet within the same spreadsheet.

    Copies the source sheet to a new tab inside the same spreadsheet.
    This differs from copy_sheet, which copies a sheet to a different spreadsheet.

    Args:
        spreadsheet_id: The ID of the spreadsheet.
        source_sheet: Name of the sheet tab to duplicate.
        new_sheet_name: Name for the new duplicate sheet.
        insert_index: Optional 0-based position where the new sheet should be inserted.
                      If omitted, the sheet is placed after the source sheet.

    Returns:
        Information about the newly created sheet including sheetId, title, and spreadsheetId.
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        source_sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, source_sheet)
    except ValueError as exc:
        return {"error": str(exc)}

    duplicate_request = {
        "sourceSheetId": source_sheet_id,
        "newSheetName": new_sheet_name,
    }
    if insert_index is not None:
        duplicate_request["insertSheetIndex"] = insert_index

    request_body = {
        "requests": [
            {"duplicateSheet": duplicate_request}
        ]
    }

    result = sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=request_body
    ).execute()

    new_props = result['replies'][0]['duplicateSheet']['properties']
    return {
        'sheetId': new_props['sheetId'],
        'title': new_props['title'],
        'index': new_props.get('index'),
        'spreadsheetId': spreadsheet_id,
    }


@mcp.tool()
def delete_sheet(spreadsheet_id: str,
                 sheet: str,
                 ctx: Context = None) -> Dict[str, Any]:
    """
    Delete a sheet (tab) from a spreadsheet.

    Permanently removes the named sheet and all its data. A spreadsheet must
    retain at least one sheet, so deleting the last remaining sheet fails.

    Args:
        spreadsheet_id: The ID of the spreadsheet.
        sheet: Name of the sheet tab to delete (case-sensitive).

    Returns:
        Dictionary with success status and the deleted sheet name and id.
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet)
    except ValueError as exc:
        return {"success": False, "error": str(exc)}

    request_body = {
        "requests": [
            {"deleteSheet": {"sheetId": sheet_id}}
        ]
    }

    try:
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()
    except Exception as exc:
        return {"success": False, "error": f"Error deleting sheet: {str(exc)}"}

    return {
        "success": True,
        "message": f"Deleted sheet '{sheet}'",
        "sheet": sheet,
        "sheet_id": sheet_id,
        "spreadsheetId": spreadsheet_id,
    }


@mcp.tool()
def set_sheet_visibility(spreadsheet_id: str,
                         sheet: str,
                         hidden: bool,
                         ctx: Context = None) -> Dict[str, Any]:
    """
    Show or hide a sheet tab in a Google Spreadsheet.

    Args:
        spreadsheet_id: The ID of the spreadsheet.
        sheet: Name of the sheet tab to show or hide.
        hidden: True to hide the sheet, False to make it visible.

    Returns:
        Confirmation with spreadsheetId, sheet name, and the hidden state applied.
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet)
    except ValueError as exc:
        return {"error": str(exc)}

    request_body = {
        "requests": [
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "hidden": hidden,
                    },
                    "fields": "hidden",
                }
            }
        ]
    }

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=request_body
    ).execute()

    return {
        'spreadsheetId': spreadsheet_id,
        'sheet': sheet,
        'hidden': hidden,
    }


@mcp.tool()
def reorder_sheet(spreadsheet_id: str,
                  sheet: str,
                  new_index: int,
                  ctx: Context = None) -> Dict[str, Any]:
    """
    Move a sheet tab to a new position within a Google Spreadsheet.

    Args:
        spreadsheet_id: The ID of the spreadsheet.
        sheet: Name of the sheet tab to move.
        new_index: 0-based position the sheet should occupy after the move.

    Returns:
        Confirmation with spreadsheetId, sheet name, and new_index applied.
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet)
    except ValueError as exc:
        return {"error": str(exc)}

    request_body = {
        "requests": [
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "index": new_index,
                    },
                    "fields": "index",
                }
            }
        ]
    }

    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=request_body
    ).execute()

    return {
        'spreadsheetId': spreadsheet_id,
        'sheet': sheet,
        'new_index': new_index,
    }


@mcp.tool()
def move_spreadsheet_to_folder(spreadsheet_id: str,
                                target_folder_id: str,
                                remove_from_current: bool = True,
                                ctx: Context = None) -> Dict[str, Any]:
    """
    Move a Google Spreadsheet to a different Drive folder.

    Uses the Drive API files.update with addParents and, by default, removeParents
    to relocate the file without creating duplicate folder memberships.

    Args:
        spreadsheet_id: The ID of the spreadsheet (Drive file ID).
        target_folder_id: ID of the destination Drive folder.
        remove_from_current: When True (default), removes the file from its current
                             parent folders before adding it to the target folder.

    Returns:
        Confirmation with spreadsheetId and target_folder_id.
    """
    drive_service = ctx.request_context.lifespan_context.drive_service

    update_kwargs = {
        'fileId': spreadsheet_id,
        'addParents': target_folder_id,
        'fields': 'id, name, parents',
        'supportsAllDrives': True,
    }

    if remove_from_current:
        # Fetch current parents so they can be removed.
        file_meta = drive_service.files().get(
            fileId=spreadsheet_id,
            fields='parents',
            supportsAllDrives=True,
        ).execute()
        current_parents = file_meta.get('parents', [])
        if current_parents:
            update_kwargs['removeParents'] = ','.join(current_parents)

    drive_service.files().update(**update_kwargs).execute()

    return {
        'spreadsheetId': spreadsheet_id,
        'target_folder_id': target_folder_id,
    }


@mcp.tool()
def trash_spreadsheet(spreadsheet_id: str,
                      ctx: Context = None) -> Dict[str, Any]:
    """
    Move a Google Spreadsheet to Drive trash. This is RECOVERABLE and NOT permanent deletion.

    The file is moved to the Drive trash and can be restored by the owner from
    drive.google.com within 30 days. It is not permanently deleted.

    Args:
        spreadsheet_id: The ID of the spreadsheet to trash.

    Returns:
        Confirmation with spreadsheetId and trashed=True.
    """
    drive_service = ctx.request_context.lifespan_context.drive_service

    drive_service.files().update(
        fileId=spreadsheet_id,
        body={'trashed': True},
        supportsAllDrives=True,
        fields='id, name, trashed',
    ).execute()

    return {
        'spreadsheetId': spreadsheet_id,
        'trashed': True,
    }
