"""
Conditional formatting tools and their private helpers.

The helpers _normalize_condition_type, _build_condition_values, and
_build_gradient_rule are used exclusively by this module, so they live here.
"""

from typing import List, Dict, Any

from mcp.server.fastmcp import Context

from gsheets_mcp.core import mcp, _get_sheet_id, _parse_row_col, _build_cell_format


# Maps this tool's legacy lowercase condition aliases to valid Google
# Sheets BooleanCondition.type enums. Real Google enums pass through
# unchanged (see _normalize_condition_type).
_CONDITION_TYPE_ALIASES = {
    'greater_than': 'NUMBER_GREATER',
    'greater_than_or_equal': 'NUMBER_GREATER_THAN_EQ',
    'less_than': 'NUMBER_LESS',
    'less_than_or_equal': 'NUMBER_LESS_THAN_EQ',
    'equal_to': 'NUMBER_EQ',
    'not_equal_to': 'NUMBER_NOT_EQ',
    'between': 'NUMBER_BETWEEN',
    'not_between': 'NUMBER_NOT_BETWEEN',
    'text_contains': 'TEXT_CONTAINS',
    'text_not_contains': 'TEXT_NOT_CONTAINS',
    'text_equal': 'TEXT_EQ',
    'text_starts_with': 'TEXT_STARTS_WITH',
    'text_ends_with': 'TEXT_ENDS_WITH',
    'date_before': 'DATE_BEFORE',
    'date_after': 'DATE_AFTER',
    'formula_custom': 'CUSTOM_FORMULA',
    'is_blank': 'BLANK',
    'is_not_blank': 'NOT_BLANK',
}

# Google BooleanCondition.type values that take ZERO ConditionValues.
_ZERO_VALUE_CONDITIONS = {
    'BLANK', 'NOT_BLANK', 'IS_EMPTY', 'TEXT_IS_EMAIL', 'TEXT_IS_URL',
    'DATE_IS_VALID',
}

# Conditions that take exactly TWO ConditionValues.
_TWO_VALUE_CONDITIONS = {'NUMBER_BETWEEN', 'NUMBER_NOT_BETWEEN', 'DATE_BETWEEN'}


def _normalize_condition_type(condition_type: str) -> str:
    """Map a condition_type to a valid Google BooleanCondition.type enum.

    Accepts both this tool's legacy lowercase aliases ("less_than") and the
    real Google enum strings ("NUMBER_LESS"). Unknown values are upper-cased
    and passed through so new Google enums work without a code change.
    """
    if not condition_type:
        return condition_type
    key = condition_type.strip()
    if key in _CONDITION_TYPE_ALIASES:
        return _CONDITION_TYPE_ALIASES[key]
    lowered = key.lower()
    if lowered in _CONDITION_TYPE_ALIASES:
        return _CONDITION_TYPE_ALIASES[lowered]
    # Already a Google enum (or an unknown one) -> pass through upper-cased.
    return key.upper()


def _build_condition_values(google_type: str, values: List[Any]) -> List[Dict[str, str]]:
    """Build a Google ConditionValue list: [{'userEnteredValue': '<raw>'}, ...].

    No extra quoting. Zero-value conditions return []; two-value conditions
    (NUMBER_BETWEEN, etc.) use the first two values; everything else uses one.
    """
    if google_type in _ZERO_VALUE_CONDITIONS:
        return []
    if not values:
        return []
    if google_type in _TWO_VALUE_CONDITIONS:
        return [{'userEnteredValue': str(v)} for v in values[:2]]
    # Single-value conditions (incl. CUSTOM_FORMULA, which expects the
    # formula string as its sole ConditionValue).
    return [{'userEnteredValue': str(values[0])}]


def _build_gradient_rule(gradient_spec: Dict[str, Any]) -> Dict[str, Any]:
    """Build a Google GradientRule (color-scale / heatmap) dict.

    gradient_spec keys: minpoint, midpoint (optional), maxpoint. Each is an
    InterpolationPoint: {color: {red,green,blue[,alpha]}, type: <PointType>,
    value: <str optional>}. PointType: MIN, MAX, NUMBER, PERCENT, PERCENTILE.
    """
    def _point(p: Dict[str, Any]) -> Dict[str, Any]:
        point: Dict[str, Any] = {}
        if 'color' in p:
            point['color'] = p['color']
        if p.get('type'):
            point['type'] = str(p['type']).upper()
        if p.get('value') is not None:
            point['value'] = str(p['value'])
        return point

    rule: Dict[str, Any] = {}
    if 'minpoint' in gradient_spec:
        rule['minpoint'] = _point(gradient_spec['minpoint'])
    if 'midpoint' in gradient_spec and gradient_spec['midpoint']:
        rule['midpoint'] = _point(gradient_spec['midpoint'])
    if 'maxpoint' in gradient_spec:
        rule['maxpoint'] = _point(gradient_spec['maxpoint'])
    return rule


@mcp.tool()
def apply_conditional_formatting(spreadsheet_id: str,
                                sheet_name: str,
                                range: str,
                                rules: List[Dict[str, Any]],
                                ctx: Context = None) -> Dict[str, Any]:
    """
    Apply conditional formatting rules to a cell range.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        range: Cell range in A1 notation (e.g., "A1:C10")
        rules: List of conditional formatting rules. Two kinds are supported.

            BOOLEAN rules (highlight cells matching a condition):
            - condition_type: a Google BooleanCondition.type enum
                (NUMBER_LESS, NUMBER_LESS_THAN_EQ, NUMBER_GREATER,
                 NUMBER_GREATER_THAN_EQ, NUMBER_EQ, NUMBER_BETWEEN,
                 TEXT_CONTAINS, TEXT_NOT_CONTAINS, TEXT_EQ, TEXT_STARTS_WITH,
                 TEXT_ENDS_WITH, DATE_BEFORE, DATE_AFTER, CUSTOM_FORMULA,
                 NOT_BLANK, BLANK, ...). Legacy lowercase aliases
                 ("less_than", "greater_than", "equal_to", "text_contains",
                 "text_starts_with", "text_ends_with", "between",
                 "formula_custom") are also accepted and mapped.
            - values: List of raw values for the condition. Single-value
                conditions take one; NUMBER_BETWEEN takes two; CUSTOM_FORMULA
                takes the formula string (e.g. "=$M1<0"); BLANK/NOT_BLANK take
                none.
            - format: Dict with formatting to apply when condition is met
                * text_format: font styling
                * background_color: cell background color
                * borders: border formatting

            GRADIENT / color-scale rules (heatmaps): pass a 'gradient' (or
            'color_scale') key on the rule instead of condition_type. Each
            interpolation point is {color: {red,green,blue}, type: <PointType>,
            value: <str>} where PointType is MIN/MAX/NUMBER/PERCENT/PERCENTILE.
            Shape: {"minpoint": {...}, "midpoint": {...}, "maxpoint": {...}}.
            midpoint is optional.
    Returns:
        Dictionary with success status and applied rules count
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)
        range_info = _parse_row_col(range)

        # Create conditional format rules
        conditional_format_rules = []

        for i, rule in enumerate(rules):
            condition_type = rule.get('condition_type')
            values = rule.get('values', [])
            format_to_apply = rule.get('format', {})

            ranges = [{
                'sheetId': sheet_id,
                'startRowIndex': range_info['start_row'] - 1,
                'endRowIndex': range_info['end_row'],
                'startColumnIndex': range_info['start_col'] - 1,
                'endColumnIndex': range_info['end_col']
            }]

            # Gradient / color-scale rule (heatmaps). Triggered by a
            # 'gradient' or 'color_scale' key on the rule instead of a
            # boolean condition_type.
            gradient_spec = rule.get('gradient') or rule.get('color_scale')
            if gradient_spec:
                gradient_rule = _build_gradient_rule(gradient_spec)
                conditional_format_rules.append({
                    'ranges': ranges,
                    'gradientRule': gradient_rule
                })
                continue

            # Boolean rule. Normalize condition_type to a valid Google
            # BooleanCondition.type enum (accepts both this tool's legacy
            # lowercase aliases and real Google enum strings).
            google_type = _normalize_condition_type(condition_type)
            condition = {'type': google_type}

            # Build ConditionValue list as {'userEnteredValue': '<raw>'}.
            # No extra quoting. Zero-value conditions (BLANK/NOT_BLANK/
            # IS_EMPTY/etc.) carry no values; NUMBER_BETWEEN carries two.
            condition_values = _build_condition_values(google_type, values)
            if condition_values:
                condition['values'] = condition_values

            conditional_format_rule = {
                'ranges': ranges,
                'booleanRule': {
                    'condition': condition,
                    'format': _build_cell_format(format_to_apply)
                }
            }

            conditional_format_rules.append(conditional_format_rule)

        # Add the conditional formatting rules
        requests = [{
            'addConditionalFormatRule': {
                'index': 0,  # Insert at the beginning
                'rule': rule
            }
        } for rule in conditional_format_rules]

        body = {'requests': requests}
        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body
        ).execute()

        return {
            "success": True,
            "message": f"Successfully applied {len(conditional_format_rules)} conditional formatting rules to {sheet_name}!{range}",
            "rules_applied": len(conditional_format_rules)
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error applying conditional formatting: {str(e)}"
        }


@mcp.tool()
def update_conditional_formatting(spreadsheet_id: str,
                                  sheet_name: str,
                                  rule_id: int,
                                  rule: Dict[str, Any],
                                  ctx: Context = None) -> Dict[str, Any]:
    """
    Update an existing conditional formatting rule.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        rule_id: ID of the rule to update
        rule: Dictionary with new rule configuration. Example:
            {
                "ranges": [{"sheetId": 0, "startRowIndex": 1, "endRowIndex": 10, "startColumnIndex": 1, "endColumnIndex": 5}],
                "booleanRule": {
                    "condition": {"type": "NUMBER_GREATER", "values": [{"userEnteredValue": "100"}]},
                    "format": {"backgroundColor": {"red": 1, "green": 0, "blue": 0}}
                }
            }

    Returns:
        Dictionary with success status and updated rule details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)

        # Ensure sheetId is set in ranges
        if 'ranges' in rule:
            for r in rule['ranges']:
                if 'sheetId' not in r:
                    r['sheetId'] = sheet_id

        # UpdateConditionalFormatRuleRequest has a oneof named 'instruction'
        # that covers 'rule' and 'newIndex' — only one may be set per request.
        # Rule-replacement: send index + rule (never newIndex alongside rule).
        request_body = {
            "requests": [
                {
                    "updateConditionalFormatRule": {
                        "index": rule_id,
                        "rule": rule
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
            "message": f"Conditional formatting rule {rule_id} updated",
            "rule_id": rule_id,
            "rule": rule
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error updating conditional formatting: {str(e)}"
        }


@mcp.tool()
def clear_conditional_formatting(spreadsheet_id: str,
                                 sheet_name: str,
                                 rule_id: int = None,
                                 ctx: Context = None) -> Dict[str, Any]:
    """
    Remove specific conditional formatting rules or all rules from a sheet.

    Args:
        spreadsheet_id: ID of the Google Spreadsheet
        sheet_name: Name of the sheet (case-sensitive)
        rule_id: ID of the rule to remove. If not provided, removes all rules from the sheet.

    Returns:
        Dictionary with success status and removal details
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    try:
        sheet_id = _get_sheet_id(sheets_service, spreadsheet_id, sheet_name)

        if rule_id is not None:
            # Remove specific rule
            request_body = {
                "requests": [
                    {
                        "deleteConditionalFormatRule": {
                            "index": rule_id,
                            "sheetId": sheet_id
                        }
                    }
                ]
            }
            message = f"Conditional formatting rule {rule_id} removed"
        else:
            # Remove all rules from sheet
            request_body = {
                "requests": [
                    {
                        "deleteConditionalFormatRule": {
                            "sheetId": sheet_id
                        }
                    }
                ]
            }
            message = f"All conditional formatting rules removed from {sheet_name}"

        response = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()

        return {
            "success": True,
            "message": message,
            "sheet_name": sheet_name
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error clearing conditional formatting: {str(e)}"
        }
