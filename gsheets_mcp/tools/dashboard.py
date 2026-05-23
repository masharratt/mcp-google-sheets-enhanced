"""
Dashboard template tool: compose a styled dashboard into one batchUpdate call.

Loads a JSON template spec from gsheets_mcp/templates/<name>.json, substitutes
{title} and {data_range} placeholders, then dispatches each block to the
appropriate builder function, collecting all request dicts into one batchUpdate.
"""

import json
import os
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import Context

from gsheets_mcp.core import (
    mcp,
    _get_sheet_id,
    _a1_to_grid_range,
    _parse_row_col,
    _build_cell_format,
    _get_format_fields,
)
from gsheets_mcp.builders import (
    build_repeat_cell_request,
    build_merge_request,
    build_banding_request,
    build_freeze_request,
    build_chart_spec,
    build_chart_request,
    build_conditional_request,
)

# Directory containing JSON template files.
_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'templates')

# Whitelist: only names matching a file in _TEMPLATES_DIR are accepted.
def _known_templates():
    try:
        return {
            f[:-5]  # strip .json
            for f in os.listdir(_TEMPLATES_DIR)
            if f.endswith('.json')
        }
    except FileNotFoundError:
        return set()


def _load_template(name: str) -> Optional[Dict[str, Any]]:
    """Return parsed JSON spec for name, or None if not found."""
    if name not in _known_templates():
        return None
    path = os.path.join(_TEMPLATES_DIR, f'{name}.json')
    with open(path) as f:
        return json.load(f)


def _substitute(value: Any, title: str, data_range: str) -> Any:
    """Recursively replace {title} and {data_range} placeholders in strings."""
    if isinstance(value, str):
        return value.replace('{title}', title).replace('{data_range}', data_range)
    if isinstance(value, dict):
        return {k: _substitute(v, title, data_range) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(item, title, data_range) for item in value]
    return value


# ---------------------------------------------------------------------------
# Block handlers
# Each handler receives (block, sheet_id) and returns a list of request dicts.
# ---------------------------------------------------------------------------

def _handle_title_bar(block: Dict[str, Any], sheet_id: int) -> List[Dict[str, Any]]:
    """Title bar: merge cells then format with background + text."""
    grid_range = _a1_to_grid_range(sheet_id, block['range'])
    requests = []

    # 1. Merge the title row
    requests.append(build_merge_request(grid_range, 'MERGE_ALL'))

    # 2. Format: background color + text format
    cell_format: Dict[str, Any] = {}
    if 'background_color' in block:
        cell_format['backgroundColor'] = block['background_color']
    if 'text_format' in block:
        from gsheets_mcp.core import _map_text_format_keys
        cell_format['textFormat'] = _map_text_format_keys(block['text_format'])
    cell_format['horizontalAlignment'] = 'CENTER'

    fields = _get_format_fields(cell_format)
    if 'horizontalAlignment' in cell_format:
        fields.append('userEnteredFormat.horizontalAlignment')

    # Build the repeatCell with both format AND the title string value.
    text = block.get('text', '')
    repeat_req = {
        'repeatCell': {
            'range': grid_range,
            'cell': {
                'userEnteredValue': {'stringValue': text},
                'userEnteredFormat': cell_format,
            },
            'fields': ','.join(fields) + ',userEnteredValue',
        }
    }
    requests.append(repeat_req)

    return requests


def _build_styled_repeat_cell(
    grid_range: Dict[str, Any],
    cell_value: Dict[str, Any],
    cell_format: Dict[str, Any],
    extra_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Build a repeatCell request with a merged value and format.

    Args:
        grid_range: GridRange dict for the repeat.
        cell_value: userEnteredValue dict, e.g. {'stringValue': 'x'} or {'formulaValue': '=SUM(...)'}
        cell_format: userEnteredFormat dict (already fully assembled).
        extra_fields: Additional field-mask strings appended after the format fields.

    Returns:
        A repeatCell request dict.
    """
    fields = _get_format_fields(cell_format)
    if extra_fields:
        fields.extend(extra_fields)
    return {
        'repeatCell': {
            'range': grid_range,
            'cell': {
                'userEnteredValue': cell_value,
                'userEnteredFormat': cell_format,
            },
            'fields': ','.join(fields) + ',userEnteredValue',
        }
    }


# Default text format applied to value cells when value_text_format is absent.
_DEFAULT_VALUE_TEXT_FORMAT = {
    'bold': True,
    'fontSize': 20,
}


def _handle_kpi_card(block: Dict[str, Any], sheet_id: int) -> List[Dict[str, Any]]:
    """KPI card: merge cells + colored background + label text.

    Split mode (new): when both value_range and value_formula are present,
    renders the label in label_range and the formula value in value_range.

    Legacy mode: single merged cell with label string only (backward compatible).
    """
    from gsheets_mcp.core import _map_text_format_keys

    value_range_a1 = block.get('value_range')
    value_formula = block.get('value_formula')
    split_mode = bool(value_range_a1 and value_formula)

    bg_color = block.get('background_color')
    text_format_raw = block.get('text_format')

    if split_mode:
        label_range_a1 = block.get('label_range') or block['range']
        label_grid = _a1_to_grid_range(sheet_id, label_range_a1)
        value_grid = _a1_to_grid_range(sheet_id, value_range_a1)

        # Build label cell format.
        label_fmt: Dict[str, Any] = {}
        if bg_color:
            label_fmt['backgroundColor'] = bg_color
        if text_format_raw:
            label_fmt['textFormat'] = _map_text_format_keys(text_format_raw)
        label_fmt['horizontalAlignment'] = 'CENTER'
        label_fmt['verticalAlignment'] = 'MIDDLE'

        label_extra = [
            'userEnteredFormat.horizontalAlignment',
            'userEnteredFormat.verticalAlignment',
        ]

        # Build value cell format.
        value_text_format_raw = block.get('value_text_format', _DEFAULT_VALUE_TEXT_FORMAT)
        value_fmt: Dict[str, Any] = {}
        if bg_color:
            value_fmt['backgroundColor'] = bg_color
        value_fmt['textFormat'] = _map_text_format_keys(value_text_format_raw)
        value_fmt['horizontalAlignment'] = 'CENTER'
        value_fmt['verticalAlignment'] = 'MIDDLE'

        value_extra = [
            'userEnteredFormat.horizontalAlignment',
            'userEnteredFormat.verticalAlignment',
        ]

        number_format = block.get('value_number_format')
        if number_format:
            value_fmt['numberFormat'] = {
                'type': number_format['type'],
                'pattern': number_format.get('pattern', ''),
            }
            value_extra.append('userEnteredFormat.numberFormat')

        requests = [
            build_merge_request(label_grid, 'MERGE_ALL'),
            _build_styled_repeat_cell(
                label_grid,
                {'stringValue': block.get('label', '')},
                label_fmt,
                label_extra,
            ),
            build_merge_request(value_grid, 'MERGE_ALL'),
            _build_styled_repeat_cell(
                value_grid,
                {'formulaValue': value_formula},
                value_fmt,
                value_extra,
            ),
        ]
        return requests

    # Legacy mode: single merged cell, label string only.
    grid_range = _a1_to_grid_range(sheet_id, block['range'])
    requests = []

    requests.append(build_merge_request(grid_range, 'MERGE_ALL'))

    cell_format: Dict[str, Any] = {}
    if bg_color:
        cell_format['backgroundColor'] = bg_color
    if text_format_raw:
        cell_format['textFormat'] = _map_text_format_keys(text_format_raw)
    cell_format['horizontalAlignment'] = 'CENTER'
    cell_format['verticalAlignment'] = 'MIDDLE'

    fields = _get_format_fields(cell_format)
    fields.append('userEnteredFormat.horizontalAlignment')
    fields.append('userEnteredFormat.verticalAlignment')

    label = block.get('label', '')
    repeat_req = {
        'repeatCell': {
            'range': grid_range,
            'cell': {
                'userEnteredValue': {'stringValue': label},
                'userEnteredFormat': cell_format,
            },
            'fields': ','.join(fields) + ',userEnteredValue',
        }
    }
    requests.append(repeat_req)

    return requests


def _handle_banded_table(block: Dict[str, Any], sheet_id: int) -> List[Dict[str, Any]]:
    """Banded table: addBanding request."""
    grid_range = _a1_to_grid_range(sheet_id, block['range'])
    req = build_banding_request(
        grid_range=grid_range,
        header_color=block.get('header_color'),
        first_band_color=block.get('first_band_color'),
        second_band_color=block.get('second_band_color'),
        apply_to=block.get('apply_to', 'ROWS'),
    )
    return [req]


def _handle_freeze(block: Dict[str, Any], sheet_id: int) -> List[Dict[str, Any]]:
    """Freeze rows/columns: updateSheetProperties request."""
    req = build_freeze_request(
        sheet_id=sheet_id,
        frozen_rows=block.get('frozen_rows'),
        frozen_cols=block.get('frozen_cols'),
    )
    return [req]


def _handle_chart(block: Dict[str, Any], sheet_id: int) -> List[Dict[str, Any]]:
    """Chart: build chart spec from data_range + addChart request."""
    data_range = block.get('data_range', 'A1:B10')
    parsed = _parse_row_col(data_range)

    chart_spec = build_chart_spec(
        chart_type=block.get('chart_type', 'COLUMN'),
        title=block.get('title', 'Chart'),
        sheet_id=sheet_id,
        start_row=parsed['start_row'] - 1,   # _parse_row_col is 1-based
        end_row=parsed['end_row'],             # exclusive in 0-based
        start_col=parsed['start_col'] - 1,
        end_col=parsed['end_col'],
    )

    anchor_block = block.get('anchor', {})
    anchor = {
        'sheetId': sheet_id,
        'rowIndex': anchor_block.get('row', 0),
        'columnIndex': anchor_block.get('col', 0),
    }
    if 'offsetXPixels' in anchor_block:
        anchor['offsetXPixels'] = anchor_block['offsetXPixels']
    if 'offsetYPixels' in anchor_block:
        anchor['offsetYPixels'] = anchor_block['offsetYPixels']

    req = build_chart_request(chart_spec=chart_spec, anchor=anchor)
    return [req]


def _handle_conditional_gradient(block: Dict[str, Any], sheet_id: int) -> List[Dict[str, Any]]:
    """Conditional gradient rule on a range."""
    grid_range = _a1_to_grid_range(sheet_id, block['range'])

    min_color = block.get('min_color', {'red': 1.0, 'green': 0.6, 'blue': 0.6})
    mid_color = block.get('mid_color', {'red': 1.0, 'green': 1.0, 'blue': 0.7})
    max_color = block.get('max_color', {'red': 0.6, 'green': 1.0, 'blue': 0.6})

    rule_body = {
        'gradientRule': {
            'minpoint': {
                'color': min_color,
                'type': 'MIN',
            },
            'midpoint': {
                'color': mid_color,
                'type': 'PERCENTILE',
                'value': '50',
            },
            'maxpoint': {
                'color': max_color,
                'type': 'MAX',
            },
        }
    }

    req = build_conditional_request(
        grid_ranges=[grid_range],
        rule_body=rule_body,
        index=block.get('index', 0),
    )
    return [req]


# Dispatch table: block 'type' -> handler function
_BLOCK_HANDLERS = {
    'title_bar': _handle_title_bar,
    'kpi_card': _handle_kpi_card,
    'banded_table': _handle_banded_table,
    'freeze': _handle_freeze,
    'chart': _handle_chart,
    'conditional_gradient': _handle_conditional_gradient,
}


@mcp.tool()
def apply_dashboard_template(
    spreadsheet_id: str,
    sheet: str,
    template_name: str,
    data_range: str = None,
    title: str = None,
    ctx: Context = None,
) -> Dict[str, Any]:
    """
    Apply declarative dashboard template to sheet in one batchUpdate.

    Loads template from gsheets_mcp/templates/<template_name>.json, substitutes
    {title}/{data_range} placeholders, converts blocks to API requests.

    Args:
        spreadsheet_id: Spreadsheet ID
        sheet: Sheet name (case-sensitive)
        template_name: Built-in templates: 'kpi_overview', 'sales_dashboard'
        data_range: A1 range for chart/table data (e.g. 'A7:F50'). Defaults to template's banded_table range.
        title: Dashboard title. Defaults to template's default text.

    Returns:
        On success: {success: True, template, sheet, blocks_applied, request_count, spreadsheetId}
        On failure: {success: False, message: reason}
    """
    # --- Validate template ---
    spec = _load_template(template_name)
    if spec is None:
        return {
            'success': False,
            'message': (
                f"Unknown template '{template_name}'. "
                f"Available templates: {sorted(_known_templates())}"
            ),
        }

    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet)
    except Exception as e:
        return {'success': False, 'message': str(e)}

    # --- Resolve substitution values ---
    # Default data_range: use the banded_table block's range if present.
    effective_data_range = data_range
    if not effective_data_range:
        for block in spec.get('blocks', []):
            if block.get('type') == 'banded_table':
                effective_data_range = block.get('range', 'A1:F50')
                break
        if not effective_data_range:
            effective_data_range = 'A1:F50'

    effective_title = title or spec.get('name', template_name).replace('_', ' ').title()

    # --- Substitute placeholders in the spec ---
    blocks = _substitute(spec.get('blocks', []), effective_title, effective_data_range)

    # --- Build all requests ---
    all_requests: List[Dict[str, Any]] = []
    blocks_applied: List[str] = []

    for block in blocks:
        block_type = block.get('type', '')
        handler = _BLOCK_HANDLERS.get(block_type)
        if handler is None:
            # Skip unknown block types gracefully.
            continue
        try:
            requests = handler(block, sheet_id)
            all_requests.extend(requests)
            if block_type not in blocks_applied:
                blocks_applied.append(block_type)
        except Exception as e:
            return {
                'success': False,
                'message': f"Error processing block '{block_type}': {str(e)}",
            }

    if not all_requests:
        return {
            'success': False,
            'message': f"Template '{template_name}' produced no requests.",
        }

    # --- One batchUpdate ---
    try:
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': all_requests},
        ).execute()
    except Exception as e:
        return {'success': False, 'message': f"batchUpdate failed: {str(e)}"}

    return {
        'success': True,
        'template': template_name,
        'sheet': sheet,
        'blocks_applied': blocks_applied,
        'request_count': len(all_requests),
        'spreadsheetId': spreadsheet_id,
    }
