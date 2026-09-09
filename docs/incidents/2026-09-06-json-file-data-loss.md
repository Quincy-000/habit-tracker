# Incident Postmortem — Habit data lost on every redeploy (JSON-file storage)

**Status:** Resolved — 2026-09-06 (commit `b94b1c1`)
**Severity:** Data loss (latent defect; single-user app, no production users)
**Component:** habit-tracker storage layer
**Fix commit:** `b94b1c1` — PostgreSQL backend via Docker Compose; dedupe moved to SQL; README Chapter 2

---

## Summary

The app originally stored every logged habit in a JSON file (`~/.habits.json`) **inside the container's filesystem**. Containers are disposable by design — each redeploy spins a fresh container with a fresh writable layer — so every redeploy silently wiped all logged habits. Storage was moved to PostgreSQL in a named volume; data now survives restarts and redeploys.

## Timeline (dates from git history)

| When | What |
|---|---|
| 2026-07-12 (`e601b79`) | Flask UI, Docker support and the AWS CI/CD pipeline added. Logs written to a JSON file inside the container. |
| July 2026 | App deployed to ECS Fargate via CodePipeline rolling deploys. Each deploy = new task = fresh container filesystem = **all logs gone**. |
| 2026-09-06 (`b94b1c1`) | Storage moved to Postgres 16 via Docker Compose with a named volume (`habits_data`); dedupe enforced in SQL (`ON CONFLICT DO NOTHING`); web service starts only after `pg_isready` healthcheck. |

## Root cause

State was stored in the container's **writable layer** — the one part of a container that is explicitly ephemeral. The deployment design (rolling deploys, immutable task replacement) made periodic data loss *guaranteed*, not possible: any successful deploy destroyed the previous data.

## Contributing factors

- **JSON chosen for zero-setup** during the learning phase — reasonable at the time, but nothing flagged it as non-durable as the app gained a real deployment pipeline.
- **No persistence test.** The original test suite monkeypatched `DATA_FILE` to a temp path — it tested the *logic*, never the *durability* of storage across a restart.
- **No export/backup path.** Once data was gone, it was unrecoverable by design.

## Blast radius

- The app had no production users — it was the vehicle for learning the pipeline (Chapter 1: "the pipeline was the point").
- Real data-loss count is **not quantified**: the ECS deployment was torn down after screenshots, and any habit logs written during that window would have been wiped on the next deploy. This postmortem does not invent a number.
- The durable lesson is architectural: the defect guaranteed loss on every deploy, so any real usage would have lost data repeatedly.

## The fix

Postgres 16 in Docker Compose with a **named volume** (`habits_data`), schema in `schema.sql`, seed in `seed.sql`:

```yaml
services:
  db:   postgres:16-alpine, named volume (habits_data), healthcheck via pg_isready
  web:  Flask app, waits for db using depends_on: condition: service_healthy
```

Data lives in the volume, not the container's writable layer. Deduplication moved from Python to a database constraint (`UNIQUE (habit_id, log_date)` + `ON CONFLICT DO NOTHING`) so the app can't silently double-log.

**Verification — the "money checkpoint":**

```
log a habit → docker compose restart → habit still there ✅
```

## Prevention / lessons

1. **State must live outside the container lifecycle** — a volume, a managed database, or object storage. If a container dies, everything it "owns" on its filesystem dies with it.
2. **Restart-survival is a first-class test.** The checkpoint above is now the documented acceptance criterion for storage changes, not an afterthought.
3. **Tests must exercise the real storage layer.** The follow-up (Chapter 3, `65f09b3`) formalized this: the suite runs against a disposable `habits_test` database, so tests hit real Postgres without touching real data.
4. **Deploy safety ≠ data safety.** Chapter 1's pipeline (immutable tags, approval gate, zero-downtime rolling deploys) made deploys *safe to ship* — but never addressed whether the data *survived* shipping. Two separate concerns; both need explicit gates.

## Related

- README Chapter 2 — the migration write-up in the app's own docs
- README Chapter 3 — DB-backed test isolation
- [Chapter 1 (archived)](../../README.md) — the original AWS pipeline this ran on
