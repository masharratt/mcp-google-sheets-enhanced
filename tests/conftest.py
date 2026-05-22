"""
Shared test fixtures for gsheets_mcp tests.

Provides mock services that replicate the chained call style used by tools:
  service.spreadsheets().values().get(...).execute()
  service.spreadsheets().batchUpdate(...).execute()
etc.
"""

import pytest
from unittest.mock import MagicMock


def _make_chained_mock(execute_return=None):
    """
    Return a MagicMock that supports arbitrary chained attribute/call access
    and has .execute() return execute_return.

    Usage:
        mock = _make_chained_mock({"values": [["a", "b"]]})
        mock.spreadsheets().values().get(spreadsheetId="x", range="A1").execute()
        # returns {"values": [["a", "b"]]}
    """
    chain = MagicMock()
    # Every attribute access or call on chain returns chain itself, so arbitrary
    # chaining works. The terminal .execute() is configured separately.
    chain.execute = MagicMock(return_value=execute_return if execute_return is not None else {})
    # Make __call__ and __getattr__ both return the same chain so chaining works.
    chain.__call__ = MagicMock(return_value=chain)
    # MagicMock already returns a new mock for attribute access, but we override
    # that to always return chain itself so the chain stays linked.
    chain.__getattr__ = lambda self, name: chain if name != 'execute' else chain.execute
    return chain


class _ChainableMock:
    """
    A minimal chainable mock that routes all attribute access and calls
    through itself so tests can assert on execute() return values and
    capture call arguments.

    Supports:
        service.spreadsheets().values().get(...).execute()
        service.spreadsheets().batchUpdate(...).execute()
        service.spreadsheets().sheets().copyTo(...).execute()
        service.spreadsheets().values().update(...).execute()
        service.spreadsheets().values().batchUpdate(...).execute()
        service.files().create(...).execute()
        service.files().list(...).execute()
        service.permissions().create(...).execute()
    """

    def __init__(self, execute_return=None):
        self._execute_return = execute_return if execute_return is not None else {}
        # Record the most recent call args for each terminal method.
        self._last_call_args = {}
        self._last_call_kwargs = {}

    def _clone(self, execute_return=None):
        """Return a new chainable mock, propagating execute_return."""
        return _ChainableMock(execute_return if execute_return is not None else self._execute_return)

    def __getattr__(self, name):
        # Return a callable that records its args and returns self (for chaining).
        def _method(*args, **kwargs):
            self._last_call_args[name] = args
            self._last_call_kwargs[name] = kwargs
            return self
        return _method

    def __call__(self, *args, **kwargs):
        return self

    def execute(self):
        return self._execute_return

    def set_execute_return(self, value):
        self._execute_return = value


@pytest.fixture
def mock_sheets_service():
    """
    A _ChainableMock wired as the sheets service.

    Set the return value of .execute() via:
        mock_sheets_service.set_execute_return({...})

    Capture what was passed to batchUpdate or values().update via:
        mock_sheets_service._last_call_kwargs['batchUpdate']
    """
    return _ChainableMock(execute_return={
        'spreadsheetId': 'test-id',
        'sheets': [{'properties': {'title': 'Sheet1', 'sheetId': 0}}]
    })


@pytest.fixture
def mock_drive_service():
    """
    A _ChainableMock wired as the drive service.
    """
    return _ChainableMock(execute_return={
        'files': [],
        'id': 'new-file-id',
        'name': 'Test Spreadsheet',
        'parents': ['root-folder-id']
    })


class _FakeLifespanContext:
    """Mimics SpreadsheetContext: sheets_service, drive_service, folder_id."""
    def __init__(self, sheets_service, drive_service, folder_id=None):
        self.sheets_service = sheets_service
        self.drive_service = drive_service
        self.folder_id = folder_id


class _FakeRequestContext:
    def __init__(self, lifespan_context):
        self.lifespan_context = lifespan_context


class _FakeCtx:
    def __init__(self, sheets_service, drive_service, folder_id=None):
        self.request_context = _FakeRequestContext(
            _FakeLifespanContext(sheets_service, drive_service, folder_id)
        )


@pytest.fixture
def fake_ctx(mock_sheets_service, mock_drive_service):
    """
    A fake Context exposing:
        ctx.request_context.lifespan_context.sheets_service
        ctx.request_context.lifespan_context.drive_service
        ctx.request_context.lifespan_context.folder_id
    Wired to mock_sheets_service and mock_drive_service fixtures.
    """
    return _FakeCtx(mock_sheets_service, mock_drive_service, folder_id='default-folder')


def assert_batchupdate_body(mock_service, expected_request_key):
    """
    Helper: assert that .batchUpdate was called and its body contained
    at least one request with the given top-level key.

    Returns the list of matched request dicts for further assertion.
    """
    kwargs = mock_service._last_call_kwargs.get('batchUpdate', {})
    body = kwargs.get('body', {})
    requests = body.get('requests', [])
    matched = [r for r in requests if expected_request_key in r]
    assert matched, (
        f"Expected a request with key '{expected_request_key}' in batchUpdate body.\n"
        f"Got requests: {requests}"
    )
    return matched
