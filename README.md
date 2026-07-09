# SPLITO — Shared Expenses App

A shared-expenses tracker for a flat with **changing membership** and **mixed currencies**,
built to import a deliberately messy spreadsheet *safely* — detecting, surfacing, and resolving
every data anomaly through a **human approval gate** rather than silently guessing.

> Spreetail full-stack engineering assignment. Engineer of record: **@harshrty**.
> AI collaborator: **Claude (Anthropic)** — see [AI_USAGE.md](AI_USAGE.md).

**Live app:** _add your deployed URL here after deploying (see Deployment)._

## Personas → what the app does

- **Aisha** — simplified "who pays whom" net settlement (greedy min-cash-flow)
- **Rohan** — itemized, no-magic-numbers audit of every rupee he owes
- **Priya** — correct INR + USD handling (date-effective rates, snapshotted)
- **Sam** — temporal membership: joined mid-April → March expenses don't touch him
- **Meera** — approval gate on every duplicate / deletion / change during import

## Tech stack

- **Backend:** Python 3.13, Django 5.1 + Django REST Framework, SimpleJWT
- **Frontend:** React (Vite) + Zustand (session) + TanStack Query (server state)
- **Database:** PostgreSQL 16 (relational only)

## Architecture & design docs

| Doc | What's in it |
|---|---|
| [REQUIREMENTS.md](REQUIREMENTS.md) | Requirement analysis, persona traceability, scope |
| [DECISIONS.md](DECISIONS.md) | Decision log (D1–D9) + live-session interview defense |
| [SCOPE.md](SCOPE.md) | Database schema (DDL) + the 17-anomaly log |
| [HLD.md](HLD.md) | High-level component architecture |
| [docs/import_report.md](docs/import_report.md) | **Generated** import report over the real CSV |
| [AI_USAGE.md](AI_USAGE.md) | AI tools used + 3 concrete mistakes caught |

## Local setup

### Backend
```bash
cd backend
docker compose up -d db                 # Postgres 16 on :5433
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                     # defaults point at the docker db
python manage.py migrate
python manage.py seed_fx                 # documented USD->INR rate
python manage.py createsuperuser         # optional, for /admin
python manage.py runserver               # http://localhost:8000
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env                     # VITE_API_URL=http://localhost:8000/api
npm run dev                              # http://localhost:5173
```

## Running the tests
```bash
cd backend && python manage.py test      # 45 tests: split math, balances, auth, APIs, import
```

## The data import (core feature)

The importer ingests `expenses_export` **exactly as provided** (xlsx or csv, no hand-editing) and
for each deliberate data problem: **detects → surfaces → quarantines → resolves on human approval**.
Nothing reaches the ledger until blocking anomalies are approved.

Regenerate the import report any time:
```bash
cd backend && python manage.py generate_import_report   # writes docs/import_report.md
```

Pipeline: `parse → staged_row → detectors → anomaly → review/approve → gated commit → ledger`.
16 isolated detectors; the Import Report is a query over the `anomaly` table.

## Deployment

`render.yaml` is a Render blueprint (backend web service + Postgres + static frontend). After the
first deploy, set `CORS_ALLOWED_ORIGINS`/`CSRF_TRUSTED_ORIGINS` (backend) and `VITE_API_URL`
(frontend) to the deployed URLs. The `release`/build step runs migrations and `seed_fx`.

## AI usage

Claude was the primary development collaborator; every line was reviewed by the engineer of
record. Three concrete cases where the AI was wrong and was caught are documented in
[AI_USAGE.md](AI_USAGE.md).
