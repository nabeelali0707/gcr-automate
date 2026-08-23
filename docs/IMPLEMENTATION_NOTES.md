# Implementation Notes

This repo now has the first backend slice:

- FastAPI app skeleton with health, upload, and submit endpoints
- In-memory repository for local development and tests
- Deadline monitor that polls Classroom-shaped data and flags urgent unsubmitted work
- Requirement digest and scaffold generation that produces support material only
- Submission service guard that rejects digest/scaffold files and only accepts `kind=user_submission`
- Token encryption helper, Telegram message builder, Classroom client wrapper, and Postgres schema

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
python -m pytest
```

Copy `.env.example` to `.env` and fill in credentials before using live Google or Telegram integrations.

To initialize Postgres manually:

```bash
psql "$DATABASE_URL" -f scripts/schema.sql
```
