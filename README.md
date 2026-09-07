# Habit Tracker — Flask + PostgreSQL (Docker Compose)

A small Flask habit-tracking app (web UI + CLI) with a real PostgreSQL backend, run entirely with Docker Compose. It started life as the vehicle for a production-style CI/CD pipeline on AWS (Chapter 1); it now lives as a local, zero-cost app whose data survives restarts (Chapter 2), whose streak and weekly-grid logic runs as SQL in Postgres, and whose test suite exercises the real database through a disposable `habits_test` copy (Chapter 3).

**Chapter 2 TL;DR:** the app originally stored logs in a JSON file at `~/.habits.json` — which was **ephemeral inside a container**, so every redeploy wiped every logged habit. The fix: replace the JSON file with Postgres, managed by Docker Compose with a named volume. Log a habit, restart the stack, it's still there.

---

## Chapter 2 — PostgreSQL backend

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

## Chapter 3 — Logic in SQL; tests against a real Postgres (current)

### The gap after Chapter 2

Two parts of the app still lagged the Postgres move. The streak counter and the last-7-days grid were computed in Python over rows fetched from the DB — logic the database should own. And the original 11-test suite still monkeypatched a JSON `DATA_FILE` that no longer existed; it was testing a storage layer the app had stopped using.

### Last-7-days grid — LEFT JOIN, filter inside the ON

A naive join drops habits with no logs that week. Putting the date window in the ON clause keeps every habit in the result; habits with no logs come back with NULL dates instead of disappearing:

```sql
SELECT habits.name, logs.log_date
FROM habits
LEFT JOIN logs
    ON habits.id = logs.habit_id
    AND logs.log_date >= CURRENT_DATE - INTERVAL '6 days'
ORDER BY habits.name, logs.log_date
```

### Streak — gaps-and-islands, with a grace day

"Current streak" means the most recent consecutive run of days — allowing today to be unlogged, since you may log it later tonight. Classic gaps-and-islands: number the rows, subtract the row number from each date (consecutive days land on the same key), group into islands, then take the latest island that ends today or yesterday:

```sql
WITH numbered AS (
    SELECT log_date,
           ROW_NUMBER() OVER (ORDER BY log_date) AS rn
    FROM logs
    WHERE habit_id = %s
),
islands AS (
    SELECT log_date,
           log_date - (rn * INTERVAL '1 day') AS island_key
    FROM numbered
),
grouped AS (
    SELECT MIN(log_date) AS island_start,
           MAX(log_date) AS island_end,
           COUNT(*)      AS island_length
    FROM islands
    GROUP BY island_key
)
SELECT COALESCE(
    (SELECT island_length FROM grouped
     WHERE island_end >= CURRENT_DATE - 1
     ORDER BY island_end DESC
     LIMIT 1),
    0
) AS current_streak;
```

Both queries were validated against hand-seeded data before being wired into `tracker.py`.

### Phase 3 — the test suite grows a real database

The old isolation trick — redirect `DATA_FILE` to a temp path — has no equivalent once storage is Postgres and every DB function opens its own connection. Options weighed:

- **Inject a connection/cursor into every function** (transaction-rollback isolation): correct, but every DB function gains an optional-parameter + skip-commit branch — production code reshaped for tests, and a future function that forgets the guard would silently commit test rows into the real database.
- **Delete-by-diff** (record existing IDs before, delete new ones after): zero prod changes, but cleanup bookkeeping grows with every table a test touches — and it runs against the same database that holds real logs.
- **Chosen: a separate `habits_test` database with a truncate-and-reseed fixture.** Same Postgres container, zero changes to `tracker.py`. `conftest.py` points the module at `habits_test`, and an autouse fixture runs `TRUNCATE habits, logs RESTART IDENTITY CASCADE` then reseeds the six habits before every test. Nothing a test writes can reach real data.

One-time setup (the container only auto-creates the `habits` database):

```bash
docker compose exec db psql -U habits -c "CREATE DATABASE habits_test;"
docker compose exec db psql -U habits -d habits_test -f schema.sql
```

Run the suite inside the compose network — the app resolves the database as host `db`, and pytest/psycopg live in the image, not the host venv:

```bash
docker compose exec web pytest -q
# 11 passed
```

Two gotchas from wiring this up: the image originally contained no tests at all — `test_tracker.py` was excluded by `.dockerignore` and neither it nor `conftest.py` had `COPY` lines in the Dockerfile — and the reset runs *before* each test, so a finished run leaves the last test's rows in `habits_test` (harmless; wiped on the next run).

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
- **Testing:** pytest against a disposable `habits_test` database (truncate + reseed per test)
- **Containerization:** Docker Compose v2 (`python:3.12-slim-bookworm` base, OS-patched)
- **Chapter 1 stack (archived):** AWS CodePipeline/CodeBuild, ECR, ECS Fargate, ALB, Trivy

## Project structure

```
.
├── tracker.py              # Flask app + CLI, reads/writes Postgres
├── test_tracker.py         # pytest suite — DB-backed, 11 tests (runs in the web container)
├── conftest.py             # points tests at habits_test; truncate + reseed per test
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

- ✅ Chapter 2: Postgres backend via Compose, dedupe in SQL, persistence across restarts
- ✅ Chapter 3: streak + last-7-days as SQL (gaps-and-islands / LEFT JOIN); 11 tests against the real DB via `habits_test`, green in-container
