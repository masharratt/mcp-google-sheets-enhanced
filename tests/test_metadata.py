"""
Tests for create_developer_metadata and search_developer_metadata
in gsheets_mcp/tools/metadata.py.
"""

import pytest
from gsheets_mcp.tools.metadata import create_developer_metadata, search_developer_metadata


# ---------------------------------------------------------------------------
# create_developer_metadata
# ---------------------------------------------------------------------------

def test_create_metadata_success(fake_ctx, mock_sheets_service):
    """create_developer_metadata returns success=True."""
    mock_sheets_service.set_execute_return({
        "spreadsheetId": "ss-1",
        "replies": [{"createDeveloperMetadata": {"developerMetadata": {"metadataId": 1, "metadataKey": "env", "metadataValue": "prod"}}}]
    })

    result = create_developer_metadata(
        spreadsheet_id="ss-1",
        metadata_key="env",
        metadata_value="prod",
        ctx=fake_ctx,
    )
    assert result["success"] is True


def test_create_metadata_uses_batch_update(fake_ctx, mock_sheets_service):
    """create_developer_metadata calls batchUpdate with createDeveloperMetadata request."""
    mock_sheets_service.set_execute_return({
        "replies": [{"createDeveloperMetadata": {"developerMetadata": {"metadataId": 5}}}]
    })

    create_developer_metadata(
        spreadsheet_id="ss-1",
        metadata_key="mykey",
        metadata_value="myval",
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    body = kwargs.get("body", {})
    requests = body.get("requests", [])
    matched = [r for r in requests if "createDeveloperMetadata" in r]
    assert matched, f"Expected createDeveloperMetadata request, got: {requests}"


def test_create_metadata_key_and_value(fake_ctx, mock_sheets_service):
    """The createDeveloperMetadata request must include the correct key and value."""
    mock_sheets_service.set_execute_return({
        "replies": [{"createDeveloperMetadata": {"developerMetadata": {"metadataId": 10}}}]
    })

    create_developer_metadata(
        spreadsheet_id="ss-1",
        metadata_key="color",
        metadata_value="blue",
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    body = kwargs.get("body", {})
    requests = body.get("requests", [])
    matched = [r for r in requests if "createDeveloperMetadata" in r]
    dm = matched[0]["createDeveloperMetadata"]["developerMetadata"]
    assert dm["metadataKey"] == "color"
    assert dm["metadataValue"] == "blue"


def test_create_metadata_default_visibility(fake_ctx, mock_sheets_service):
    """Default visibility is DOCUMENT."""
    mock_sheets_service.set_execute_return({
        "replies": [{"createDeveloperMetadata": {"developerMetadata": {"metadataId": 1}}}]
    })

    create_developer_metadata(
        spreadsheet_id="ss-1",
        metadata_key="k",
        metadata_value="v",
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    body = kwargs.get("body", {})
    requests = body.get("requests", [])
    matched = [r for r in requests if "createDeveloperMetadata" in r]
    dm = matched[0]["createDeveloperMetadata"]["developerMetadata"]
    assert dm["visibility"] == "DOCUMENT"


def test_create_metadata_explicit_visibility(fake_ctx, mock_sheets_service):
    """Explicit visibility=PROJECT is forwarded."""
    mock_sheets_service.set_execute_return({
        "replies": [{"createDeveloperMetadata": {"developerMetadata": {"metadataId": 2}}}]
    })

    create_developer_metadata(
        spreadsheet_id="ss-1",
        metadata_key="k",
        metadata_value="v",
        visibility="PROJECT",
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    body = kwargs.get("body", {})
    requests = body.get("requests", [])
    matched = [r for r in requests if "createDeveloperMetadata" in r]
    dm = matched[0]["createDeveloperMetadata"]["developerMetadata"]
    assert dm["visibility"] == "PROJECT"


def test_create_metadata_spreadsheet_location_default(fake_ctx, mock_sheets_service):
    """Default location_type SPREADSHEET produces a spreadsheet location."""
    mock_sheets_service.set_execute_return({
        "replies": [{"createDeveloperMetadata": {"developerMetadata": {"metadataId": 3}}}]
    })

    create_developer_metadata(
        spreadsheet_id="ss-1",
        metadata_key="k",
        metadata_value="v",
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    body = kwargs.get("body", {})
    requests = body.get("requests", [])
    matched = [r for r in requests if "createDeveloperMetadata" in r]
    location = matched[0]["createDeveloperMetadata"]["developerMetadata"]["location"]
    assert "spreadsheet" in location, f"Expected spreadsheet location, got: {location}"


def test_create_metadata_sheet_location(fake_ctx, mock_sheets_service):
    """location_type=SHEET produces a sheetId location."""
    # Do NOT override execute_return here: the mock default includes the sheet list
    # so _get_sheet_id can resolve "Sheet1" -> 0, and batchUpdate returns {}.
    create_developer_metadata(
        spreadsheet_id="ss-1",
        metadata_key="k",
        metadata_value="v",
        location_type="SHEET",
        sheet="Sheet1",
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
    body = kwargs.get("body", {})
    requests = body.get("requests", [])
    matched = [r for r in requests if "createDeveloperMetadata" in r]
    assert matched, f"Expected createDeveloperMetadata in requests, got: {requests}"
    location = matched[0]["createDeveloperMetadata"]["developerMetadata"]["location"]
    assert "sheetId" in location, f"Expected sheetId in location, got: {location}"


def test_create_metadata_returns_metadata_id(fake_ctx, mock_sheets_service):
    """Return value includes metadataId from the API response."""
    mock_sheets_service.set_execute_return({
        "replies": [{
            "createDeveloperMetadata": {
                "developerMetadata": {
                    "metadataId": 42,
                    "metadataKey": "env",
                    "metadataValue": "staging"
                }
            }
        }]
    })

    result = create_developer_metadata(
        spreadsheet_id="ss-1",
        metadata_key="env",
        metadata_value="staging",
        ctx=fake_ctx,
    )
    assert result["success"] is True
    assert result.get("metadata", {}).get("metadataId") == 42


def test_create_metadata_error_handling(fake_ctx, mock_sheets_service):
    """create_developer_metadata returns success=False on exception."""
    original_execute = mock_sheets_service.execute
    mock_sheets_service.execute = lambda: (_ for _ in ()).throw(Exception("API failure"))

    result = create_developer_metadata(
        spreadsheet_id="ss-1",
        metadata_key="k",
        metadata_value="v",
        ctx=fake_ctx,
    )
    assert result["success"] is False

    mock_sheets_service.execute = original_execute


# ---------------------------------------------------------------------------
# search_developer_metadata
# ---------------------------------------------------------------------------

def test_search_metadata_success(fake_ctx, mock_sheets_service):
    """search_developer_metadata returns success=True with matched entries."""
    mock_sheets_service.set_execute_return({
        "matchedDeveloperMetadata": [
            {"developerMetadata": {"metadataId": 1, "metadataKey": "env", "metadataValue": "prod"}}
        ]
    })

    result = search_developer_metadata(
        spreadsheet_id="ss-1",
        metadata_key="env",
        ctx=fake_ctx,
    )
    assert result["success"] is True
    assert len(result["metadata"]) == 1


def test_search_metadata_calls_search_endpoint(fake_ctx, mock_sheets_service):
    """search_developer_metadata calls developerMetadata().search() not batchUpdate."""
    mock_sheets_service.set_execute_return({
        "matchedDeveloperMetadata": []
    })

    search_developer_metadata(
        spreadsheet_id="ss-2",
        metadata_key="mykey",
        ctx=fake_ctx,
    )

    # The 'search' method should have been called
    kwargs = mock_sheets_service._last_call_kwargs.get("search", {})
    assert kwargs.get("spreadsheetId") == "ss-2", (
        f"Expected search called with spreadsheetId='ss-2', got kwargs: {mock_sheets_service._last_call_kwargs}"
    )


def test_search_metadata_by_key_filter(fake_ctx, mock_sheets_service):
    """When metadata_key is provided, the dataFilters include a metadataLookup by key."""
    mock_sheets_service.set_execute_return({"matchedDeveloperMetadata": []})

    search_developer_metadata(
        spreadsheet_id="ss-1",
        metadata_key="color",
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("search", {})
    body = kwargs.get("body", {})
    data_filters = body.get("dataFilters", [])
    assert data_filters, f"Expected dataFilters in search body, got: {body}"
    lookup = data_filters[0].get("developerMetadataLookup", {})
    assert lookup.get("metadataKey") == "color"


def test_search_metadata_by_id_filter(fake_ctx, mock_sheets_service):
    """When metadata_id is provided, the dataFilters include a metadataLookup by id."""
    mock_sheets_service.set_execute_return({"matchedDeveloperMetadata": []})

    search_developer_metadata(
        spreadsheet_id="ss-1",
        metadata_id=99,
        ctx=fake_ctx,
    )

    kwargs = mock_sheets_service._last_call_kwargs.get("search", {})
    body = kwargs.get("body", {})
    data_filters = body.get("dataFilters", [])
    assert data_filters
    lookup = data_filters[0].get("developerMetadataLookup", {})
    assert lookup.get("metadataId") == 99


def test_search_metadata_empty_result(fake_ctx, mock_sheets_service):
    """search_developer_metadata handles empty matchedDeveloperMetadata gracefully."""
    mock_sheets_service.set_execute_return({})

    result = search_developer_metadata(
        spreadsheet_id="ss-1",
        ctx=fake_ctx,
    )
    assert result["success"] is True
    assert result["metadata"] == []


def test_search_metadata_error_handling(fake_ctx, mock_sheets_service):
    """search_developer_metadata returns success=False on exception."""
    original_execute = mock_sheets_service.execute
    mock_sheets_service.execute = lambda: (_ for _ in ()).throw(Exception("search error"))

    result = search_developer_metadata(
        spreadsheet_id="ss-1",
        ctx=fake_ctx,
    )
    assert result["success"] is False

    mock_sheets_service.execute = original_execute
