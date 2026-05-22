"""
Regression tests for apply_cell_formatting (gsheets_mcp/tools/format.py).

Bug: snake_case keys were passed raw into userEnteredFormat, causing HTTP 400
from the Google Sheets API. This suite fails against the original code and
passes after the fix.
"""

import pytest
from gsheets_mcp.tools.format import apply_cell_formatting


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _get_repeat_cell(mock_service):
    """Extract the repeatCell body from the last batchUpdate call."""
    kwargs = mock_service._last_call_kwargs.get('batchUpdate', {})
    body = kwargs.get('body', {})
    requests = body.get('requests', [])
    repeat_cells = [r for r in requests if 'repeatCell' in r]
    assert repeat_cells, f"No repeatCell found in batchUpdate requests: {requests}"
    return repeat_cells[0]['repeatCell']


def _user_entered_format(mock_service):
    return _get_repeat_cell(mock_service)['cell']['userEnteredFormat']


def _fields_mask(mock_service):
    return _get_repeat_cell(mock_service)['fields']


# ---------------------------------------------------------------------------
# test (a): text_format sub-keys must be camelCased
# ---------------------------------------------------------------------------

def test_text_format_camel_case(fake_ctx, mock_sheets_service):
    """
    formatting={"text_format": {"font_size": 14, "bold": True}}
    must produce userEnteredFormat.textFormat = {"fontSize": 14, "bold": True}
    NOT {"font_size": 14, "bold": True}.
    """
    result = apply_cell_formatting(
        spreadsheet_id="test-id",
        sheet_name="Sheet1",
        range="A1:B2",
        formatting={"text_format": {"font_size": 14, "bold": True}},
        ctx=fake_ctx,
    )

    assert result.get("success") is True, f"Tool returned failure: {result}"

    uef = _user_entered_format(mock_sheets_service)
    assert "textFormat" in uef, f"textFormat missing from userEnteredFormat: {uef}"

    tf = uef["textFormat"]
    # Must use camelCase keys
    assert "fontSize" in tf, f"Expected 'fontSize', got keys: {list(tf.keys())}"
    assert tf["fontSize"] == 14
    assert tf.get("bold") is True
    # Must NOT have the snake_case key
    assert "font_size" not in tf, f"snake_case key 'font_size' still present in textFormat"


# ---------------------------------------------------------------------------
# test (b): alignment dict keys must be expanded as sibling camelCase fields
# ---------------------------------------------------------------------------

def test_alignment_camel_case(fake_ctx, mock_sheets_service):
    """
    formatting={"alignment": {"horizontal": "CENTER", "vertical": "MIDDLE"}}
    must produce userEnteredFormat.horizontalAlignment = "CENTER"
    and userEnteredFormat.verticalAlignment = "MIDDLE".
    NOT a nested "alignment" key or bare "horizontal"/"vertical" keys.
    """
    result = apply_cell_formatting(
        spreadsheet_id="test-id",
        sheet_name="Sheet1",
        range="A1:B2",
        formatting={"alignment": {"horizontal": "CENTER", "vertical": "MIDDLE"}},
        ctx=fake_ctx,
    )

    assert result.get("success") is True, f"Tool returned failure: {result}"

    uef = _user_entered_format(mock_sheets_service)

    # Correct camelCase siblings
    assert uef.get("horizontalAlignment") == "CENTER", (
        f"horizontalAlignment not set correctly. userEnteredFormat: {uef}"
    )
    assert uef.get("verticalAlignment") == "MIDDLE", (
        f"verticalAlignment not set correctly. userEnteredFormat: {uef}"
    )

    # Must NOT contain the raw nested alignment dict or bare keys
    assert "alignment" not in uef, f"Raw 'alignment' key must not appear in userEnteredFormat"
    assert "horizontal" not in uef, f"Raw 'horizontal' key must not appear in userEnteredFormat"
    assert "vertical" not in uef, f"Raw 'vertical' key must not appear in userEnteredFormat"


# ---------------------------------------------------------------------------
# test (c): number_format passed through as numberFormat
# ---------------------------------------------------------------------------

def test_number_format_passed_through(fake_ctx, mock_sheets_service):
    """
    formatting={"number_format": {"type": "NUMBER", "pattern": "#,##0.00"}}
    must produce userEnteredFormat.numberFormat = {"type": "NUMBER", "pattern": "#,##0.00"}.
    """
    nf = {"type": "NUMBER", "pattern": "#,##0.00"}
    result = apply_cell_formatting(
        spreadsheet_id="test-id",
        sheet_name="Sheet1",
        range="A1:B2",
        formatting={"number_format": nf},
        ctx=fake_ctx,
    )

    assert result.get("success") is True, f"Tool returned failure: {result}"

    uef = _user_entered_format(mock_sheets_service)
    assert "numberFormat" in uef, f"numberFormat missing from userEnteredFormat: {uef}"
    assert uef["numberFormat"] == nf


# ---------------------------------------------------------------------------
# test (d): fields mask must use userEnteredFormat.<field> prefix
# ---------------------------------------------------------------------------

def test_fields_mask_uses_prefix(fake_ctx, mock_sheets_service):
    """
    The 'fields' string in the repeatCell request must use the
    'userEnteredFormat.<field>' prefix format (same as set_number_format),
    not bare field names like 'textFormat'.
    """
    apply_cell_formatting(
        spreadsheet_id="test-id",
        sheet_name="Sheet1",
        range="A1:B2",
        formatting={
            "text_format": {"bold": True},
            "alignment": {"horizontal": "LEFT"},
        },
        ctx=fake_ctx,
    )

    mask = _fields_mask(mock_sheets_service)
    # Every segment in the mask must be prefixed with userEnteredFormat.
    for segment in mask.split(","):
        segment = segment.strip()
        assert segment.startswith("userEnteredFormat."), (
            f"fields mask segment '{segment}' lacks 'userEnteredFormat.' prefix. Full mask: {mask}"
        )


# ---------------------------------------------------------------------------
# test (e): combined formatting builds correct full structure
# ---------------------------------------------------------------------------

def test_combined_formatting(fake_ctx, mock_sheets_service):
    """
    When text_format + alignment + number_format are all provided,
    the resulting userEnteredFormat must contain all mapped fields
    with correct camelCase keys.
    """
    result = apply_cell_formatting(
        spreadsheet_id="test-id",
        sheet_name="Sheet1",
        range="B3:D5",
        formatting={
            "text_format": {
                "bold": True,
                "font_size": 12,
                "font_family": "Arial",
                "foreground_color": {"red": 1.0, "green": 0.0, "blue": 0.0},
            },
            "alignment": {
                "horizontal": "RIGHT",
                "vertical": "TOP",
                "wrap_strategy": "WRAP",
            },
            "number_format": {"type": "CURRENCY", "pattern": "$#,##0.00"},
        },
        ctx=fake_ctx,
    )

    assert result.get("success") is True, f"Tool returned failure: {result}"

    uef = _user_entered_format(mock_sheets_service)

    # textFormat sub-keys
    tf = uef.get("textFormat", {})
    assert tf.get("bold") is True
    assert tf.get("fontSize") == 12
    assert tf.get("fontFamily") == "Arial"
    assert tf.get("foregroundColor") == {"red": 1.0, "green": 0.0, "blue": 0.0}
    assert "font_size" not in tf
    assert "font_family" not in tf
    assert "foreground_color" not in tf

    # alignment siblings
    assert uef.get("horizontalAlignment") == "RIGHT"
    assert uef.get("verticalAlignment") == "TOP"
    assert uef.get("wrapStrategy") == "WRAP"

    # numberFormat
    assert uef.get("numberFormat") == {"type": "CURRENCY", "pattern": "$#,##0.00"}
