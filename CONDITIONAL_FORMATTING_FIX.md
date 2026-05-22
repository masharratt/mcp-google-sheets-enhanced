# Conditional Formatting Fix + SSE/Build Gotchas

Date: 2026-05-21. File: `server.py`. Container: `mcp-google-sheets-enhanced` (SSE :8000, health :8001).

## 1. `apply_conditional_formatting` was broken

### Symptom
Only `condition_type=NOT_BLANK` worked. Every value-bearing rule failed:
- Lowercase aliases (`less_than`, `text_contains`) were forwarded raw as the Google
  `BooleanCondition.type` (invalid enum) and the value was double-quoted (`""0""`).
- Real Google enums (`NUMBER_LESS`, `CUSTOM_FORMULA`) passed the type check but the
  `values` array was dropped -> `requires exactly one ConditionValue, but 0 supplied`.

### Root cause (original `server.py` ~1149-1161)
```python
condition = {'type': condition_type}            # raw forward, no enum mapping
if condition_type in ['greater_than','less_than',...]:
    condition['values'] = [f'"{values[0]}"']    # bare double-quoted string, wrong shape
```
Three defects: (1) no alias->enum mapping, (2) values emitted as `'"0"'` strings instead
of `{'userEnteredValue': '0'}`, (3) value branch keyed on lowercase only, so real enums
never set `values`. `NOT_BLANK` only worked because it needs zero ConditionValues.

### Fix
Three module-level helpers + rewritten rule loop:
- `_normalize_condition_type()` - maps legacy aliases (`less_than`->`NUMBER_LESS`,
  `text_contains`->`TEXT_CONTAINS`, `formula_custom`->`CUSTOM_FORMULA`, ...) via
  `_CONDITION_TYPE_ALIASES`; real Google enums pass through upper-cased.
- `_build_condition_values()` - builds `[{'userEnteredValue': str(v)}]`, NO extra quoting.
  Returns 0 values for `BLANK`/`NOT_BLANK`/`IS_EMPTY`, 2 for `NUMBER_BETWEEN`/
  `DATE_BETWEEN`/`NUMBER_NOT_BETWEEN`, 1 otherwise (incl. `CUSTOM_FORMULA`).
- `_build_gradient_rule()` - NEW: emits Google `gradientRule` color-scale heatmaps from
  `minpoint`/`midpoint`/`maxpoint` (PointType MIN/MAX/NUMBER/PERCENT/PERCENTILE).

Loop now branches to `gradientRule` when the rule carries a `gradient`/`color_scale`
key, else normalizes type and attaches `values` only when non-empty (NOT_BLANK stays safe).

### Working call shapes (verified live)
```jsonc
// numeric threshold
{"condition_type":"NUMBER_LESS","values":["0"],"format":{"background_color":{"red":0.96,"green":0.8,"blue":0.8}}}
// formula
{"condition_type":"CUSTOM_FORMULA","values":["=AND($I3<>\"\",TODAY()-$I3>30)"],"format":{...}}
// text flag
{"condition_type":"NOT_BLANK","values":[],"format":{...}}
// color scale / heatmap
{"gradient":{"minpoint":{"type":"MIN","color":{"red":0.34,"green":0.73,"blue":0.54}},
             "midpoint":{"type":"PERCENTILE","value":"50","color":{"red":1,"green":0.84,"blue":0.4}},
             "maxpoint":{"type":"MAX","color":{"red":0.92,"green":0.49,"blue":0.45}}}}
```

## 2. SSE handshake died after rebuild (separate bug, same day)

### Symptom
`/mcp` reconnect -> `SSE error: The socket connection was closed unexpectedly`, while
`/health` stayed `200 healthy`.

### Root cause
`docker-compose.yml` had `CREDENTIALS_CONFIG=${CREDENTIALS_CONFIG}` under `environment:`.
Values under `environment:` interpolate from the **shell running `docker compose`**, not
from `env_file`, and an explicit empty entry **overrides** `env_file`. With the var unset
in the shell, the container got an empty value -> `entrypoint.py setup_credentials()` wrote
no `credentials.json` -> all auth paths failed. FastMCP runs the lifespan **per SSE
connection**, so the auth exception aborted every just-opened stream. `/health` is a
separate route with no lifespan, so it masked the failure.

### Fix
Removed the override line so the value flows from `env_file`:
```diff
   environment:
     - GOOGLE_PROJECT_ID=${GOOGLE_PROJECT_ID:-}
-    - CREDENTIALS_CONFIG=${CREDENTIALS_CONFIG}
```

## 3. Rebuild procedure (IMPORTANT)

```bash
docker build --no-cache -t mcp-google-sheets-enhanced:latest .   # --no-cache is REQUIRED
docker compose up -d --force-recreate
```
- `docker compose up -d --build` alone hits the layer cache and silently ships the OLD
  `server.py`. Use `--no-cache`.
- After any restart, the Claude Code MCP client must `/mcp` reconnect (SSE session is
  server-side stateful; the old session 404s with "Could not find session").

### Verify
```bash
curl -s localhost:8001/health                       # {"status":"healthy"}
curl -N --max-time 6 localhost:8000/sse              # emits `event: endpoint`, holds open
docker logs --tail 50 mcp-google-sheets-enhanced     # no auth ExceptionGroup after GET /sse
```

## Follow-ups (not done)
- `update_conditional_formatting` likely still has the old value-handling bug + a separate
  oneof error (`rule` and `newIndex` both set). Not routed through the new helpers. Use
  clear + re-apply instead.
- Optional: make `entrypoint.py` fail loud at boot when `CREDENTIALS_CONFIG` is empty so
  `/health` reflects auth state instead of masking it.
