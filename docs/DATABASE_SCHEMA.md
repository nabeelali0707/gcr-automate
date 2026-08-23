# Database Schema

Postgres (Supabase-compatible). All timestamps UTC.

## `oauth_tokens`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK -> users | |
| provider | text | `google` |
| access_token_enc | bytea | Fernet-encrypted |
| refresh_token_enc | bytea | Fernet-encrypted |
| expires_at | timestamptz | |

## `courses`
| Column | Type | Notes |
|---|---|---|
| id | text PK | Classroom course id |
| user_id | uuid FK | |
| name | text | |
| section | text | |

## `assignments`
| Column | Type | Notes |
|---|---|---|
| id | text PK | Classroom coursework id (idempotency key) |
| course_id | text FK -> courses | |
| title | text | |
| due_at | timestamptz | converted to UTC |
| submission_state | text | mirrors Classroom's state enum |
| status | text | `pending`, `digested`, `scaffolded`, `awaiting_files`, `ready_to_submit`, `submitted`, `skipped`, `failed` |
| created_at | timestamptz | |
| updated_at | timestamptz | |

## `agent_runs`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | referenced in Telegram callback_data |
| assignment_id | text FK -> assignments | |
| state | text | LangGraph node name at last checkpoint |
| attempt | int | retry counter |
| error | text nullable | |
| started_at | timestamptz | |
| finished_at | timestamptz nullable | |

## `generated_files`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| assignment_id | text FK -> assignments | |
| kind | text | `digest`, `scaffold`, or `user_submission` |
| filename | text | |
| storage_path | text | local/object storage path |
| created_at | timestamptz | |

`kind` is the enforcement point noted in `docs/ARCHITECTURE.md`: only rows
with `kind='user_submission'` are eligible to be attached by
`submit_assignment()`.

## `approval_requests`
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| agent_run_id | uuid FK -> agent_runs | |
| type | text | `digest_ready`, `ready_to_submit` |
| telegram_message_id | text | |
| responded | boolean default false | |
| response | text nullable | `submit`, `ignore`, `cancel` |
| created_at | timestamptz | |

## Indexes
- `assignments (due_at)` — polling range queries
- `assignments (id)` unique — idempotency
- `agent_runs (assignment_id, started_at desc)` — latest run lookup
- `generated_files (assignment_id, kind)` — submit-eligibility check
