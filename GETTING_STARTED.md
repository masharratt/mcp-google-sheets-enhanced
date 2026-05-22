# Getting Started (Plain-Language Guide)

This guide gets the Google Sheets server running without assuming you know Docker or Google
Cloud. Follow it top to bottom. Set-up takes about 20 minutes, mostly clicking in Google's
website. You do it once.

> **What this does:** it lets an AI assistant (or other tool) read and edit your Google Sheets
> for you. You give it permission once, through a "robot account" that you control and can shut
> off any time.

---

## Step 1 — Create a Google Cloud project

1. Go to <https://console.cloud.google.com/>.
2. Top bar, click the project dropdown → **New Project**. Name it anything (e.g. "sheets-bot").
3. Click **Create**, then wait for it to finish and select the new project.

## Step 2 — Turn on the two APIs it needs

1. In the search bar at the top, type **Google Sheets API**, open it, click **Enable**.
2. Search **Google Drive API**, open it, click **Enable**.

(These are free for normal use.)

## Step 3 — Make a "robot account" (service account)

1. Left menu → **APIs & Services** → **Credentials**.
2. Click **Create Credentials** → **Service account**.
3. Give it a name (e.g. "sheets-bot"), click **Create and Continue**, then **Done**.
4. You'll see it listed under "Service Accounts". Click it.
5. Copy its **email address** — it looks like `sheets-bot@your-project.iam.gserviceaccount.com`.
   You'll need it in Step 5.

## Step 4 — Download the robot's key file

1. On the service account page, open the **Keys** tab.
2. **Add Key** → **Create new key** → choose **JSON** → **Create**.
3. A `.json` file downloads. **This is a password. Keep it private. Never email it or commit it
   to a public place.**

## Step 5 — Share your spreadsheet with the robot

1. Open the Google Sheet you want the assistant to use.
2. Click **Share** (top right).
3. Paste the robot's email from Step 3 and give it **Editor** access. Send.

Repeat for every sheet you want it to touch. If it isn't shared, the robot can't see it.

## Step 6 — Turn the key file into one line of text

The server reads the key as a single base64 string (one long line), not a file.

- **Mac/Linux:** open a terminal, run:
  ```bash
  base64 -w0 path/to/your-key.json
  ```
  (On Mac, drop `-w0`.) Copy the long line it prints.
- **Windows (PowerShell):**
  ```powershell
  [Convert]::ToBase64String([IO.File]::ReadAllBytes("path\to\your-key.json"))
  ```

## Step 7 — Fill in the settings file

1. In this project folder, copy `.env.example` to a new file named `.env`.
2. Open `.env`. Paste the long line from Step 6 after `CREDENTIALS_CONFIG=`.
3. Set `GOOGLE_PROJECT_ID=` to your project id (visible in the Google console URL/dropdown).
4. Save. **Never share this `.env` file.**

## Step 8 — Start it

You need [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.
In a terminal, inside this project folder:

```bash
docker build --no-cache -t mcp-google-sheets-enhanced:latest .
docker compose up -d --force-recreate
```

Wait about a minute, then check it's alive:

```bash
curl -s localhost:8001/health
```

You want to see `{"status":"healthy"}`.

## Step 9 — Connect your assistant

Point your MCP client at `http://localhost:8000/sse`. For Claude Code, add to `.mcp.json`:

```json
{ "mcpServers": { "google-sheets": { "type": "sse", "url": "http://localhost:8000/sse" } } }
```

Done. Ask the assistant to read or edit one of your shared sheets.

---

## If something goes wrong

- **`{"status":"healthy"}` but the assistant can't read sheets** — almost always one of: the key
  wasn't pasted fully into `.env`, or the sheet wasn't shared with the robot's email. Health being
  green does NOT prove the login works (see the [technical notes](./CONDITIONAL_FORMATTING_FIX.md)).
- **"Could not find session"** — restart happened; reconnect the assistant (in Claude Code, run
  `/mcp`).
- **Build seems to use old code** — you must include `--no-cache` in the build command.

## Turning it off / revoking access

- Stop the server: `docker compose down`.
- Cut off access entirely: in Google Cloud → Credentials, delete the service account's key (or the
  account). The robot instantly loses access to every sheet.
