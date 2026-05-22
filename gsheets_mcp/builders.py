"""
Pure request-builder functions for the Google Sheets batchUpdate API.

Each function accepts already-resolved values (integer sheetId, GridRange
dicts, plain config values) and returns a single request dict ready to be
placed inside a batchUpdate 'requests' list.

None of these functions make network calls, hold a reference to
sheets_service, or call .execute().  They are intentionally side-effect-free
so that a future dashboard-template tool can compose many request types into
one batchUpdate call.
"""

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Cell formatting
# ---------------------------------------------------------------------------

def build_repeat_cell_request(
    grid_range: Dict[str, Any],
    cell_format: Dict[str, Any],
    fields: List[str],
) -> Dict[str, Any]:
    """
    Build a repeatCell request dict.

    Args:
        grid_range: A GridRange dict (sheetId, startRowIndex, endRowIndex,
            startColumnIndex, endColumnIndex) as produced by _a1_to_grid_range
            or assembled inline from _parse_row_col results.
        cell_format: The userEnteredFormat dict (textFormat, backgroundColor,
            horizontalAlignment, etc.).
        fields: List of field-mask strings (e.g.
            ['userEnteredFormat.textFormat', 'userEnteredFormat.backgroundColor']).
            Joined with commas to form the 'fields' mask.

    Returns:
        {"repeatCell": {"range": ..., "cell": {"userEnteredFormat": ...}, "fields": ...}}
    """
    return {
        "repeatCell": {
            "range": grid_range,
            "cell": {
                "userEnteredFormat": cell_format,
            },
            "fields": ",".join(fields),
        }
    }


# ---------------------------------------------------------------------------
# Merge cells
# ---------------------------------------------------------------------------

def build_merge_request(
    grid_range: Dict[str, Any],
    merge_type: str,
) -> Dict[str, Any]:
    """
    Build a mergeCells request dict.

    Args:
        grid_range: A GridRange dict.
        merge_type: Google Sheets MergeType string ('MERGE_ALL', 'MERGE_COLUMNS',
            'MERGE_ROWS', 'UNMERGE').

    Returns:
        {"mergeCells": {"range": ..., "mergeType": ...}}
    """
    return {
        "mergeCells": {
            "range": grid_range,
            "mergeType": merge_type,
        }
    }


# ---------------------------------------------------------------------------
# Banding
# ---------------------------------------------------------------------------

def build_banding_request(
    grid_range: Dict[str, Any],
    header_color: Optional[Dict[str, float]],
    first_band_color: Optional[Dict[str, float]],
    second_band_color: Optional[Dict[str, float]],
    apply_to: str = "ROWS",
) -> Dict[str, Any]:
    """
    Build an addBanding request dict.

    Args:
        grid_range: A GridRange dict.
        header_color: Optional RGB dict (0-1 floats) for the header row/column.
            Pass None to omit.
        first_band_color: RGB dict (0-1 floats) for odd bands.
        second_band_color: RGB dict (0-1 floats) for even bands.
        apply_to: 'ROWS' (default) or 'COLUMNS'. Determines whether
            rowProperties or columnProperties is used.

    Returns:
        {"addBanding": {"bandedRange": {"range": ..., "rowProperties"/"columnProperties": {...}}}}
    """
    use_columns = apply_to.upper() == "COLUMNS"
    properties_key = "columnProperties" if use_columns else "rowProperties"

    band_properties: Dict[str, Any] = {}
    if first_band_color is not None:
        band_properties["firstBandColor"] = first_band_color
    if second_band_color is not None:
        band_properties["secondBandColor"] = second_band_color
    if header_color is not None:
        band_properties["headerColor"] = header_color

    banded_range = {
        "range": grid_range,
        properties_key: band_properties,
    }

    return {
        "addBanding": {
            "bandedRange": banded_range,
        }
    }


# ---------------------------------------------------------------------------
# Freeze dimensions
# ---------------------------------------------------------------------------

def build_freeze_request(
    sheet_id: int,
    frozen_rows: Optional[int],
    frozen_cols: Optional[int],
) -> Dict[str, Any]:
    """
    Build an updateSheetProperties request that freezes rows and/or columns.

    Only the counts/fields actually provided are included in the request,
    matching the behavior of the freeze_dimensions tool.

    Args:
        sheet_id: Integer sheet ID.
        frozen_rows: Number of rows to freeze, or None to leave unchanged.
        frozen_cols: Number of columns to freeze, or None to leave unchanged.

    Returns:
        {"updateSheetProperties": {"properties": {...}, "fields": "..."}}

    Raises:
        ValueError: If both frozen_rows and frozen_cols are None.
    """
    if frozen_rows is None and frozen_cols is None:
        raise ValueError("At least one of frozen_rows or frozen_cols must be provided.")

    grid_properties: Dict[str, Any] = {}
    fields_list: List[str] = []

    if frozen_rows is not None:
        grid_properties["frozenRowCount"] = frozen_rows
        fields_list.append("gridProperties.frozenRowCount")

    if frozen_cols is not None:
        grid_properties["frozenColumnCount"] = frozen_cols
        fields_list.append("gridProperties.frozenColumnCount")

    return {
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": grid_properties,
            },
            "fields": ",".join(fields_list),
        }
    }


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def build_chart_spec(
    chart_type: str,
    title: str,
    sheet_id: int,
    start_row: int,
    end_row: int,
    start_col: int,
    end_col: int,
) -> Dict[str, Any]:
    """
    Build a ChartSpec dict for a basic chart (COLUMN, BAR, LINE, PIE, SCATTER, AREA).

    This is a helper for build_chart_request and for create_chart to reuse.

    Args:
        chart_type: One of 'COLUMN', 'BAR', 'LINE', 'PIE', 'SCATTER', 'AREA'
            (already normalized to the Google enum string).
        title: Chart title string.
        sheet_id: Integer sheet ID for domain and series source ranges.
        start_row: 0-based start row index (from _parse_row_col result).
        end_row: Exclusive end row index.
        start_col: 0-based start column index.
        end_col: Exclusive end column index.

    Returns:
        A ChartSpec dict with title and basicChart body.
    """
    # Bar charts are horizontal: their value series must target the BOTTOM_AXIS.
    # Column/line/area/scatter charts plot values on the LEFT_AXIS.
    target_axis = "BOTTOM_AXIS" if chart_type == "BAR" else "LEFT_AXIS"
    return {
        "title": title,
        "basicChart": {
            "chartType": chart_type,
            "axis": [
                {"position": "BOTTOM_AXIS", "title": "Categories"},
                {"position": "LEFT_AXIS", "title": "Values"},
            ],
            "domains": [
                {
                    "domain": {
                        "sourceRange": {
                            "sources": [
                                {
                                    "sheetId": sheet_id,
                                    "startRowIndex": start_row,
                                    "endRowIndex": end_row,
                                    "startColumnIndex": start_col,
                                    "endColumnIndex": start_col + 1,
                                }
                            ]
                        }
                    }
                }
            ],
            # One series per data column. The Sheets API requires every
            # ChartSourceRange to be a single column (or single row); a series
            # spanning multiple columns is rejected with HTTP 400.
            "series": [
                {
                    "series": {
                        "sourceRange": {
                            "sources": [
                                {
                                    "sheetId": sheet_id,
                                    "startRowIndex": start_row,
                                    "endRowIndex": end_row,
                                    "startColumnIndex": col,
                                    "endColumnIndex": col + 1,
                                }
                            ]
                        }
                    },
                    "targetAxis": target_axis,
                }
                for col in range(start_col + 1, end_col)
            ],
            "headerCount": 1,
        },
    }


def build_chart_request(
    chart_spec: Dict[str, Any],
    anchor: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build an addChart request dict.

    Args:
        chart_spec: A fully-built ChartSpec dict (e.g. from build_chart_spec or
            assembled inline).
        anchor: A dict that may contain the anchorCell fields (sheetId,
            rowIndex, columnIndex) and optionally overlayPosition-level fields
            (offsetXPixels, offsetYPixels). Offset keys are lifted to the
            overlayPosition level; only the cell-address keys go into anchorCell.

    Returns:
        {"addChart": {"chart": {"spec": ..., "position": {"overlayPosition": {"anchorCell": ...}}}}}
    """
    _overlay_only_keys = {"offsetXPixels", "offsetYPixels"}
    anchor_cell = {k: v for k, v in anchor.items() if k not in _overlay_only_keys}

    overlay_position: Dict[str, Any] = {
        "anchorCell": anchor_cell,
    }
    # Lift pixel offsets to overlayPosition level if provided.
    if "offsetXPixels" in anchor:
        overlay_position["offsetXPixels"] = anchor["offsetXPixels"]
    if "offsetYPixels" in anchor:
        overlay_position["offsetYPixels"] = anchor["offsetYPixels"]

    return {
        "addChart": {
            "chart": {
                "spec": chart_spec,
                "position": {
                    "overlayPosition": overlay_position,
                },
            }
        }
    }


# ---------------------------------------------------------------------------
# Conditional formatting
# ---------------------------------------------------------------------------

def build_conditional_request(
    grid_ranges: List[Dict[str, Any]],
    rule_body: Dict[str, Any],
    index: int = 0,
) -> Dict[str, Any]:
    """
    Build an addConditionalFormatRule request dict.

    Args:
        grid_ranges: List of GridRange dicts that the rule applies to.
        rule_body: The rule body dict. For boolean rules this should be
            {'booleanRule': {...}}; for gradient rules {'gradientRule': {...}}.
            The 'ranges' key must NOT be included here; it is injected
            automatically from grid_ranges.
        index: Insertion index for the rule (default 0 = top of the list).

    Returns:
        {"addConditionalFormatRule": {"rule": {"ranges": [...], ...rule_body}, "index": index}}
    """
    return {
        "addConditionalFormatRule": {
            "rule": {
                "ranges": grid_ranges,
                **rule_body,
            },
            "index": index,
        }
    }
