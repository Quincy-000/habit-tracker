# Habit Tracker — Flask + PostgreSQL (Docker Compose)

A small Flask habit-tracking app (web UI + CLI) with a real PostgreSQL backend, run entirely with Docker Compose. It started life as the vehicle for a production-style CI/CD pipeline on AWS (Chapter 1); it now lives as a local, zero-cost app whose data survives restarts (Chapter 2).

**Chapter 2 TL;DR:** the app originally stored logs in a JSON file at `~/.habits.json` — which was **ephemeral inside a container**, so every redeploy wiped every logged habit. The fix: replace the JSON file with Postgres, managed by Docker Compose with a named volume. Log a habit, restart the stack, it's still there.

---

## Chapter 2 — PostgreSQL backend (current)

### The problem

In the original Docker/ECS deployment, data lived in a JSON file inside the container's filesystem. Containers are disposable by design — on every redeploy the file (and every logged habit) vanished. The app needed storage that outlives the process.

### Quickstart

Requires Docker with the Compose v2 plugin.

```bash
docker compose up -d --build
# web app → http://localhost:5000
```

Postgres runs on `localhost:5432` (published for direct `psql` access and the host CLI). Connection settings default to `habits`/`habits` — copy `.env.example` to `.env` to override; nothing is hardcoded in the repo.

```bash
# CLI against the same database (host works because 5432 is published)
python tracker.py today
python tracker.py log "AWS Study"
python tracker.py streak "AWS Study"

# or poke the database directly
psql postgresql://habits:habits@localhost:5432/habits
```

### Schema

```sql
CREATE TABLE habits (
    id   SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE logs (
    id       SERIAL PRIMARY KEY,
    habit_id INTEGER NOT NULL REFERENCES habits(id),
    log_date DATE NOT NULL,
    UNIQUE (habit_id, log_date)
);
```

Applied via `schema.sql` (psql), seeded with the 6 habits via `seed.sql`.

### Compose layout

```
services:
  db:   postgres:16-alpine, named volume (habits_data), healthcheck via pg_isready
  web:  Flask app, waits for db using depends_on: condition: service_healthy
```

`web` starts only after `db` is genuinely ready (healthcheck), not merely started — otherwise the app connects before Postgres accepts connections.

### Deduplication moved into the database

Logging the same habit twice on one day is now handled by Postgres, not Python:

```sql
INSERT INTO logs (habit_id, log_date)
VALUES (%s, %s)
ON CONFLICT (habit_id, log_date) DO NOTHING
RETURNING id;
```

No row returned → already logged today. The `UNIQUE (habit_id, log_date)` constraint guarantees it at the database level — the app can't get it wrong even if the Python logic changes.

### The money checkpoint

```
log a habit → docker compose restart → habit still there ✅
```

Data survives because it lives in the named volume, not in the container's writable layer.

---

## Chapter 1 (archived) — Containerized CI/CD Pipeline on AWS

The app was originally the vehicle for learning a full, production-style CI/CD pipeline: automated testing, container vulnerability scanning, a manual approval gate, and zero-downtime deployment to AWS ECS Fargate behind a load balancer. **The app itself was intentionally simple. The pipeline was the point.** Infrastructure was torn down after screenshots to avoid ongoing cost; the code artifacts (`buildspec.yml`, `task-definition.json`, `pipeline.json`) are retained locally.

### Architecture (as built, July 2026)

```
GitHub push (main)
      │
      ▼
CodePipeline: Source
      │  (CodeConnections → GitHub)
      ▼
CodePipeline: Build  ──────────────────────────────┐
      │  (CodeBuild)                                │
      │  1. pytest -v            → 11 tests         │
      │  2. docker build         → image             │
      │  3. trivy image scan     → HIGH/CRITICAL gate │
      │  4. docker push          → Amazon ECR         │
      ▼                                              │
CodePipeline: Approval  ◄── human review, blocks until approved
      │
      ▼
CodePipeline: Deploy
      │  (ECS rolling deployment)
      ▼
ECS Fargate Service ── Application Load Balancer ── Public URL
      (habit-tracker-cluster / habit-tracker-service)
```

**Why a manual approval gate exists between build and deploy:** automated checks (tests, vulnerability scans) can confirm code is *safe*, but not that it's the *right moment* to ship. The approval stage is a deliberate, auditable human decision point — every deploy carries a record of who approved it and when, separate from what the automated gates already confirmed.

### What the pipeline enforced

| Stage | Tool | Gate |
|---|---|---|
| Test | `pytest` | 11 tests covering habit logging, dedup logic, streak calculation, Flask routes — build fails if any test fails |
| Build | Docker | Multi-stage build on `python:3.12-slim-bookworm`, OS packages patched via `apt-get upgrade` |
| Security scan | Trivy | Hard-fails on any **fixable** HIGH/CRITICAL CVE (`--ignore-unfixed`) |
| Approval | CodePipeline manual approval | Pipeline pauses for explicit human sign-off before any change reaches the running service |
| Deploy | ECS Fargate rolling | New task must pass ALB health checks before old task is retired — zero downtime |

### Engineering decisions worth keeping on record

- **Debian `bookworm` over `trixie` for the base image** — `python:3.12-slim` (which defaults to `trixie`) surfaced 20 CVEs, all OS-layer, all `affected`/`fix_deferred` — no patch existed upstream. `bookworm` + `--ignore-unfixed` keeps the security gate meaningful without blocking on CVEs nobody can patch yet.
- **Two separate security groups (ALB vs. task)** — the running container never accepts traffic directly from the internet, only from the load balancer.
- **Immutable image tagging** — every build tagged with `latest` + commit SHA, so any deployment traces back to its exact commit; rollback = redeploy a known-good tag.
- **IAM roles scoped per service** — CodeBuild, ECS execution, and CodePipeline each got only the permissions their actual data flow required (e.g. CodeBuild gained S3 artifact access only once CodePipeline started feeding it source from S3).

### Screenshots (July 2026 deployment)

 <img width="1349" height="714" alt="Screenshot 2026-07-12 224402" src="https://github.com/user-attachments/assets/3cc7ad1e-d204-463f-b0bc-8e1b29b09d29" />
 <img width="1365" height="526" alt="Screenshot 2026-07-12 224525 - Copy" src="https://github.com/user-attachments/assets/6ac1769b-cbde-4319-acda-18e45f2421cd" />
 <img width="908" height="593" alt="Screenshot 2026-07-12 155024" src="https://github.com/user-attachments/assets/162ecf42-8143-4b85-8171-063d777cd24c" />
 <img width="1361" height="507" alt="Screenshot 2026-07-12 224650 - Copy" src="https://github.com/user-attachments/assets/48492094-c4fc-4e88-a473-c0b3380accb0" />
 <img width="1365" height="435" alt="image" src="https://github.com/user-attachments/assets/a1bbed4d-2f60-4681-8826-7cbeb25f420f" />

---

## Tech stack

- **App:** Python, Flask, Jinja2 templates
- **Database:** PostgreSQL 16 (Docker Compose, named volume, healthcheck-gated startup)
- **DB access:** psycopg 3, raw SQL (no ORM — the point is learning SQL)
- **Containerization:** Docker Compose v2 (`python:3.12-slim-bookworm` base, OS-patched)
- **Chapter 1 stack (archived):** AWS CodePipeline/CodeBuild, ECR, ECS Fargate, ALB, Trivy

## Project structure

```
.
├── tracker.py              # Flask app + CLI, reads/writes Postgres
├── test_tracker.py         # pytest suite (being migrated to the DB layer)
├── templates/
│   └── index.html          # Web UI
├── Dockerfile
├── compose.yaml            # db + web services, named volume, healthcheck
├── schema.sql              # habits + logs tables
├── seed.sql                # the 6 default habits
├── requirements.txt
├── requirements-dev.txt
└── .env.example            # connection settings (copy to .env to override)
```

## Status

- ✅ Chapter 2 core: Postgres backend via Compose, dedupe in SQL, persistence across restarts
- 🔜 Streak + last-7-days views as SQL queries (currently plain Python over fetched rows)
- 🔜 Tests migrated to the DB layer
