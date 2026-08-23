# Classroom Deadline Assistant

A human-in-the-loop tool that watches Google Classroom for assignments you're
about to miss, pings you on Telegram, hands you a fast digest of what's being
asked plus a starter scaffold, and — once **you've** done the actual work —
automates the tedious upload/attach/turn-in mechanics with a one-tap submit.

## What this project deliberately does NOT do

This is not an auto-solve-and-submit bot. It will never:

- Generate a final solution to an assignment on your behalf
- Write code, essays, or answers that get submitted as your work
- Submit anything without you having produced the actual content yourself

The "approval" step in the submit flow is for confirming *your* files are
correct and ready — not for rubber-stamping AI-generated work as your own.
That distinction is the whole design boundary of this project; every doc
in `/docs` is written around it.

## What it does do

1. **Deadline radar** — polls Classroom every 10–15 min, flags assignments
   due soon that aren't yet turned in, and notifies you on Telegram
   immediately (so "I forgot" stops being a problem).
2. **Requirement digest** — downloads the assignment's attachments and
   produces a clean, fast summary of what's actually being asked, so you're
   not parsing a dense PDF at 11pm.
3. **Scaffolding** — generates a starter template, relevant concept
   pointers, and a checklist to help you get moving quickly. It stops well
   short of a finished answer.
4. **Manual one-tap submit** — once you've written your own solution and
   uploaded it to the app, a Telegram button handles Drive upload +
   Classroom attach + turn-in, removing the tedious API mechanics.

## Docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system design, components, data flow
- [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md) — phased MVP plan
- [`docs/API_INTEGRATIONS.md`](docs/API_INTEGRATIONS.md) — Classroom, Drive, Telegram integration details
- [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) — tables and relationships
- [`docs/AGENT_WORKFLOW.md`](docs/AGENT_WORKFLOW.md) — LangGraph state machine design
- [`CLAUDE.md`](CLAUDE.md) — instructions for Claude Code when working in this repo
