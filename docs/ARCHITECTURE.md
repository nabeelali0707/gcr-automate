# Architecture

## Goal

Never miss a Classroom deadline again, get a fast on-ramp into what an
assignment requires, and remove the tedious parts of submitting — without
the system ever producing the graded work itself.

## High-level flow

```
Scheduler (every 10-15 min, APScheduler)
        |
        v
Fetch assignments due soon & not yet turned in  (Classroom API)
        |
        v
For each urgent assignment:
        |
        +--> Download attachments (Drive API)
        |
        +--> Extract text (PyMuPDF/pdfplumber, OCR fallback)
        |
        +--> Digest requirements (LLM: structured JSON summary)
        |
        +--> Generate scaffold (starter template, checklist, concept notes)
        |
        +--> Store digest + scaffold + metadata (Postgres)
        |
        +--> Telegram notification: "Assignment X due in 6h — digest + scaffold ready"
        |
        v
User writes their own solution (outside the system, or uploaded back into it)
        |
        v
User taps "Submit" in Telegram (only enabled once files are attached)
        |
        v
Upload user's files to Drive -> attach to Classroom submission -> turnIn
        |
        v
Mark as submitted in DB
```

## Components

| Component | Responsibility |
|---|---|
| **Scheduler** | Polls Classroom on a fixed interval; enqueues urgent assignments |
| **Classroom Integration** | OAuth, list courses/assignments, check submission status, download attachments, attach files, turn in |
| **Extraction** | Converts PDFs/docs/images into plain text; OCR fallback |
| **Digest Agent (LangGraph)** | Turns extracted text into a structured requirements summary and a scaffold (template/outline/checklist) — explicitly stops short of a final answer |
| **Sandbox** | Docker container, no network, resource-limited; runs **user-submitted** code so they can self-check before submitting — not used to execute AI-generated solutions |
| **Telegram Bot** | Notifications, `/status`, `/run_now`, digest delivery, submit button |
| **Submission Service** | Drive upload + Classroom attach + turnIn, gated on the user having supplied files |
| **Database** | Tracks courses, assignments, digests, scaffolds, submissions, OAuth tokens |

## Why the scaffold stops where it does

The digest agent produces:
- A plain-language restatement of the requirements
- Expected output files/format
- A starter file skeleton (function signatures, section headers, boilerplate)
- A checklist of sub-tasks
- Pointers to relevant concepts

It does **not** produce a working final implementation, a filled-in essay,
or complete answers to graded questions. This is enforced structurally: the
scaffold generation prompt is instructed to produce structure and hints
only, and the submission service has no code path that can attach
scaffold-only output to a Classroom submission — only files the user has
explicitly uploaded/edited after scaffold generation are eligible for
`submit_assignment()`.

## Security

- OAuth tokens encrypted at rest (Fernet), never logged.
- Docker sandbox: `--network none`, CPU/memory/time limits, read-only root fs.
- Least-privilege scopes: `classroom.courses.readonly`,
  `classroom.coursework.students`, `drive.file` (not full Drive access).
