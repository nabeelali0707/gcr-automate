# MVP Build Plan

## Phase 1 — Classroom OAuth + read access
- Google Cloud project, OAuth consent screen, credentials
- Scopes: `classroom.courses.readonly`, `classroom.coursework.students`, `drive.file`
- `integrations/classroom.py`: `list_courses()`, `list_coursework()`, `get_submission_status()`
- Store encrypted tokens in `oauth_tokens` table
- CLI smoke test: print your courses and upcoming assignments

## Phase 2 — Deadline monitoring
- APScheduler job, every 10–15 min
- Query: coursework with `dueDate` within threshold (e.g. 24h) and
  submission state != `TURNED_IN`/`RETURNED`
- Persist to `assignments` table with idempotency on `assignment_id`

## Phase 3 — File extraction + requirement digest
- Download attachments via Drive API
- PyMuPDF/pdfplumber text extraction; Tesseract OCR fallback for images/scans
- LLM call producing structured JSON: questions, expected output files,
  constraints, deadline — **summary only, no answers**

## Phase 4 — Scaffold generation
- Given the digest, generate: starter file skeleton, checklist, concept
  notes/pointers
- Explicit prompt constraints preventing full solution generation
  (see `docs/ARCHITECTURE.md#why-the-scaffold-stops-where-it-does`)
- Store scaffold + digest in `generated_files` (marked `kind=scaffold`)

## Phase 5 — Telegram bot
- `/start`, `/status`, `/run_now`
- Digest + scaffold delivery message with inline buttons: **View Digest**,
  **Get Scaffold**, **Ignore**
- Reminder if no response before deadline

## Phase 6 — User file intake + sandbox self-check
- Endpoint/bot flow for the user to upload their own completed files
- Docker sandbox (no network, resource limits) to run/test the
  **user's** code and report pass/fail before submission
- Files marked `kind=user_submission` once uploaded — only this kind is
  eligible for the submit flow

## Phase 7 — Submission flow
- Telegram **Submit** button enabled only when `kind=user_submission`
  files exist for the assignment
- `submit_assignment()`: upload to Drive → create/attach to student
  submission → `turnIn`
- Handle already-submitted / error / retry cases

## Phase 8 — Polish
- Parallel processing across assignments
- Model router fallback (if using multiple LLM providers)
- `/status` dashboard summary, logging, error notifications
