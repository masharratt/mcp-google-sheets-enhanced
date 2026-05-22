"""
Unit tests for gsheets_mcp/builders.py.

All builders are pure functions (no network calls, no mocks needed).
Tests verify the top-level request key, nested shape, field masks, and
representative values for each builder.
"""

import pytest

from gsheets_mcp.builders import (
    build_repeat_cell_request,
    build_merge_request,
    build_banding_request,
    build_freeze_request,
    build_chart_spec,
    build_chart_request,
    build_conditional_request,
)


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

GRID_RANGE = {
    "sheetId": 42,
    "startRowIndex": 0,
    "endRowIndex": 10,
    "startColumnIndex": 0,
    "endColumnIndex": 4,
}

RED_COLOR = {"red": 1.0, "green": 0.0, "blue": 0.0}
BLUE_COLOR = {"red": 0.0, "green": 0.0, "blue": 1.0}
WHITE_COLOR = {"red": 1.0, "green": 1.0, "blue": 1.0}


# ---------------------------------------------------------------------------
# build_repeat_cell_request
# ---------------------------------------------------------------------------

class TestBuildRepeatCellRequest:
    def test_top_level_key(self):
        result = build_repeat_cell_request(
            grid_range=GRID_RANGE,
            cell_format={"backgroundColor": RED_COLOR},
            fields=["userEnteredFormat.backgroundColor"],
        )
        assert "repeatCell" in result

    def test_range_forwarded(self):
        result = build_repeat_cell_request(
            grid_range=GRID_RANGE,
            cell_format={"backgroundColor": RED_COLOR},
            fields=["userEnteredFormat.backgroundColor"],
        )
        assert result["repeatCell"]["range"] == GRID_RANGE

    def test_cell_format_nested_under_userEnteredFormat(self):
        cell_fmt = {"textFormat": {"bold": True}}
        result = build_repeat_cell_request(
            grid_range=GRID_RANGE,
            cell_format=cell_fmt,
            fields=["userEnteredFormat.textFormat"],
        )
        assert result["repeatCell"]["cell"]["userEnteredFormat"] == cell_fmt

    def test_fields_joined_as_comma_string(self):
        fields = ["userEnteredFormat.textFormat", "userEnteredFormat.backgroundColor"]
        result = build_repeat_cell_request(
            grid_range=GRID_RANGE,
            cell_format={"textFormat": {}, "backgroundColor": RED_COLOR},
            fields=fields,
        )
        assert result["repeatCell"]["fields"] == ",".join(fields)

    def test_single_field(self):
        result = build_repeat_cell_request(
            grid_range=GRID_RANGE,
            cell_format={"numberFormat": {"type": "NUMBER"}},
            fields=["userEnteredFormat.numberFormat"],
        )
        assert result["repeatCell"]["fields"] == "userEnteredFormat.numberFormat"


# ---------------------------------------------------------------------------
# build_merge_request
# ---------------------------------------------------------------------------

class TestBuildMergeRequest:
    def test_top_level_key(self):
        result = build_merge_request(grid_range=GRID_RANGE, merge_type="MERGE_ALL")
        assert "mergeCells" in result

    def test_range_forwarded(self):
        result = build_merge_request(grid_range=GRID_RANGE, merge_type="MERGE_ALL")
        assert result["mergeCells"]["range"] == GRID_RANGE

    def test_merge_type_forwarded(self):
        for mt in ("MERGE_ALL", "MERGE_COLUMNS", "MERGE_ROWS", "UNMERGE"):
            result = build_merge_request(grid_range=GRID_RANGE, merge_type=mt)
            assert result["mergeCells"]["mergeType"] == mt


# ---------------------------------------------------------------------------
# build_banding_request
# ---------------------------------------------------------------------------

class TestBuildBandingRequest:
    def test_top_level_key(self):
        result = build_banding_request(
            grid_range=GRID_RANGE,
            header_color=None,
            first_band_color=WHITE_COLOR,
            second_band_color=BLUE_COLOR,
        )
        assert "addBanding" in result

    def test_banded_range_key_present(self):
        result = build_banding_request(
            grid_range=GRID_RANGE,
            header_color=None,
            first_band_color=WHITE_COLOR,
            second_band_color=BLUE_COLOR,
        )
        assert "bandedRange" in result["addBanding"]

    def test_range_forwarded(self):
        result = build_banding_request(
            grid_range=GRID_RANGE,
            header_color=None,
            first_band_color=WHITE_COLOR,
            second_band_color=BLUE_COLOR,
        )
        assert result["addBanding"]["bandedRange"]["range"] == GRID_RANGE

    def test_row_properties_default(self):
        result = build_banding_request(
            grid_range=GRID_RANGE,
            header_color=None,
            first_band_color=WHITE_COLOR,
            second_band_color=BLUE_COLOR,
        )
        banded = result["addBanding"]["bandedRange"]
        assert "rowProperties" in banded
        assert "columnProperties" not in banded

    def test_column_properties_when_apply_to_columns(self):
        result = build_banding_request(
            grid_range=GRID_RANGE,
            header_color=None,
            first_band_color=WHITE_COLOR,
            second_band_color=BLUE_COLOR,
            apply_to="COLUMNS",
        )
        banded = result["addBanding"]["bandedRange"]
        assert "columnProperties" in banded
        assert "rowProperties" not in banded

    def test_header_color_included_when_provided(self):
        result = build_banding_request(
            grid_range=GRID_RANGE,
            header_color=RED_COLOR,
            first_band_color=WHITE_COLOR,
            second_band_color=BLUE_COLOR,
        )
        props = result["addBanding"]["bandedRange"]["rowProperties"]
        assert props["headerColor"] == RED_COLOR

    def test_header_color_omitted_when_none(self):
        result = build_banding_request(
            grid_range=GRID_RANGE,
            header_color=None,
            first_band_color=WHITE_COLOR,
            second_band_color=BLUE_COLOR,
        )
        props = result["addBanding"]["bandedRange"]["rowProperties"]
        assert "headerColor" not in props

    def test_band_colors_set(self):
        result = build_banding_request(
            grid_range=GRID_RANGE,
            header_color=None,
            first_band_color=WHITE_COLOR,
            second_band_color=BLUE_COLOR,
        )
        props = result["addBanding"]["bandedRange"]["rowProperties"]
        assert props["firstBandColor"] == WHITE_COLOR
        assert props["secondBandColor"] == BLUE_COLOR


# ---------------------------------------------------------------------------
# build_freeze_request
# ---------------------------------------------------------------------------

class TestBuildFreezeRequest:
    def test_top_level_key(self):
        result = build_freeze_request(sheet_id=0, frozen_rows=2, frozen_cols=None)
        assert "updateSheetProperties" in result

    def test_sheet_id_in_properties(self):
        result = build_freeze_request(sheet_id=7, frozen_rows=1, frozen_cols=None)
        assert result["updateSheetProperties"]["properties"]["sheetId"] == 7

    def test_frozen_rows_only(self):
        result = build_freeze_request(sheet_id=0, frozen_rows=3, frozen_cols=None)
        props = result["updateSheetProperties"]["properties"]["gridProperties"]
        assert props["frozenRowCount"] == 3
        assert "frozenColumnCount" not in props
        assert result["updateSheetProperties"]["fields"] == "gridProperties.frozenRowCount"

    def test_frozen_cols_only(self):
        result = build_freeze_request(sheet_id=0, frozen_rows=None, frozen_cols=2)
        props = result["updateSheetProperties"]["properties"]["gridProperties"]
        assert props["frozenColumnCount"] == 2
        assert "frozenRowCount" not in props
        assert result["updateSheetProperties"]["fields"] == "gridProperties.frozenColumnCount"

    def test_both_frozen(self):
        result = build_freeze_request(sheet_id=0, frozen_rows=1, frozen_cols=2)
        props = result["updateSheetProperties"]["properties"]["gridProperties"]
        assert props["frozenRowCount"] == 1
        assert props["frozenColumnCount"] == 2
        fields = result["updateSheetProperties"]["fields"]
        assert "gridProperties.frozenRowCount" in fields
        assert "gridProperties.frozenColumnCount" in fields

    def test_raises_when_both_none(self):
        with pytest.raises(ValueError):
            build_freeze_request(sheet_id=0, frozen_rows=None, frozen_cols=None)


# ---------------------------------------------------------------------------
# build_chart_spec
# ---------------------------------------------------------------------------

class TestBuildChartSpec:
    def _spec(self, **kwargs):
        defaults = dict(
            chart_type="COLUMN",
            title="Test Chart",
            sheet_id=0,
            start_row=0,
            end_row=10,
            start_col=0,
            end_col=4,
        )
        defaults.update(kwargs)
        return build_chart_spec(**defaults)

    def test_title_set(self):
        assert self._spec(title="My Chart")["title"] == "My Chart"

    def test_basic_chart_key_present(self):
        assert "basicChart" in self._spec()

    def test_chart_type_forwarded(self):
        assert self._spec(chart_type="LINE")["basicChart"]["chartType"] == "LINE"

    def test_axes_present(self):
        axes = self._spec()["basicChart"]["axis"]
        positions = [a["position"] for a in axes]
        assert "BOTTOM_AXIS" in positions
        assert "LEFT_AXIS" in positions

    def test_domain_source_range_shape(self):
        spec = self._spec(sheet_id=5, start_row=1, end_row=11, start_col=2, end_col=6)
        source = spec["basicChart"]["domains"][0]["domain"]["sourceRange"]["sources"][0]
        assert source["sheetId"] == 5
        assert source["startRowIndex"] == 1
        assert source["endRowIndex"] == 11
        # Domain is only the first column
        assert source["startColumnIndex"] == 2
        assert source["endColumnIndex"] == 3

    def test_series_source_range_shape(self):
        spec = self._spec(sheet_id=5, start_row=1, end_row=11, start_col=2, end_col=6)
        source = spec["basicChart"]["series"][0]["series"]["sourceRange"]["sources"][0]
        assert source["sheetId"] == 5
        assert source["startRowIndex"] == 1
        assert source["endRowIndex"] == 11
        # First series is the single column immediately after the domain.
        assert source["startColumnIndex"] == 3
        assert source["endColumnIndex"] == 4

    def test_one_series_per_data_column(self):
        """
        Regression (live HttpError 400): the Sheets API rejects a series whose
        source range spans more than one column ('ranges require all rows or all
        columns to have length of 1'). A multi-column data range must produce one
        single-column series per data column, not one wide series.
        """
        # start_col=2 (domain col 2), end_col=6 -> data cols 3,4,5 -> 3 series.
        spec = self._spec(start_col=2, end_col=6)
        series = spec["basicChart"]["series"]
        assert len(series) == 3
        for s in series:
            src = s["series"]["sourceRange"]["sources"][0]
            assert src["endColumnIndex"] - src["startColumnIndex"] == 1, (
                "every series source must be exactly one column wide"
            )
        cols = [s["series"]["sourceRange"]["sources"][0]["startColumnIndex"] for s in series]
        assert cols == [3, 4, 5]

    def test_header_count(self):
        assert self._spec()["basicChart"]["headerCount"] == 1

    def test_non_bar_series_target_left_axis(self):
        for ct in ("COLUMN", "LINE", "AREA"):
            spec = self._spec(chart_type=ct)
            for s in spec["basicChart"]["series"]:
                assert s["targetAxis"] == "LEFT_AXIS"

    def test_bar_series_target_bottom_axis(self):
        """
        Regression (live HttpError 400): 'Bar charts series may only target the
        BOTTOM_AXIS.' A BAR chart's value series must target BOTTOM_AXIS, unlike
        COLUMN/LINE which use LEFT_AXIS.
        """
        spec = self._spec(chart_type="BAR")
        for s in spec["basicChart"]["series"]:
            assert s["targetAxis"] == "BOTTOM_AXIS"


# ---------------------------------------------------------------------------
# build_chart_request
# ---------------------------------------------------------------------------

class TestBuildChartRequest:
    def _anchor(self, **kwargs):
        base = {"sheetId": 0, "rowIndex": 5, "columnIndex": 3}
        base.update(kwargs)
        return base

    def _spec(self):
        return {"title": "Chart", "basicChart": {"chartType": "BAR"}}

    def test_top_level_key(self):
        result = build_chart_request(chart_spec=self._spec(), anchor=self._anchor())
        assert "addChart" in result

    def test_spec_forwarded(self):
        spec = self._spec()
        result = build_chart_request(chart_spec=spec, anchor=self._anchor())
        assert result["addChart"]["chart"]["spec"] is spec

    def test_position_shape(self):
        anchor = self._anchor()
        result = build_chart_request(chart_spec=self._spec(), anchor=anchor)
        overlay = result["addChart"]["chart"]["position"]["overlayPosition"]
        assert "anchorCell" in overlay
        # anchorCell contains only cell-address keys
        ac = overlay["anchorCell"]
        assert ac["sheetId"] == anchor["sheetId"]
        assert ac["rowIndex"] == anchor["rowIndex"]
        assert ac["columnIndex"] == anchor["columnIndex"]

    def test_pixel_offsets_forwarded_from_anchor(self):
        anchor = self._anchor(offsetXPixels=10, offsetYPixels=20)
        result = build_chart_request(chart_spec=self._spec(), anchor=anchor)
        overlay = result["addChart"]["chart"]["position"]["overlayPosition"]
        # Offsets are at overlayPosition level, not inside anchorCell
        assert overlay["offsetXPixels"] == 10
        assert overlay["offsetYPixels"] == 20
        assert "offsetXPixels" not in overlay["anchorCell"]
        assert "offsetYPixels" not in overlay["anchorCell"]

    def test_no_pixel_offsets_when_absent(self):
        anchor = self._anchor()  # no offsetXPixels/offsetYPixels
        result = build_chart_request(chart_spec=self._spec(), anchor=anchor)
        overlay = result["addChart"]["chart"]["position"]["overlayPosition"]
        assert "offsetXPixels" not in overlay
        assert "offsetYPixels" not in overlay


# ---------------------------------------------------------------------------
# build_conditional_request
# ---------------------------------------------------------------------------

class TestBuildConditionalRequest:
    def _ranges(self):
        return [GRID_RANGE]

    def _boolean_body(self):
        return {
            "booleanRule": {
                "condition": {"type": "NUMBER_GREATER", "values": [{"userEnteredValue": "100"}]},
                "format": {"backgroundColor": RED_COLOR},
            }
        }

    def _gradient_body(self):
        return {
            "gradientRule": {
                "minpoint": {"color": BLUE_COLOR, "type": "MIN"},
                "maxpoint": {"color": RED_COLOR, "type": "MAX"},
            }
        }

    def test_top_level_key(self):
        result = build_conditional_request(
            grid_ranges=self._ranges(), rule_body=self._boolean_body()
        )
        assert "addConditionalFormatRule" in result

    def test_ranges_in_rule(self):
        result = build_conditional_request(
            grid_ranges=self._ranges(), rule_body=self._boolean_body()
        )
        assert result["addConditionalFormatRule"]["rule"]["ranges"] == self._ranges()

    def test_boolean_rule_body_merged(self):
        result = build_conditional_request(
            grid_ranges=self._ranges(), rule_body=self._boolean_body()
        )
        rule = result["addConditionalFormatRule"]["rule"]
        assert "booleanRule" in rule

    def test_gradient_rule_body_merged(self):
        result = build_conditional_request(
            grid_ranges=self._ranges(), rule_body=self._gradient_body()
        )
        rule = result["addConditionalFormatRule"]["rule"]
        assert "gradientRule" in rule

    def test_index_default_zero(self):
        result = build_conditional_request(
            grid_ranges=self._ranges(), rule_body=self._boolean_body()
        )
        assert result["addConditionalFormatRule"]["index"] == 0

    def test_index_custom(self):
        result = build_conditional_request(
            grid_ranges=self._ranges(), rule_body=self._boolean_body(), index=3
        )
        assert result["addConditionalFormatRule"]["index"] == 3

    def test_multiple_ranges(self):
        ranges = [GRID_RANGE, {**GRID_RANGE, "sheetId": 1}]
        result = build_conditional_request(
            grid_ranges=ranges, rule_body=self._boolean_body()
        )
        assert len(result["addConditionalFormatRule"]["rule"]["ranges"]) == 2

    def test_rule_body_keys_do_not_include_ranges(self):
        # ranges must NOT be duplicated inside rule_body
        body_with_ranges = {**self._boolean_body(), "ranges": self._ranges()}
        result = build_conditional_request(
            grid_ranges=self._ranges(), rule_body=body_with_ranges
        )
        rule = result["addConditionalFormatRule"]["rule"]
        # ranges appears once (from grid_ranges), not doubled
        assert rule["ranges"] == self._ranges()
