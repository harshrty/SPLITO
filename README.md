# SPLITO — Shared Expenses App

A shared-expenses tracker for a flat with **changing membership** and **mixed currencies**,
built to import a deliberately messy spreadsheet *safely* — detecting, surfacing, and
resolving every data anomaly through a human approval gate rather than silently guessing.

> Spreetail full-stack engineering assignment. Engineer of record: **@harshrty**.

## Status

🚧 In active development (design-first). See the design docs below.

## Documentation

| Doc | What's in it |
|---|---|
| [REQUIREMENTS.md](REQUIREMENTS.md) | Requirement analysis, persona traceability, scope |
| [DECISIONS.md](DECISIONS.md) | Decision log (D1–D9) + live-session interview defense |
| SCOPE.md | *(coming)* Database schema + anomaly log |
| AI_USAGE.md | *(coming)* AI tools used + caught mistakes |

## Personas & core goals

- **Aisha** — simplified "who pays whom" net settlement
- **Rohan** — itemized, no-magic-numbers audit of his balance
- **Priya** — correct multi-currency handling (INR + USD)
- **Sam** — temporal membership (joined mid-April → no March expenses)
- **Meera** — approval gate on any duplicate/deletion/change

## Tech stack

- **Backend:** Python (Django REST *or* FastAPI — see DECISIONS.md D6)
- **Frontend:** React + Zustand + TanStack Query
- **Database:** PostgreSQL (relational only)

## Local setup

_Setup instructions will be added as the backend and frontend are scaffolded._

## The data import (core feature)

The importer ingests `expenses_export.csv` **as provided** (no manual pre-editing) and, for each
of the deliberate data problems, **detects → surfaces → quarantines → resolves on human approval**.
It produces an **Import Report** listing every anomaly and the action taken.
