"""
Developer metadata tools: create and search developer metadata in Google Sheets.

Developer metadata are key/value labels attached to a spreadsheet, sheet, or range.
"""

from typing import Dict, Any, Optional

from mcp.server.fastmcp import Context

from gsheets_mcp.core import mcp, _get_sheet_id


@mcp.tool()
def create_developer_metadata(spreadsheet_id: str,
                               metadata_key: str,
                               metadata_value: str,
                               visibility: str = "DOCUMENT",
                               location_type: str = "SPREADSHEET",
                               sheet: Optional[str] = None,
                               ctx: Context = None) -> Dict[str, Any]:
    """
    Attach developer metadata (a key/value label) to a spreadsheet or sheet.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        metadata_key: Key for the metadata entry
        metadata_value: Value for the metadata entry
        visibility: 'DOCUMENT' (default) or 'PROJECT'
        location_type: 'SPREADSHEET' (default) or 'SHEET'
        sheet: Sheet name (required when location_type is 'SHEET')

    Returns:
        Dictionary with success status and created metadata (including metadataId)
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        if location_type == "SHEET":
            if not sheet:
                raise ValueError("sheet is required when location_type is 'SHEET'")
            sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet)
            location = {"sheetId": sheet_id}
        else:
            location = {"spreadsheet": True}

        developer_metadata = {
            "metadataKey": metadata_key,
            "metadataValue": metadata_value,
            "visibility": visibility,
            "location": location
        }

        request_body = {
            "requests": [
                {
                    "createDeveloperMetadata": {
                        "developerMetadata": developer_metadata
                    }
                }
            ]
        }

        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()

        created = (
            response.get("replies", [{}])[0]
            .get("createDeveloperMetadata", {})
            .get("developerMetadata", {})
        )

        return {
            "success": True,
            "message": "Developer metadata created successfully",
            "metadata": created
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error creating developer metadata: {str(e)}"
        }


@mcp.tool()
def search_developer_metadata(spreadsheet_id: str,
                               metadata_key: Optional[str] = None,
                               metadata_id: Optional[int] = None,
                               ctx: Context = None) -> Dict[str, Any]:
    """
    Search developer metadata attached to a spreadsheet using dataFilters.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        metadata_key: Filter by metadata key (optional)
        metadata_id: Filter by metadata ID (optional)

    Returns:
        Dictionary with success status and list of matched metadata entries
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        lookup: Dict[str, Any] = {}
        if metadata_key is not None:
            lookup["metadataKey"] = metadata_key
        if metadata_id is not None:
            lookup["metadataId"] = metadata_id

        data_filters = [{"developerMetadataLookup": lookup}]

        body = {"dataFilters": data_filters}

        response = sheets_service.spreadsheets().developerMetadata().search(
            spreadsheetId=spreadsheet_id,
            body=body
        ).execute()

        matched = response.get("matchedDeveloperMetadata", [])
        entries = [m.get("developerMetadata", m) for m in matched]

        return {
            "success": True,
            "message": f"Found {len(entries)} metadata entries",
            "metadata": entries
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error searching developer metadata: {str(e)}"
        }
