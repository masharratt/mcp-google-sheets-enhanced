# mcp-google-sheets-enhanced

Self-hosted [Model Context Protocol](https://modelcontextprotocol.io) server for Google Sheets,
served over SSE. A patched fork of [xing5/mcp-google-sheets](https://github.com/xing5/mcp-google-sheets)
with fixed conditional-formatting tools and SSE/credential hardening.

## What's different from upstream

- `apply_conditional_formatting` rewritten: condition-type alias map + uppercase passthrough,
  correct value building per condition type, and color-scale (gradient) heatmap support. Upstream
  effectively only handled `NOT_BLANK`.
- SSE transport + a separate health endpoint, packaged for container deploy.
- Service-account auth via a single base64 env var (`CREDENTIALS_CONFIG`).

Full patch rationale: [`CONDITIONAL_FORMATTING_FIX.md`](./CONDITIONAL_FORMATTING_FIX.md).

Known unfixed: `update_conditional_formatting` sets both `rule` and `newIndex` in a protobuf
`oneof` → 400. Clear and re-create rules instead.

## Architecture

- **MCP server**: SSE on `:8000`, endpoint `/sse`. Clients connect here.
- **Health server**: plain FastAPI on `:8001`, `/health` → `{"status":"healthy"}`. Runs in a
  background thread, independent of the MCP lifespan.
- **Auth**: `entrypoint.py` decodes `CREDENTIALS_CONFIG` (base64 service-account JSON) to
  `/app/credentials.json` and sets `GOOGLE_APPLICATION_CREDENTIALS`.

**New to Docker or Google Cloud?** Follow the plain-language
[Getting Started guide](./GETTING_STARTED.md) instead of the terse steps below.

## Prerequisites

1. A GCP project with the **Google Sheets API** and **Drive API** enabled.
2. A **service account** in that project; download its JSON key.
3. Share each target spreadsheet with the service-account email (Editor).

## Setup

```bash
cp .env.example .env
# base64-encode the service-account JSON (no line wraps):
base64 -w0 service-account.json
# paste the output as CREDENTIALS_CONFIG in .env, set GOOGLE_PROJECT_ID
```

## Run

```bash
docker build --no-cache -t mcp-google-sheets-enhanced:latest .   # --no-cache REQUIRED, see Gotchas
docker compose up -d --force-recreate
```

Verify:

```bash
curl -s localhost:8001/health                    # {"status":"healthy"}
curl -N --max-time 6 localhost:8000/sse           # emits `event: endpoint`, holds open
docker logs --tail 50 mcp-google-sheets-enhanced  # no auth ExceptionGroup after GET /sse
```

## MCP client config

```json
{ "mcpServers": { "google-sheets": { "type": "sse", "url": "http://localhost:8000/sse" } } }
```

## Tools

The server exposes 69 MCP tools across ten categories. All ranges use A1 notation (e.g. `A1:C10`, not `A1:C10!Sheet1`). Sheet names are case-sensitive.

### Reading data

| Tool | Purpose | Key parameters |
|------|---------|-----------------|
| `get_sheet_data` | Fetch cell values or full grid metadata from a range | `spreadsheet_id`, `sheet`, `range` (optional), `include_grid_data` (bool, default false) |
| `get_sheet_formulas` | Extract formulas from cells (returns formulas, not computed values) | `spreadsheet_id`, `sheet`, `range` (optional) |
| `get_multiple_sheet_data` | Fetch multiple ranges across sheets in one call | `queries` (list of `{spreadsheet_id, sheet, range}` dicts) |
| `get_multiple_spreadsheet_summary` | Get sheet names, headers, and first N rows from multiple spreadsheets | `spreadsheet_ids` (list), `rows_to_fetch` (int, default 5) |
| `get_spreadsheet_metadata` | Get spreadsheet-level metadata without fetching cell data | `spreadsheet_id`, `include_sheet_properties` (bool, default true) |
| `batch_get_values` | Read multiple A1 ranges from a single spreadsheet in one call | `spreadsheet_id`, `ranges` (list), `value_render_option` (string, default 'FORMATTED_VALUE'), `major_dimension` (string, default 'ROWS') |
| `list_sheets` | List all sheet tab names in a spreadsheet | `spreadsheet_id` |
| `list_validation_rules` | Get all data validation rules in a sheet or spreadsheet | `spreadsheet_id`, `sheet_name` (optional) |

### Writing data

| Tool | Purpose | Key parameters |
|------|---------|-----------------|
| `update_cells` | Update cell values in a single range | `spreadsheet_id`, `sheet`, `range`, `data` (2D array) |
| `batch_update_cells` | Update multiple non-contiguous ranges at once | `spreadsheet_id`, `sheet`, `ranges` (dict mapping range strings to 2D arrays) |
| `append_data` | Append rows after the last row with data in a range | `spreadsheet_id`, `sheet`, `data` (2D array), `range` (optional), `value_input_option` (string, default 'USER_ENTERED'), `insert_data_option` (string, default 'INSERT_ROWS') |
| `batch_clear_values` | Clear multiple ranges in one API call | `spreadsheet_id`, `ranges` (list of A1 notation strings) |
| `find_replace` | Find and replace text across a spreadsheet or sheet | `spreadsheet_id`, `find`, `replacement`, `sheet` (optional), `match_case` (bool, default false), `match_entire_cell` (bool, default false), `search_by_regex` (bool, default false), `include_formulas` (bool, default false) |
| `clear_data_validation` | Remove data validation rules from a range | `spreadsheet_id`, `sheet_name`, `range` |

### Spreadsheet and sheet management

| Tool | Purpose | Key parameters |
|------|---------|-----------------|
| `create_spreadsheet` | Create a new Google Spreadsheet | `title`, `folder_id` (optional) |
| `create_sheet` | Create a new sheet tab in an existing spreadsheet | `spreadsheet_id`, `title` |
| `duplicate_sheet` | Duplicate a sheet within the same spreadsheet | `spreadsheet_id`, `source_sheet`, `new_sheet_name`, `insert_index` (optional) |
| `list_spreadsheets` | List all spreadsheets in a Drive folder | `folder_id` (optional, uses configured default) |
| `list_folders` | List all folders in a Drive folder | `parent_folder_id` (optional) |
| `rename_sheet` | Rename a sheet tab | `spreadsheet`, `sheet`, `new_name` |
| `copy_sheet` | Copy a sheet from one spreadsheet to another | `src_spreadsheet`, `src_sheet`, `dst_spreadsheet`, `dst_sheet` |
| `set_sheet_visibility` | Show or hide a sheet tab | `spreadsheet_id`, `sheet`, `hidden` (bool) |
| `reorder_sheet` | Move a sheet tab to a new position | `spreadsheet_id`, `sheet`, `new_index` (0-based int) |
| `move_spreadsheet_to_folder` | Move a spreadsheet to a different Drive folder | `spreadsheet_id`, `target_folder_id`, `remove_from_current` (bool, default true) |
| `trash_spreadsheet` | Move a spreadsheet to Drive trash (recoverable, not permanent) | `spreadsheet_id` |
| `share_spreadsheet` | Share a spreadsheet with users by email and role | `spreadsheet_id`, `recipients` (list of `{email_address, role}` dicts), `send_notification` (bool, default true) |

### Rows and columns

| Tool | Purpose | Key parameters |
|------|---------|-----------------|
| `add_rows` | Insert rows into a sheet | `spreadsheet_id`, `sheet`, `count`, `start_row` (0-based, optional) |
| `add_columns` | Insert columns into a sheet | `spreadsheet_id`, `sheet`, `count`, `start_column` (0-based, optional) |
| `insert_rows` | Insert N rows at a given 0-based index with optional formatting inheritance | `spreadsheet_id`, `sheet`, `start_index` (0-based), `count`, `inherit_from_before` (bool, default true) |
| `insert_columns` | Insert N columns at a given 0-based index with optional formatting inheritance | `spreadsheet_id`, `sheet`, `start_index` (0-based), `count`, `inherit_from_before` (bool, default true) |
| `delete_columns` | Delete columns (convenience wrapper for column deletion) | `spreadsheet_id`, `sheet`, `start_index` (0-based), `end_index` (0-based, exclusive) |
| `delete_rows_columns` | Delete rows or columns | `spreadsheet_id`, `sheet_name`, `dimension` ('ROWS' or 'COLUMNS'), `start_index` (0-based), `end_index` (0-based, exclusive) |
| `freeze_dimensions` | Freeze rows and/or columns | `spreadsheet_id`, `sheet`, `frozen_rows` (optional), `frozen_columns` (optional) |
| `set_dimension_size` | Manually resize rows or columns to a given pixel size | `spreadsheet_id`, `sheet`, `dimension` ('ROWS' or 'COLUMNS'), `start_index` (0-based), `end_index` (0-based, exclusive), `pixel_size` (int) |
| `group_dimensions` | Group rows or columns | `spreadsheet_id`, `sheet`, `dimension` ('ROWS' or 'COLUMNS'), `start_index` (0-based), `end_index` (0-based, exclusive) |
| `ungroup_dimensions` | Ungroup rows or columns | `spreadsheet_id`, `sheet`, `dimension` ('ROWS' or 'COLUMNS'), `start_index` (0-based), `end_index` (0-based, exclusive) |
| `sort_range` | Sort a grid range by one or more columns | `spreadsheet_id`, `sheet`, `range` (A1 notation), `sort_specs` (list of dicts with `dimension_index` and `sort_order`) |
| `auto_resize_dimensions` | Auto-fit row heights and column widths | `spreadsheet_id`, `sheet_name`, `dimensions` (dict with `rows` and/or `columns` specs) |

### Formatting

| Tool | Purpose | Key parameters |
|------|---------|-----------------|
| `apply_text_formatting` | Font, alignment, text color, background color | `spreadsheet_id`, `sheet_name`, `range`, `text_formatting` dict with font_family, font_size, bold, italic, underline, strikethrough, foreground_color, background_color, horizontal_alignment, vertical_alignment, wrap_text |
| `apply_cell_formatting` | Comprehensive cell formatting (borders, alignment, number format, background via nested fields) | `spreadsheet_id`, `sheet_name`, `range`, `formatting` dict |
| `set_number_format` | Format cells as currency, date, percentage, text, etc. | `spreadsheet_id`, `sheet_name`, `range`, `number_format` (type: 'TEXT', 'NUMBER', 'CURRENCY', 'DATE', 'TIME', 'PERCENT'), `pattern` (optional custom format string) |
| `add_cell_borders` | Add borders with custom styles and colors | `spreadsheet_id`, `sheet_name`, `range`, `borders` dict |
| `merge_cells` | Merge or unmerge cells | `spreadsheet_id`, `sheet_name`, `range`, `merge_type` ('MERGE_ALL', 'MERGE_COLUMNS', 'MERGE_ROWS', 'UNMERGE') |
| `move_range` | Move cell data to a new location | `spreadsheet_id`, `sheet_name`, `source_range`, `destination` (dict with row/col indices) |
| `add_banding` | Apply alternating row or column color bands over a range | `spreadsheet_id`, `sheet`, `range`, `first_band_color` (RGB dict 0-1), `second_band_color` (RGB dict 0-1), `header_color` (optional RGB dict), `apply_to` (string, 'ROWS' or 'COLUMNS', default 'ROWS') |
| `remove_banding` | Remove alternating color banding by its ID | `spreadsheet_id`, `banded_range_id` (int) |

### Conditional formatting

| Tool | Purpose | Key parameters |
|------|---------|-----------------|
| `apply_conditional_formatting` | Highlight cells based on rules (numeric, text, date, formula, or color scales) | `spreadsheet_id`, `sheet_name`, `range`, `rules` (list of rule dicts) |
| `update_conditional_formatting` | Modify an existing conditional formatting rule | `spreadsheet_id`, `sheet_name`, `rule_id`, `rule` dict (KNOWN BUG: use clear + re-apply instead) |
| `clear_conditional_formatting` | Remove conditional formatting rules | `spreadsheet_id`, `sheet_name`, `rule_id` (optional; if omitted removes all rules from sheet) |

#### Conditional formatting: boolean rules

Boolean rules highlight cells matching a condition. Provide `condition_type`, `values`, and `format`:

```json
{
  "condition_type": "NUMBER_LESS",
  "values": ["0"],
  "format": {
    "background_color": {"red": 0.96, "green": 0.8, "blue": 0.8}
  }
}
```

Accepted condition types (case-insensitive, aliases also work):
- `NUMBER_LESS`, `NUMBER_LESS_THAN_EQ`, `NUMBER_GREATER`, `NUMBER_GREATER_THAN_EQ`, `NUMBER_EQ`, `NUMBER_NOT_EQ`, `NUMBER_BETWEEN`, `NUMBER_NOT_BETWEEN`
- `TEXT_CONTAINS`, `TEXT_NOT_CONTAINS`, `TEXT_EQ`, `TEXT_STARTS_WITH`, `TEXT_ENDS_WITH`
- `DATE_BEFORE`, `DATE_AFTER`, `DATE_BETWEEN`
- `CUSTOM_FORMULA` (pass the formula as a single value, e.g. `["=AND($I3<>\"\",TODAY()-$I3>30)"]`)
- `BLANK`, `NOT_BLANK`, `IS_EMPTY`

Values array: single value for most conditions, two values for `NUMBER_BETWEEN` / `NUMBER_NOT_BETWEEN` / `DATE_BETWEEN`, zero for `BLANK` / `NOT_BLANK` / `IS_EMPTY`.

#### Conditional formatting: color-scale rules (heatmaps)

Color scales map cell values to a gradient. Omit `condition_type` and use `gradient` (or `color_scale`) instead:

```json
{
  "gradient": {
    "minpoint": {
      "type": "MIN",
      "color": {"red": 0.34, "green": 0.73, "blue": 0.54}
    },
    "midpoint": {
      "type": "PERCENTILE",
      "value": "50",
      "color": {"red": 1, "green": 0.84, "blue": 0.4}
    },
    "maxpoint": {
      "type": "MAX",
      "color": {"red": 0.92, "green": 0.49, "blue": 0.45}
    }
  }
}
```

Point types: `MIN`, `MAX`, `NUMBER`, `PERCENT`, `PERCENTILE`. Include a `value` field for `NUMBER`, `PERCENT`, `PERCENTILE`.

### Data validation

| Tool | Purpose | Key parameters |
|------|---------|-----------------|
| `set_data_validation` | Add dropdown, list, checkbox, or numeric/date constraints to cells | `spreadsheet_id`, `sheet_name`, `range`, `validation_rule` (dict with `type`, `allow_invalid_data`, dropdown list/range, or constraint values) |
| `list_validation_rules` | Get all validation rules in a sheet or spreadsheet | `spreadsheet_id`, `sheet_name` (optional) |
| `clear_data_validation` | Remove validation rules from a range | `spreadsheet_id`, `sheet_name`, `range` |

### Protection

| Tool | Purpose | Key parameters |
|------|---------|-----------------|
| `protect_sheet_range` | Protect a sheet or range from editing | `spreadsheet_id`, `sheet_name`, `range` (optional), `protection_description`, `warning_only` (bool, default true), `requesting_users_can_edit` (bool, default false), `editor_emails` (list, optional) |
| `set_edit_permissions` | Grant edit access to specific users on a protected range | `spreadsheet_id`, `protection_id`, `users` (list of emails, optional), `roles` (list of roles, optional) |
| `remove_protection` | Remove a protection rule | `spreadsheet_id`, `protection_id` |

### Charts

| Tool | Purpose | Key parameters |
|------|---------|-----------------|
| `create_chart` | Create a new chart on a sheet | `spreadsheet_id`, `sheet_name`, `chart_type` ('COLUMN', 'BAR', 'LINE', 'PIE', 'SCATTER', 'AREA'), `data_range`, `position` (dict with rowIndex, columnIndex), `title` (optional) |
| `update_chart` | Modify chart title, axis labels, legend, etc. | `spreadsheet_id`, `sheet_name`, `chart_id`, `properties` (dict) |
| `delete_chart` | Delete a chart from a spreadsheet | `spreadsheet_id`, `chart_id` (int) |
| `move_resize_chart` | Reposition and resize a chart | `spreadsheet_id`, `sheet_name`, `chart_id`, `position` (dict with rowIndex, columnIndex, and optional width/height) |

### Named ranges

| Tool | Purpose | Key parameters |
|------|---------|-----------------|
| `create_named_range` | Define a named range for easier reference in formulas | `spreadsheet_id`, `name`, `range` (A1 notation or 'Sheet!A1:C10') |
| `list_named_ranges` | Get all named ranges in a spreadsheet | `spreadsheet_id` |
| `update_named_range` | Change which range a name refers to | `spreadsheet_id`, `name`, `new_range` |

### Filters

| Tool | Purpose | Key parameters |
|------|---------|-----------------|
| `create_filter` | Create a filter on a data range (header row required) | `spreadsheet_id`, `sheet_name`, `range` |
| `apply_filter_criteria` | Set filter conditions on specific columns | `spreadsheet_id`, `sheet_name`, `filter_id`, `criteria` (dict mapping column index to condition) |
| `clear_filter` | Remove all filters from a sheet | `spreadsheet_id`, `sheet_name` |
| `create_filter_view` | Create a named, saved filter view over a range | `spreadsheet_id`, `sheet`, `range`, `title`, `criteria` (optional dict) |
| `delete_filter_view` | Delete a named filter view by its ID | `spreadsheet_id`, `filter_view_id` (int) |

### Pivot tables

| Tool | Purpose | Key parameters |
|------|---------|-----------------|
| `create_pivot_table` | Create a pivot table in Google Sheets using an anchor cell | `spreadsheet_id`, `source_sheet`, `source_range` (A1 notation), `anchor_sheet`, `anchor_row` (0-based), `anchor_col` (0-based), `rows` (list of dicts with source_column_offset, show_totals, sort_order), `values` (list of dicts with source_column_offset, summarize_function), `columns` (optional list of dicts) |
| `delete_pivot_table` | Delete a pivot table by writing an empty cell at its anchor position | `spreadsheet_id`, `anchor_sheet`, `anchor_row` (0-based), `anchor_col` (0-based) |

### Developer metadata

| Tool | Purpose | Key parameters |
|------|---------|-----------------|
| `create_developer_metadata` | Attach a key/value label to a spreadsheet or sheet | `spreadsheet_id`, `metadata_key`, `metadata_value`, `visibility` (string, default 'DOCUMENT'), `location_type` (string, default 'SPREADSHEET'), `sheet` (optional, required when location_type is 'SHEET') |
| `search_developer_metadata` | Search developer metadata attached to a spreadsheet using dataFilters | `spreadsheet_id`, `metadata_key` (optional), `metadata_id` (optional int) |

#### Important formatting notes

- **Single-cell ranges in formatting tools must use the format `S8:S8`, not `S8`.** This applies to conditional formatting, data validation, borders, text formatting, and all range-based tools.
- **Cell background fills via `apply_text_formatting`.** Use the `background_color` field in the `text_formatting` dict. The `apply_cell_formatting` tool does not accept `background_color`.
- **Color objects** use 0-1 float values: `{"red": 1.0, "green": 0.5, "blue": 0.0}` (orange). Include `alpha` (0-1) for transparency.
- **Conditional formatting update bug.** `update_conditional_formatting` has a known protobuf oneof conflict. Clear and re-apply rules instead.

## Remote / public deploys (optional auth)

The MCP endpoint has no built-in authentication and the service account has Editor
access to your sheets. Do **not** expose `:8000` to the internet unprotected. By default
the compose file binds the server to `127.0.0.1` (local only).

An optional bearer-token gateway (Caddy) ships behind the `secure` compose profile:

```bash
# in .env:  set a token, optionally a domain for HTTPS
#   MCP_AUTH_TOKEN=$(openssl rand -hex 32)
#   DOMAIN=sheets.example.com      # blank = plain HTTP on AUTH_PORT
docker compose --profile secure up -d
```

- `DOMAIN` set → Caddy auto-provisions a Let's Encrypt cert and serves HTTPS on `:443`
  (port 80 must be reachable for the ACME challenge).
- `DOMAIN` blank → plain HTTP on `AUTH_PORT` (default 8080), token still enforced. Use
  behind an upstream TLS terminator only.

Every request must carry the token, including the MCP client:

```json
{ "mcpServers": { "google-sheets": {
  "type": "sse",
  "url": "https://sheets.example.com/sse",
  "headers": { "Authorization": "Bearer YOUR_MCP_AUTH_TOKEN" }
} } }
```

Requests without a valid `Authorization: Bearer <token>` get `401`. The unauthenticated
backend stays bound to localhost; the gateway reaches it over the internal compose network.

After any container restart, reconnect the client (`/mcp` in Claude Code). The SSE session is
server-side stateful; the old session 404s ("Could not find session").

## Gotchas

1. **`--no-cache` is mandatory.** `docker compose up -d --build` hits the layer cache and ships the
   OLD `server.py`. Always `docker build --no-cache` first, then `--force-recreate`.
2. **Never put `CREDENTIALS_CONFIG` under compose `environment:`.** It interpolates from the
   launching shell, not `env_file`, and an empty entry overrides `env_file`, breaking auth while
   `/health` stays green. Keep it in `env_file` only.
3. **`/health` lies.** The MCP lifespan runs per SSE connection, not at boot. Auth can be fully
   broken while health is 200. Trust the `/sse` curl + docker logs.
4. Single-cell ranges in formatting tools must be `S8:S8`, not `S8`.
5. Cell background fills: use `apply_text_formatting` with nested `background_color`.
   `apply_cell_formatting` rejects background.

## License

MIT. See [`LICENSE`](./LICENSE). Original work © 2025 Xing Wu; patches © 2026.
