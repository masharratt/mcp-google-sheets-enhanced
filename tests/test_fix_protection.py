"""
Failing tests for Bug 1: set_edit_permissions uses wrong fields mask.

Live error: HTTP 400 - 'protectedRanges' must be nested under 'sheets'.
Fix: fields must be 'sheets.properties,sheets.protectedRanges'.
"""

import pytest
from unittest.mock import MagicMock
from gsheets_mcp.tools.protection import set_edit_permissions


SPREADSHEET_ID = "test-spreadsheet-id"
PROTECTION_ID = "42"


def _make_get_response(protection_id=42):
    """Build a spreadsheets().get() response with protectedRanges under sheets[]."""
    return {
        "spreadsheetId": SPREADSHEET_ID,
        "sheets": [
            {
                "properties": {"title": "Sheet1", "sheetId": 0},
                "protectedRanges": [
                    {
                        "protectedRangeId": protection_id,
                        "range": {"sheetId": 0},
                        "warningOnly": True,
                    }
                ],
            }
        ],
    }


class _CapturingMock:
    """
    Tracks what fields= was passed to spreadsheets().get() and returns
    a configurable response from execute().
    """

    def __init__(self, get_response):
        self._get_response = get_response
        self.captured_get_kwargs = {}
        self.captured_batchupdate_kwargs = {}

    # -- sheets_service entry point --
    def spreadsheets(self):
        return self

    # -- spreadsheets().get(**kwargs) --
    def get(self, **kwargs):
        self.captured_get_kwargs = kwargs
        return self

    # -- spreadsheets().batchUpdate(**kwargs) --
    def batchUpdate(self, **kwargs):
        self.captured_batchupdate_kwargs = kwargs
        return self

    def execute(self):
        # Return get_response for the first call (get), then empty dict for batchUpdate.
        # Simple heuristic: if batchUpdate was already called return {}.
        if self.captured_batchupdate_kwargs:
            return {"replies": [{}]}
        return self._get_response

    # Allow arbitrary chaining (e.g. spreadsheets()() is never called but guard it).
    def __call__(self, *args, **kwargs):
        return self


class _FakeLifespanCtx:
    def __init__(self, service, requesting_user_email="sa@proj.iam.gserviceaccount.com"):
        self.sheets_service = service
        self.requesting_user_email = requesting_user_email


class _FakeReqCtx:
    def __init__(self, lifespan):
        self.lifespan_context = lifespan


class _FakeCtx:
    def __init__(self, service):
        self.request_context = _FakeReqCtx(_FakeLifespanCtx(service))


# ---------------------------------------------------------------------------
# Test: fields mask must include sheets.protectedRanges (not bare protectedRanges)
# ---------------------------------------------------------------------------

def test_set_edit_permissions_fields_mask_correct():
    """
    set_edit_permissions must call spreadsheets().get() with
    fields containing 'sheets.protectedRanges', NOT bare 'protectedRanges'.
    """
    mock_svc = _CapturingMock(get_response=_make_get_response(42))
    ctx = _FakeCtx(mock_svc)

    result = set_edit_permissions(
        spreadsheet_id=SPREADSHEET_ID,
        protection_id=PROTECTION_ID,
        users=["user@example.com"],
        ctx=ctx,
    )

    fields_used = mock_svc.captured_get_kwargs.get("fields", "")
    assert "sheets.protectedRanges" in fields_used, (
        f"Expected 'sheets.protectedRanges' in fields mask, got: {fields_used!r}"
    )
    # Must NOT contain the bare (broken) path
    assert "protectedRanges" in fields_used  # still present but nested
    # Confirm the bare path is not alone (i.e. not 'sheets.properties,protectedRanges')
    import re
    bare = re.search(r'(?<![.\w])protectedRanges', fields_used)
    assert bare is None, (
        f"Bare 'protectedRanges' (not nested under 'sheets.') found in fields: {fields_used!r}"
    )


def test_set_edit_permissions_finds_protection_and_succeeds():
    """
    When the protection exists in the corrected response structure,
    set_edit_permissions should return success=True.
    """
    mock_svc = _CapturingMock(get_response=_make_get_response(42))
    ctx = _FakeCtx(mock_svc)

    result = set_edit_permissions(
        spreadsheet_id=SPREADSHEET_ID,
        protection_id=PROTECTION_ID,
        users=["user@example.com"],
        ctx=ctx,
    )

    assert result.get("success") is True, f"Expected success, got: {result}"


def test_set_edit_permissions_keeps_requesting_user_editor():
    """
    Regression: the editors.users list must include the requesting service
    account. The Sheets API rejects an updateProtectedRange that removes the
    requester ('You can't remove yourself as an editor.', observed live).
    There is no 'requestingUserCanEdit' field on Editors, so the requester
    email must be appended to users.
    """
    mock_svc = _CapturingMock(get_response=_make_get_response(42))
    ctx = _FakeCtx(mock_svc)

    set_edit_permissions(
        spreadsheet_id=SPREADSHEET_ID,
        protection_id=PROTECTION_ID,
        users=["user@example.com"],
        ctx=ctx,
    )

    body = mock_svc.captured_batchupdate_kwargs.get("body", {})
    editors = body["requests"][0]["updateProtectedRange"]["protectedRange"]["editors"]
    assert "requestingUserCanEdit" not in editors, (
        "requestingUserCanEdit is not a valid Editors field; must not be sent"
    )
    assert "user@example.com" in editors["users"]
    assert "sa@proj.iam.gserviceaccount.com" in editors["users"], (
        f"requesting service account must be retained as editor, got: {editors['users']!r}"
    )


def test_set_edit_permissions_not_found_returns_failure():
    """
    When no protection matches the given ID, return success=False.
    """
    mock_svc = _CapturingMock(get_response=_make_get_response(999))
    ctx = _FakeCtx(mock_svc)

    result = set_edit_permissions(
        spreadsheet_id=SPREADSHEET_ID,
        protection_id=PROTECTION_ID,  # "42", but mock only has id 999
        users=["user@example.com"],
        ctx=ctx,
    )

    assert result.get("success") is False
    assert PROTECTION_ID in result.get("message", "")
