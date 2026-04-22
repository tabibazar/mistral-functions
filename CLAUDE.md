# CLAUDE.md

Guidance for Claude Code (and other AI assistants) working in this repository.

## What this project is

A small Flask web app that pairs the **Mistral AI chat API** with **AWS Cost Explorer** via Mistral's function-calling (tools) feature. The user chats with Mistral in the browser; when the model asks to call one of the exposed AWS cost functions, the backend runs it against Cost Explorer and feeds the result back to Mistral for a natural-language summary.

There is no database, no test suite, no build step, and no package layout — everything runs from a single `app.py` against a YAML config file.

## Repository layout

```
.
├── app.py                 # Entire Flask backend (~660 lines): config load, AWS helpers, /api/chat tool loop
├── example.config.yml     # Template for config.yml (gitignored, holds secrets)
├── requirements.txt       # Pinned runtime deps (Flask, boto3, requests, mistralai, PyYAML, ...)
├── templates/index.html   # Single-page chat UI (server-rendered by Flask)
├── static/
│   ├── css/style.css      # UI styling
│   └── js/app.js          # Chat client: form handling, localStorage sessions, markdown rendering
├── README.md              # User-facing setup and usage docs
└── .gitignore             # Notably ignores config.yml (never commit credentials)
```

## How the app works (end-to-end)

1. `app.py` loads `config.yml` at import time. Missing file = import error — the app refuses to start without config.
2. Boot creates a module-level `boto3.Session` and a `ce_client` for Cost Explorer.
3. `GET /` renders `templates/index.html`.
4. The browser (`static/js/app.js`) keeps chat history in `localStorage` and POSTs the running message list to `/api/chat`.
5. `/api/chat` sends the messages plus three tool definitions to Mistral (`MISTRAL_API_URL` from config, `tool_choice: "auto"`).
6. If Mistral responds with `tool_calls`, the backend dispatches to the matching Python function, appends the `{role: "tool", ...}` result, and re-requests Mistral for a natural-language reply.
7. The final assistant message is returned as JSON to the frontend, which renders it with `marked` (markdown).

### Exposed AWS tools

All three live in `app.py` and are wired into the `tools` array inside `chat()`:

| Function | Purpose | AWS call |
|---|---|---|
| `get_aws_cost_summary(start_date, end_date, granularity)` | Total + per-service spend over a date range | `ce.get_cost_and_usage` grouped by `SERVICE` |
| `get_aws_cost_forecast(days, granularity)` | Projected future spend | `ce.get_cost_forecast` |
| `get_aws_service_costs(service_name, start_date, end_date, granularity)` | Drill-down by `USAGE_TYPE` for one service | `ce.get_cost_and_usage` filtered + grouped by `USAGE_TYPE` |

When adding a new tool, both pieces must be updated together:
1. Implement a Python function that returns a JSON-serializable dict (on error, return `{"error": ..., "help": ...}` — do not raise).
2. Append a matching `{"type": "function", "function": {...}}` entry to the `tools` list in `chat()`.
3. Add an `elif function_name == "..."` branch in the tool-dispatch loop (around `chat()` line ~559).

## Development workflow

### Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp example.config.yml config.yml   # then fill in real credentials
python app.py                      # serves on http://127.0.0.1:5000/ with debug=True
```

`config.yml` is in `.gitignore` — never commit it, and never paste real keys into `example.config.yml`.

### Running

`python app.py` runs Flask's dev server with `debug=True` (auto-reload, verbose errors). There is no production entry point (no gunicorn config, no Dockerfile) — if one is added, remember to disable debug mode and stop reading `config.yml` from the process CWD.

### Testing changes

There is **no automated test suite**. When verifying changes:
- Hit `GET /api/test-aws` — sanity checks that STS + Cost Explorer credentials work.
- Exercise `/api/chat` via the UI with a real prompt (e.g. *"What did I spend on AWS in the last 7 days?"*) and watch the stdout log for the tool-call and follow-up round trip.
- For pure AWS-function changes, you can import and call the helpers directly from a Python REPL with `config.yml` present.

If you add or change behavior, state in the PR description exactly how you verified it — do not claim "tested" without running the flow.

## Conventions and gotchas

- **Credentials**: All secrets come from `config.yml`. Do not read from environment variables, `~/.aws/credentials`, or hardcoded strings. Do not introduce `dotenv`.
- **Client inconsistency**: `get_aws_cost_forecast`, `get_aws_service_costs`, and `test_aws` all use the module-level `ce_client`, but `get_aws_cost_summary` constructs a fresh `boto3.client('ce', ...)` on every call (`app.py:72`). If you touch that function, either keep the local construction or unify on the module-level client consistently — don't mix half-way.
- **Logging**: Use the module-level `logger` (configured to stdout at INFO). A few raw `print(...)` blocks dump full AWS responses for debugging (`app.py:136`, `app.py:312`) — leave them unless explicitly asked to remove, but do not add more.
- **Error handling in chat()**: Almost every error path returns HTTP 200 with an assistant-shaped message. That is intentional — the frontend only knows how to render `{"message": {...}}`. Preserve this contract for user-visible failures; only return non-200 for genuinely malformed requests (empty body, no messages).
- **Tool result format**: Must be JSON-stringified into `content` of a `{"role": "tool", "tool_call_id": ..., "name": ...}` message. Mistral rejects non-string `content`.
- **Frontend state**: Chat history lives only in the browser's `localStorage` (`awsCostChatSessions`, capped at 10 sessions). The server is stateless — every POST must include the full message history.
- **No build step for frontend**: `static/js/app.js` is plain ES, loaded directly. `marked` is pulled from a CDN. Don't introduce bundlers/frameworks unless the user asks.
- **Cost Explorer is not free**: Each `get_cost_and_usage` / `get_cost_forecast` call is a paid API request (~$0.01 per request at time of writing). Avoid loops or retries that could fan out during development.

## What not to do without being asked

- Don't add a test framework, linter config, pre-commit hooks, Dockerfile, or CI config.
- Don't swap Flask for FastAPI, or `requests` for the `mistralai` SDK, even though `mistralai` is already in `requirements.txt` — the current code uses raw `requests`.
- Don't move config into environment variables or rewrite the credentials loader.
- Don't refactor `app.py` into packages/modules unless the task specifically calls for it; keeping it flat is the existing convention.
- Don't commit `config.yml` or any file containing real API keys or AWS credentials. If you see one staged, stop and warn.

## Git workflow

- Default development branch for Claude-authored work in this session: `claude/add-claude-documentation-gXzPn`.
- Create new commits rather than amending; use descriptive messages (see `git log` for the existing terse style).
- Do not open pull requests unless explicitly asked.
