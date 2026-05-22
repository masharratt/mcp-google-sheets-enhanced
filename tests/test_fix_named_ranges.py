"""
Failing tests for Bug 2 & 3: create_named_range and update_named_range pass
raw A1 strings where the API expects a GridRange dict.

Live error: HTTP 400 - Invalid value at '...named_range.range' (type ...GridRange).
Fix: convert A1 notation to GridRange using _a1_to_grid_range from structure.py.
"""

import pytest
from gsheets_mcp.tools.named_ranges import create_named_range, update_named_range


SPREADSHEET_ID = "test-spreadsheet-id"
SHEET_ID = 0
SHEET_NAME = "Sheet1"


# ---------------------------------------------------------------------------
# Chainable mock that can return different values for get() vs batchUpdate()
# ---------------------------------------------------------------------------

class _DualReturnMock:
    """
    Returns get_response for spreadsheets().get().execute() and
    batch_response for spreadsheets().batchUpdate().execute().
    Captures kwargs for both calls.
    """

    def __init__(self, get_response, batch_response=None):
        self._get_response = get_response
        self._batch_response = batch_response or {"replies": [{"addNamedRange": {"namedRange": {"namedRangeId": "nr-1"}}}]}
        self._mode = "get"  # tracks which execute() we're about to serve
        self.last_batchupdate_body = None
        self.last_get_kwargs = {}

    def spreadsheets(self):
        return self

    def get(self, **kwargs):
        self.last_get_kwargs = kwargs
        self._mode = "get"
        return self

    def batchUpdate(self, **kwargs):
        self.last_batchupdate_body = kwargs.get("body", {})
        self._mode = "batch"
        return self

    def execute(self):
        if self._mode == "batch":
            return self._batch_response
        return self._get_response

    def __call__(self, *args, **kwargs):
        return self


def _make_spreadsheet_response(sheet_id=SHEET_ID, title=SHEET_NAME):
    """Minimal get() response with sheets.properties."""
    return {
        "spreadsheetId": SPREADSHEET_ID,
        "sheets": [{"properties": {"title": title, "sheetId": sheet_id}}],
        "namedRanges": [
            {
                "name": "ExistingRange",
                "namedRangeId": "nr-existing",
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 3,
                    "startColumnIndex": 0,
                    "endColumnIndex": 1,
                },
            }
        ],
    }


class _FakeLifespanCtx:
    def __init__(self, service):
        self.sheets_service = service


class _FakeReqCtx:
    def __init__(self, lifespan):
        self.lifespan_context = lifespan


class _FakeCtx:
    def __init__(self, service):
        self.request_context = _FakeReqCtx(_FakeLifespanCtx(service))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GRID_RANGE_KEYS = {"sheetId", "startRowIndex", "endRowIndex", "startColumnIndex", "endColumnIndex"}


def _is_grid_range(obj):
    """Return True if obj is a dict with all GridRange keys."""
    return isinstance(obj, dict) and GRID_RANGE_KEYS.issubset(obj.keys())


def _extract_named_range_from_body(body, request_key):
    """Pull the namedRange dict out of the batchUpdate body."""
    requests = body.get("requests", [])
    for req in requests:
        if request_key in req:
            return req[request_key]["namedRange"]
    return None


# ---------------------------------------------------------------------------
# Bug 2: create_named_range must send GridRange, not a string
# ---------------------------------------------------------------------------

def test_create_named_range_sends_grid_range_not_string():
    """
    create_named_range must convert 'Sheet1!A2:A4' into a GridRange dict
    before sending to the API, not pass the raw string.
    """
    mock_svc = _DualReturnMock(
        get_response=_make_spreadsheet_response(),
        batch_response={"replies": [{"addNamedRange": {"namedRange": {"namedRangeId": "nr-1"}}}]},
    )
    ctx = _FakeCtx(mock_svc)

    result = create_named_range(
        spreadsheet_id=SPREADSHEET_ID,
        name="MyRange",
        range="Sheet1!A2:A4",
        ctx=ctx,
    )

    assert result.get("success") is True, f"Expected success, got: {result}"

    named_range = _extract_named_range_from_body(mock_svc.last_batchupdate_body, "addNamedRange")
    assert named_range is not None, "addNamedRange request not found in batchUpdate body"

    range_sent = named_range.get("range")
    assert _is_grid_range(range_sent), (
        f"Expected namedRange.range to be a GridRange dict, got: {range_sent!r}"
    )


def test_create_named_range_grid_range_values_correct():
    """
    Verify the GridRange indices match the A1 notation 'A2:A4':
      startRowIndex=1, endRowIndex=4, startColumnIndex=0, endColumnIndex=1
    """
    mock_svc = _DualReturnMock(
        get_response=_make_spreadsheet_response(),
        batch_response={"replies": [{"addNamedRange": {"namedRange": {"namedRangeId": "nr-2"}}}]},
    )
    ctx = _FakeCtx(mock_svc)

    create_named_range(
        spreadsheet_id=SPREADSHEET_ID,
        name="ColA",
        range="A2:A4",  # no sheet prefix — should default to sheet 0
        ctx=ctx,
    )

    named_range = _extract_named_range_from_body(mock_svc.last_batchupdate_body, "addNamedRange")
    range_sent = named_range.get("range")

    assert range_sent["startRowIndex"] == 1, f"Expected startRowIndex=1, got {range_sent['startRowIndex']}"
    assert range_sent["endRowIndex"] == 4, f"Expected endRowIndex=4, got {range_sent['endRowIndex']}"
    assert range_sent["startColumnIndex"] == 0, f"Expected startColumnIndex=0, got {range_sent['startColumnIndex']}"
    assert range_sent["endColumnIndex"] == 1, f"Expected endColumnIndex=1, got {range_sent['endColumnIndex']}"
    assert range_sent["sheetId"] == SHEET_ID


def test_create_named_range_range_is_not_string():
    """namedRange.range must NOT be a plain string."""
    mock_svc = _DualReturnMock(
        get_response=_make_spreadsheet_response(),
    )
    ctx = _FakeCtx(mock_svc)

    create_named_range(
        spreadsheet_id=SPREADSHEET_ID,
        name="StrTest",
        range="B3:C5",
        ctx=ctx,
    )

    named_range = _extract_named_range_from_body(mock_svc.last_batchupdate_body, "addNamedRange")
    range_sent = named_range.get("range")
    assert not isinstance(range_sent, str), (
        f"namedRange.range must not be a string, got: {range_sent!r}"
    )


# ---------------------------------------------------------------------------
# Bug 3: update_named_range must send GridRange, not a string
# ---------------------------------------------------------------------------

def test_update_named_range_sends_grid_range_not_string():
    """
    update_named_range must convert new_range to a GridRange dict.
    """
    mock_svc = _DualReturnMock(
        get_response=_make_spreadsheet_response(),
        batch_response={"replies": [{}]},
    )
    ctx = _FakeCtx(mock_svc)

    result = update_named_range(
        spreadsheet_id=SPREADSHEET_ID,
        name="ExistingRange",
        new_range="A1:B2",
        ctx=ctx,
    )

    assert result.get("success") is True, f"Expected success, got: {result}"

    named_range = _extract_named_range_from_body(mock_svc.last_batchupdate_body, "updateNamedRange")
    assert named_range is not None, "updateNamedRange request not found in batchUpdate body"

    range_sent = named_range.get("range")
    assert _is_grid_range(range_sent), (
        f"Expected namedRange.range to be a GridRange dict, got: {range_sent!r}"
    )


def test_update_named_range_not_found_returns_failure():
    """
    When the named range does not exist, update_named_range must return success=False.
    """
    mock_svc = _DualReturnMock(
        get_response=_make_spreadsheet_response(),
    )
    ctx = _FakeCtx(mock_svc)

    result = update_named_range(
        spreadsheet_id=SPREADSHEET_ID,
        name="NonExistent",
        new_range="A1:B2",
        ctx=ctx,
    )

    assert result.get("success") is False
    assert "NonExistent" in result.get("message", "")
