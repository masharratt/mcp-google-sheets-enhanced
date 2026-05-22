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

- **MCP server** — SSE on `:8000`, endpoint `/sse`. Clients connect here.
- **Health server** — plain FastAPI on `:8001`, `/health` → `{"status":"healthy"}`. Runs in a
  background thread, independent of the MCP lifespan.
- **Auth** — `entrypoint.py` decodes `CREDENTIALS_CONFIG` (base64 service-account JSON) to
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

After any container restart, reconnect the client (`/mcp` in Claude Code). The SSE session is
server-side stateful; the old session 404s ("Could not find session").

## Gotchas

1. **`--no-cache` is mandatory.** `docker compose up -d --build` hits the layer cache and ships the
   OLD `server.py`. Always `docker build --no-cache` first, then `--force-recreate`.
2. **Never put `CREDENTIALS_CONFIG` under compose `environment:`.** It interpolates from the
   launching shell, not `env_file`, and an empty entry overrides `env_file` — breaking auth while
   `/health` stays green. Keep it in `env_file` only.
3. **`/health` lies.** The MCP lifespan runs per SSE connection, not at boot. Auth can be fully
   broken while health is 200. Trust the `/sse` curl + docker logs.
4. Single-cell ranges in formatting tools must be `S8:S8`, not `S8`.
5. Cell background fills: use `apply_text_formatting` with nested `background_color`.
   `apply_cell_formatting` rejects background.

## License

MIT. See [`LICENSE`](./LICENSE). Original work © 2025 Xing Wu; patches © 2026.
