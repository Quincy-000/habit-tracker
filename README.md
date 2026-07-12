# Habit Tracker — Containerized CI/CD Pipeline on AWS

A small Flask habit-tracking app used as the vehicle for a full, production-style CI/CD pipeline: automated testing, container vulnerability scanning, a manual approval gate, and zero-downtime deployment to AWS ECS Fargate behind a load balancer.

The app itself is intentionally simple. The pipeline is the point.

## Live Demo

> Demo was deployed to AWS ECS Fargate and torn down after screenshots were captured, to avoid ongoing infrastructure cost. See screenshots below for a working, publicly-reachable deployment.

## Architecture

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

## What the pipeline actually enforces

| Stage | Tool | Gate |
|---|---|---|
| Test | `pytest` | 11 tests covering habit logging, dedup logic, streak calculation, Flask routes — build fails if any test fails |
| Build | Docker | Multi-stage build on `python:3.12-slim-bookworm`, OS packages patched via `apt-get upgrade` |
| Security scan | Trivy | Hard-fails the build on any **fixable** HIGH/CRITICAL CVE (`--ignore-unfixed`, since gating on vulnerabilities with no available patch would make the pipeline permanently un-shippable through no fault of the code) |
| Approval | AWS CodePipeline manual approval | Pipeline pauses; requires an explicit human approval before any change reaches the running service |
| Deploy | ECS Fargate rolling deployment | New task must pass ALB health checks before old task is retired — zero downtime |

## Tech stack

- **App:** Python, Flask, Jinja2 templates
- **Testing:** pytest, with `monkeypatch`/`tmp_path` fixtures to isolate tests from real data
- **Containerization:** Docker (`python:3.12-slim-bookworm`)
- **Security scanning:** Trivy (OS + Python dependency CVE scanning)
- **CI/CD:** AWS CodePipeline, AWS CodeBuild
- **Registry:** Amazon ECR
- **Compute:** Amazon ECS on Fargate (serverless containers, no EC2 management)
- **Networking:** Application Load Balancer, VPC security groups (ALB and task security groups are separated — the task only accepts traffic from the ALB, never directly from the internet)
- **IAM:** Dedicated, least-privilege roles for CodeBuild, ECS task execution, and CodePipeline — each scoped only to the specific resources it needs to touch

## Project structure

```
.
├── tracker.py              # Flask app + CLI habit tracker logic
├── test_tracker.py         # pytest suite (11 tests)
├── templates/
│   └── index.html          # Web UI
├── Dockerfile               # python:3.12-slim-bookworm, OS-patched
├── buildspec.yml            # CodeBuild: test → build → Trivy scan → push
├── task-definition.json     # ECS Fargate task definition
├── pipeline.json             # CodePipeline definition (source/build/approval/deploy)
├── requirements.txt
└── requirements-dev.txt
```

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Run the tests
pytest -v

# Run the web app
python tracker.py web
# → http://127.0.0.1:5000

# Or use the CLI directly
python tracker.py today
python tracker.py log "Reading"
python tracker.py streak "Reading"
```

## Running in Docker

```bash
docker build -t habit-tracker .
docker run --rm -p 5000:5000 habit-tracker
```

## Notable engineering decisions

- **Debian `bookworm` over `trixie` for the base image** — an earlier build using `python:3.12-slim` (which defaults to `trixie`) surfaced 20 CVEs, all in the OS layer, with statuses of `affected`/`fix_deferred` — meaning no patch existed yet upstream, not a misconfiguration on this end. Switching to `bookworm`, a more mature Debian release, combined with `--ignore-unfixed` in the Trivy scan, keeps the security gate meaningful (it still catches anything genuinely fixable) without blocking on CVEs nobody can currently patch.
- **Two separate security groups** (ALB vs. task) rather than one shared group — the running container never accepts traffic directly from the internet, only from the load balancer, on the specific port it needs.
- **Immutable image tagging** — every build is tagged with both `latest` and the short git commit SHA, so any running deployment can be traced back to the exact commit that produced it, and rollback is a matter of redeploying a known-good tag rather than reconstructing what changed.
- **IAM roles scoped per service, not shared** — CodeBuild, ECS task execution, and CodePipeline each have their own role with only the permissions their specific job requires (e.g., the CodeBuild role only gained S3 artifact access once CodeBuild started reading source from CodePipeline's S3 bucket instead of directly from GitHub — permissions were added as the actual data flow required them, not granted broadly up front).

## Screenshots

 <img width="1349" height="714" alt="Screenshot 2026-07-12 224402" src="https://github.com/user-attachments/assets/3cc7ad1e-d204-463f-b0bc-8e1b29b09d29" />
 <img width="1365" height="526" alt="Screenshot 2026-07-12 224525 - Copy" src="https://github.com/user-attachments/assets/6ac1769b-cbde-4319-acda-18e45f2421cd" />
 <img width="908" height="593" alt="Screenshot 2026-07-12 155024" src="https://github.com/user-attachments/assets/162ecf42-8143-4b85-8171-063d777cd24c" />
 <img width="1361" height="507" alt="Screenshot 2026-07-12 224650 - Copy" src="https://github.com/user-attachments/assets/48492094-c4fc-4e88-a473-c0b3380accb0" />
 




---

Built as a hands-on exercise in production-style CI/CD: every piece — IAM roles, security groups, the load balancer, the pipeline stages — was stood up and debugged manually rather than templated, including working through a GitHub App authorization mismatch, an IAM `PassConnection` permission gap, and a CVE-fixed-vs-unfixed tradeoff that shaped the final Dockerfile.
