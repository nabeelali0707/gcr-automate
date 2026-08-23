# Agent Workflow (LangGraph)

## State schema

```python
class AssignmentState(TypedDict):
    assignment_id: str
    course_id: str
    due_at: datetime
    attachments: list[str]          # Drive file IDs
    extracted_text: str | None
    digest: dict | None             # structured requirements summary
    scaffold: dict | None           # starter files/checklist, NOT a solution
    user_files: list[str] | None    # storage paths of user-uploaded work
    attempt: int
    error: str | None
```

## Nodes

| Node | Purpose |
|---|---|
| `FETCH` | Pull assignment + submission status from Classroom |
| `CHECK_DEADLINE` | Filter to "due soon & not submitted"; route to `SKIP` otherwise |
| `DOWNLOAD` | Fetch attachments via Drive |
| `EXTRACT` | Text extraction (PyMuPDF/pdfplumber, OCR fallback) |
| `DIGEST` | LLM: structured requirements summary (no answers) |
| `SCAFFOLD` | LLM: starter template + checklist + concept notes (no full solution) |
| `NOTIFY_DIGEST` | Telegram message with digest + scaffold |
| `AWAIT_USER_FILES` | Wait for user to upload their own completed work |
| `SANDBOX_CHECK` | Run user's code in Docker sandbox, report pass/fail back to user |
| `NOTIFY_READY` | Telegram "ready to submit" message, gated on `user_files` present |
| `SUBMIT` | Drive upload + Classroom attach + turnIn (only reachable with `user_files`) |
| `SKIP` | Not urgent / already submitted |
| `FAIL` | Extraction/digest error after retries; notify user for manual action |

## Edges (simplified)

```
FETCH -> CHECK_DEADLINE -> {DOWNLOAD, SKIP}
DOWNLOAD -> EXTRACT -> DIGEST -> SCAFFOLD -> NOTIFY_DIGEST -> AWAIT_USER_FILES
AWAIT_USER_FILES -> {SANDBOX_CHECK, FAIL(timeout)}
SANDBOX_CHECK -> NOTIFY_READY -> SUBMIT
any node -> FAIL (on unrecoverable error, max 3 retries on transient ones)
```

## Key invariant

`SUBMIT` is only reachable through `AWAIT_USER_FILES` →
`SANDBOX_CHECK` → `NOTIFY_READY`. There is no edge from `SCAFFOLD` or
`NOTIFY_DIGEST` directly to `SUBMIT`. This mirrors the DB-level
enforcement (`generated_files.kind='user_submission'` required) so the
boundary is enforced at both the graph level and the data level.

## Tools available to the agent

`get_courses`, `get_assignments`, `get_assignment_details`,
`get_submission_status`, `download_attachment`, `extract_text`, `ocr_pdf`,
`generate_digest`, `generate_scaffold`, `notify_telegram`,
`run_user_code_in_sandbox`, `submit_assignment`, `mark_skipped`.

`submit_assignment` is implemented to raise if called with anything other
than `kind='user_submission'` files — this is a runtime guard, not just a
graph-structure convention.

## Idempotency & retries

- Keyed on `assignment_id`; a run already in `submitted`/`skipped` state
  is not reprocessed.
- Transient failures (network, rate limit) retried up to 3x with backoff.
- Extraction/digest failures beyond retry limit route to `FAIL`, which
  notifies the user to review manually — the system does not attempt to
  guess or force a digest through.

## Manual trigger

`/run_now` in Telegram triggers an out-of-cycle poll for the requesting
user's assignments.
