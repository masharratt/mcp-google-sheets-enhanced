"""
Regression tests for BUG 1 (move_resize_chart) and BUG 2 (update_chart).

BUG 1: move_resize_chart emitted updateChartPosition (invalid). Fix: updateEmbeddedObjectPosition.
BUG 2: update_chart sent only the changed property without the chart-type body. Fix: merge into existing spec.
"""

import pytest
from unittest.mock import MagicMock

from tests.conftest import assert_batchupdate_body


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SPREADSHEET_ID = "fake-spreadsheet-id"
SHEET_NAME = "Sheet1"
CHART_ID = 42


def _make_service_with_chart(chart_spec_body):
    """
    Return a mock sheets service whose spreadsheets().get().execute() returns
    a spreadsheet payload that contains one chart with the given spec body.
    The batchUpdate().execute() returns {}.
    """
    existing_spec = {
        "title": "Original Title",
        **chart_spec_body,  # e.g. basicChart: {...}
    }

    spreadsheet_payload = {
        "spreadsheetId": SPREADSHEET_ID,
        "sheets": [
            {
                "properties": {"sheetId": 0, "title": SHEET_NAME},
                "charts": [
                    {
                        "chartId": CHART_ID,
                        "spec": existing_spec,
                        "position": {
                            "overlayPosition": {
                                "anchorCell": {"sheetId": 0, "rowIndex": 0, "columnIndex": 0}
                            }
                        },
                    }
                ],
            }
        ],
    }

    # We need a mock that returns different things for get() vs batchUpdate().
    # Use a simple object approach.
    class _SwitchingService:
        def __init__(self):
            self._last_call_kwargs = {}

        def spreadsheets(self):
            return self

        def get(self, **kwargs):
            self._last_call_kwargs["get"] = kwargs
            return self

        def batchUpdate(self, **kwargs):
            self._last_call_kwargs["batchUpdate"] = kwargs
            return self

        def execute(self):
            # If the last call recorded was batchUpdate, return empty; else spreadsheet payload.
            if "batchUpdate" in self._last_call_kwargs:
                # After batchUpdate is called once, keep returning {} but
                # we need get() to still work for the initial fetch.
                # Check call order by inspecting kwargs keys.
                pass
            return spreadsheet_payload

    # Simpler: separate mock objects per call.
    svc = MagicMock()

    get_chain = MagicMock()
    get_chain.execute.return_value = spreadsheet_payload

    batch_chain = MagicMock()
    batch_chain.execute.return_value = {}

    # spreadsheets() returns a resource mock
    resource = MagicMock()
    resource.get.return_value = get_chain
    resource.batchUpdate.return_value = batch_chain

    svc.spreadsheets.return_value = resource
    return svc, resource


# ---------------------------------------------------------------------------
# BUG 1: move_resize_chart must use updateEmbeddedObjectPosition
# ---------------------------------------------------------------------------

class TestMoveResizeChart:
    def test_emits_updateEmbeddedObjectPosition_not_updateChartPosition(
        self, mock_sheets_service, fake_ctx
    ):
        """
        Before fix: batchUpdate body contains updateChartPosition (invalid API field).
        After fix:  batchUpdate body contains updateEmbeddedObjectPosition.
        """
        from gsheets_mcp.tools.charts import move_resize_chart

        position = {"rowIndex": 5, "columnIndex": 3, "offsetXPixels": 10, "offsetYPixels": 20}
        result = move_resize_chart(
            spreadsheet_id=SPREADSHEET_ID,
            sheet_name=SHEET_NAME,
            chart_id=CHART_ID,
            position=position,
            ctx=fake_ctx,
        )

        assert result.get("success") is True, f"Tool returned failure: {result}"

        # Must NOT have updateChartPosition
        kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
        body = kwargs.get("body", {})
        requests = body.get("requests", [])
        bad_keys = [r for r in requests if "updateChartPosition" in r]
        assert not bad_keys, (
            "batchUpdate body still contains invalid 'updateChartPosition'. "
            "Should use 'updateEmbeddedObjectPosition'."
        )

        # Must have updateEmbeddedObjectPosition
        matched = assert_batchupdate_body(mock_sheets_service, "updateEmbeddedObjectPosition")
        req = matched[0]["updateEmbeddedObjectPosition"]
        assert req["objectId"] == CHART_ID, f"objectId should be {CHART_ID}, got {req.get('objectId')}"

    def test_position_shape_anchorCell(self, mock_sheets_service, fake_ctx):
        """
        The newPosition must contain overlayPosition.anchorCell with sheetId, rowIndex, columnIndex.
        """
        from gsheets_mcp.tools.charts import move_resize_chart

        position = {"rowIndex": 2, "columnIndex": 4}
        move_resize_chart(
            spreadsheet_id=SPREADSHEET_ID,
            sheet_name=SHEET_NAME,
            chart_id=CHART_ID,
            position=position,
            ctx=fake_ctx,
        )

        kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
        req = kwargs["body"]["requests"][0]["updateEmbeddedObjectPosition"]
        overlay = req["newPosition"]["overlayPosition"]
        anchor = overlay["anchorCell"]
        assert "sheetId" in anchor
        assert anchor["rowIndex"] == 2
        assert anchor["columnIndex"] == 4

    def test_size_pixels_forwarded(self, mock_sheets_service, fake_ctx):
        """
        widthPixels and heightPixels in position dict should appear in overlayPosition.
        """
        from gsheets_mcp.tools.charts import move_resize_chart

        position = {
            "rowIndex": 0,
            "columnIndex": 0,
            "widthPixels": 600,
            "heightPixels": 400,
        }
        move_resize_chart(
            spreadsheet_id=SPREADSHEET_ID,
            sheet_name=SHEET_NAME,
            chart_id=CHART_ID,
            position=position,
            ctx=fake_ctx,
        )

        kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
        req = kwargs["body"]["requests"][0]["updateEmbeddedObjectPosition"]
        overlay = req["newPosition"]["overlayPosition"]
        assert overlay.get("widthPixels") == 600
        assert overlay.get("heightPixels") == 400

    def test_fields_mask_present(self, mock_sheets_service, fake_ctx):
        """
        updateEmbeddedObjectPosition requires a 'fields' mask.
        """
        from gsheets_mcp.tools.charts import move_resize_chart

        move_resize_chart(
            spreadsheet_id=SPREADSHEET_ID,
            sheet_name=SHEET_NAME,
            chart_id=CHART_ID,
            position={"rowIndex": 1, "columnIndex": 1},
            ctx=fake_ctx,
        )

        kwargs = mock_sheets_service._last_call_kwargs.get("batchUpdate", {})
        req = kwargs["body"]["requests"][0]["updateEmbeddedObjectPosition"]
        assert "fields" in req, "updateEmbeddedObjectPosition must include a 'fields' mask"


# ---------------------------------------------------------------------------
# BUG 2: update_chart must merge new property into existing chartSpec
# ---------------------------------------------------------------------------

class TestUpdateChart:
    def test_chartSpec_preserves_existing_chart_type_body(self):
        """
        Before fix: chartSpec sent is just the properties dict (e.g. {title: ...}).
        After fix:  chartSpec contains the merged spec including basicChart body.
        """
        from gsheets_mcp.tools.charts import update_chart

        existing_basic = {
            "chartType": "COLUMN",
            "axis": [{"position": "BOTTOM_AXIS", "title": "X"}],
        }
        svc, resource = _make_service_with_chart({"basicChart": existing_basic})

        class _FakeCtxDirect:
            class request_context:
                class lifespan_context:
                    sheets_service = svc

        result = update_chart(
            spreadsheet_id=SPREADSHEET_ID,
            sheet_name=SHEET_NAME,
            chart_id=CHART_ID,
            properties={"title": "New Title"},
            ctx=_FakeCtxDirect(),
        )

        assert result.get("success") is True, f"Tool returned failure: {result}"

        # Inspect what was sent to batchUpdate
        batch_call = resource.batchUpdate.call_args
        assert batch_call is not None, "batchUpdate was not called"
        body = batch_call.kwargs.get("body") or batch_call.args[0] if batch_call.args else batch_call.kwargs.get("body")
        # body could be a kwarg
        if body is None:
            body = batch_call[1].get("body") or batch_call[0][0] if batch_call[0] else {}

        requests = body.get("requests", [])
        update_reqs = [r for r in requests if "updateChartSpec" in r]
        assert update_reqs, f"No updateChartSpec in requests: {requests}"

        spec = update_reqs[0]["updateChartSpec"]["spec"]
        assert "basicChart" in spec, (
            f"Merged chartSpec is missing 'basicChart'. Got keys: {list(spec.keys())}"
        )
        assert spec["title"] == "New Title", f"Title not updated: {spec.get('title')}"

    def test_chartSpec_title_updated(self):
        """The new title must be reflected in the merged spec."""
        from gsheets_mcp.tools.charts import update_chart

        svc, resource = _make_service_with_chart({"basicChart": {"chartType": "LINE"}})

        class _FakeCtxDirect:
            class request_context:
                class lifespan_context:
                    sheets_service = svc

        update_chart(
            spreadsheet_id=SPREADSHEET_ID,
            sheet_name=SHEET_NAME,
            chart_id=CHART_ID,
            properties={"title": "Updated"},
            ctx=_FakeCtxDirect(),
        )

        batch_call = resource.batchUpdate.call_args
        body = batch_call.kwargs.get("body", {})
        spec = body["requests"][0]["updateChartSpec"]["spec"]
        assert spec["title"] == "Updated"

    def test_chartSpec_fetches_existing_spec_before_update(self):
        """
        The tool must call spreadsheets().get() to read the existing spec
        before sending batchUpdate.
        """
        from gsheets_mcp.tools.charts import update_chart

        svc, resource = _make_service_with_chart({"basicChart": {"chartType": "BAR"}})

        class _FakeCtxDirect:
            class request_context:
                class lifespan_context:
                    sheets_service = svc

        update_chart(
            spreadsheet_id=SPREADSHEET_ID,
            sheet_name=SHEET_NAME,
            chart_id=CHART_ID,
            properties={"title": "T"},
            ctx=_FakeCtxDirect(),
        )

        # spreadsheets().get() must have been called
        assert resource.get.called, "spreadsheets().get() was not called to fetch existing spec"
