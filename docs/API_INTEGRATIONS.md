# API Integrations

## Google Classroom

**OAuth scopes**
- `https://www.googleapis.com/auth/classroom.courses.readonly`
- `https://www.googleapis.com/auth/classroom.coursework.students`
- `https://www.googleapis.com/auth/drive.file`

**Flow:** standard OAuth 2.0 consent → exchange code for tokens → store
encrypted (Fernet or KMS-backed) → refresh silently on expiry.

**Key calls**
| Purpose | Endpoint |
|---|---|
| List courses | `courses.list` |
| List coursework | `courses.courseWork.list` |
| Get coursework detail | `courses.courseWork.get` |
| Check submission status | `courses.courseWork.studentSubmissions.list` |
| Download attachment | via Drive API `files.get` (alt=media) using the Drive file ID referenced in the coursework material |
| Attach files to submission | `courses.courseWork.studentSubmissions.modifyAttachments` |
| Turn in | `courses.courseWork.studentSubmissions.turnIn` |

**Submission sequence** (only reachable once user-authored files exist —
see `docs/BUILD_PLAN.md` Phase 7):
1. Upload file(s) to Drive (`drive.file` scope — app-created files only)
2. `modifyAttachments` with the new Drive file ID(s)
3. `turnIn`

**Timezone handling:** convert `dueDate`/`dueTime` (UTC) to the user's
stored local timezone before comparing against the polling threshold.

**Polling, not webhooks:** Classroom doesn't offer push notifications for
this use case, so APScheduler drives a fixed-interval poll (10–15 min).

## Google Drive
- Scope kept to `drive.file` (app can only see/manage files it creates or
  the user explicitly opens with it) — not full Drive access.
- Used for: downloading assignment attachments (via file ID from
  Classroom material), uploading the user's finished files at submit time.

## Telegram Bot API

**Commands**
- `/start` — link Telegram chat ID to the user's account
- `/status` — list currently tracked urgent assignments and their state
- `/run_now` — manually trigger a poll cycle

**Notification message (digest ready)**
- Assignment name, course, due time
- Inline buttons: `View Digest`, `Get Scaffold`, `Ignore`

**Notification message (ready to submit)**
- Shown only once `kind=user_submission` files exist for the assignment
- Inline buttons: `Submit`, `View Files`, `Cancel`

Callback data includes `agent_run_id` so callbacks map back to the right
assignment/run row.

**Deadline warnings:** if no interaction within a configurable window
before the due date, send an escalating reminder.
