# Implementation Notes

## What's Built (Current State)

### Phase 1 — Classroom OAuth + read access ✅
- `app/integrations/oauth.py` — `GoogleOAuthFlow` (authorization_url + exchange_code),
  `TokenCipher` (Fernet encrypt/decrypt), `build_credentials()` with auto-refresh,
  `build_classroom_service()` / `build_drive_service()` helpers
- `GET /oauth/google` — redirects user to Google consent screen
- `GET /oauth/google/callback` — exchanges code, stores encrypted tokens in Supabase DB
- `app/db/sql_repository.py` — `OAuthTokenRepository` (store + load with cipher)

### Phase 2 — Deadline monitoring ✅
- `app/services/monitor.py` — `DeadlineMonitor.poll_once()` polls Classroom, upserts
  courses + assignments, detects urgent (due within threshold), triggers digest pipeline
  and sends Telegram notification automatically

### Phase 3 — File extraction + requirement digest ✅
- `app/extraction/text.py` — real PDF (pdfplumber), DOCX (python-docx), plain text,
  CSV/MD, and raw fallback; optional Tesseract OCR for image-only PDF pages
- `app/services/llm.py` — AI requirement digest extractor (supporting Gemini and OpenAI
  via HTTPX with structured JSON mode), falling back to rule-based keyword/regex extraction
  in `app/agent/digest.py` when API keys are not configured.

### Phase 4 — Scaffold generation ✅
- `app/scaffolding/generator.py` — deterministic scaffold from digest; includes
  `SCAFFOLD_BOUNDARY` comment in every output file preventing solution generation

### Phase 5 — Telegram bot ✅
- `app/integrations/telegram.py` — `TelegramBotClient.send_message()`, message builders
  for digest-ready and ready-to-submit with inline buttons
- `POST /telegram/webhook` — handles `/start`, `/status`, `/run_now` commands and
  `digest:`, `scaffold:`, `ignore:`, `submit:`, `cancel:` callback queries
- `app/config.py` — `TELEGRAM_CHAT_ID` setting for outbound notifications

### Phase 6 — User file intake + sandbox ✅
- `POST /assignments/{id}/user-files` — chunked upload, sanitized filename,
  stored as `kind=user_submission`, marks assignment `READY_TO_SUBMIT`
- `app/sandbox/runner.py` — Docker sandbox: network-disabled, 128 MB RAM, 50% CPU,
  15-second timeout, Python 3.11-slim image; graceful fallback when Docker unavailable

### Phase 7 — Submission flow ✅
- `app/integrations/drive.py` — `GoogleDriveClient` with real `download_attachment()`
  (including Google Workspace export: Docs→DOCX, Sheets→CSV) and `upload_file()`
- `app/integrations/classroom.py` — `SubmissionService` enforces boundary: only
  `kind=user_submission` files can pass through `turnIn`
- `POST /assignments/{id}/submit` — full end-to-end: Drive upload → attach → turn-in

### Database — Supabase ✅
- Project: **gcrAuto** (`yfzvrqpztppwebzavlch`, ap-southeast-1, ACTIVE_HEALTHY)
- All 6 tables live: `oauth_tokens`, `courses`, `assignments`, `agent_runs`,
  `generated_files`, `approval_requests` + 3 indexes
- `app/db/orm.py` — SQLAlchemy 2.0 ORM (`Mapped[]` + `mapped_column` style)
- `app/db/session.py` — engine, `SessionLocal`, `init_db()`, `get_db()` dependency
- `app/db/sql_repository.py` — `SqlRepository` + `OAuthTokenRepository`

### LangGraph pipeline ✅
- `app/agent/workflow.py` — full `StateGraph` with 11 nodes matching `AGENT_WORKFLOW.md`:
  `CHECK_DEADLINE → DOWNLOAD → EXTRACT → DIGEST → SCAFFOLD → NOTIFY_DIGEST →
  AWAIT_USER_FILES → SANDBOX_CHECK → NOTIFY_READY → SUBMIT` (+ `SKIP`, `FAIL`)
- Compiled lazily via `get_graph()` singleton
- All routing helpers preserved for backward compatibility

### Additional routes ✅
- `GET  /assignments` — list all open assignments
- `GET  /assignments/{id}` — detail + files
- `GET  /assignments/{id}/status` — digest/scaffold/user-file counts
- `POST /assignments/{id}/run-now` — manually trigger digest pipeline
- `GET  /status` — dashboard summary by status

### FastAPI lifespan ✅
- `app/main.py` — `asynccontextmanager` lifespan: DB `init_db()` on startup,
  APScheduler auto-started when `GOOGLE_CLIENT_ID` + `TELEGRAM_BOT_TOKEN` are set

### Tests — 34 passing ✅
| Test file | Coverage |
|---|---|
| `test_api_routes.py` | Upload + submit endpoints |
| `test_demo.py` | Full demo poll + digest flow |
| `test_digest_runner.py` | Runner stores digest + scaffold |
| `test_extraction.py` | txt, md, pdf, docx, unknown fallback |
| `test_monitor.py` | Urgent detection, skip, due-date parsing |
| `test_oauth.py` | Fernet round-trip |
| `test_sandbox.py` | Missing file, wrong type, Docker fallback |
| `test_submission_boundary.py` | Rejects scaffold files, accepts user_submission |
| `test_workflow_graph.py` | Routing helpers, node units, graph compile |
| `test_workflow_routes.py` | Route helper edge cases |

---

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
python -m pytest
```

Copy `.env.example` to `.env` and fill in:

| Variable | How to get it |
|---|---|
| `DATABASE_URL` | Pre-filled for Supabase gcrAuto — just add your DB password |
| `FERNET_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google Cloud Console → APIs & Services → Credentials |
| `TELEGRAM_BOT_TOKEN` | Talk to @BotFather on Telegram |
| `TELEGRAM_CHAT_ID` | Send `/start` to @userinfobot |

## Run locally (no Google/Telegram needed)

```bash
python scripts/run_local_demo.py
```

## Run the server

```bash
uvicorn app.main:app --reload
# Then visit http://localhost:8000/docs for the interactive API
```

## Start OAuth flow

Navigate to `http://localhost:8000/oauth/google` — you'll be redirected to Google,
then back to `/oauth/google/callback` which stores encrypted tokens in Supabase.

## Remaining work (Phase 8 — Polish)

- [x] LLM-backed digest (supporting Gemini and OpenAI APIs, falling back to local rule-based extractor)
- [x] Parallel processing across multiple urgent assignments (concurrent execution via ThreadPoolExecutor)
- [ ] Row Level Security policies on Supabase tables
- [ ] Multi-user support (currently single-user UUID `00000000-0000-0000-0000-000000000001`)
- [ ] Retry logic with exponential backoff for Classroom/Drive API calls
- [ ] Telegram `/status` deep-link into individual assignment pages
