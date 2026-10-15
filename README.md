# لُب (Lub) | NODO concept

Arabic-first intentional social network for meaningful knowledge exchange instead of public popularity counters.

## Product rules in this prototype
- Four publishing intentions: أفيد، أتعلم، أوثّق ذكرى، أطلب مساعدة.
- Posts enter a 12-hour fridge and require explicit author confirmation after the full interval. Time expiry alone does not publish.
- No public like counter; semantic signals are استفدت، فكرت، تواصلت معك. Public aggregate counts are not returned by the API.
- Profile visibility control, comments, saved posts, reports, audit events, and self-service account deletion.

## Architecture
- FastAPI serves the Arabic RTL web UI and JSON API.
- SQLAlchemy models for users, posts, comments, semantic signals, saved posts, reports, and audit events.
- Argon2 password hashing, signed expiring bearer tokens, and server-side ownership checks.
- Health endpoint reports both reachability and the actual database backend.

## Current deployment state
- Public URL: https://lub-social.onrender.com/
- Health endpoint: https://lub-social.onrender.com/health
- Metadata endpoint: https://lub-social.onrender.com/api/meta
- Latest verified health result: service healthy, but `database_backend=sqlite` and `postgres_configured=false`.
- **Do not use the current deployment for real community data.** SQLite on a Render instance is not the intended durable setup. The existing Postgres database is available but its connection reference has not yet been activated for this service.

## Render database wiring
The root `render.yaml` declares `DATABASE_URL` as a reference to the existing `lub-social-db` resource. Render Blueprints support this `fromDatabase` reference even when the database is already present in the same workspace (see [Render Blueprint spec](https://render.com/docs/blueprint-spec)).

Because `lub-social` was originally created outside a Blueprint, committing `render.yaml` **does not activate the reference by itself**. A Blueprint must be connected to this repository and branch in Render, and the initial sync must be approved. Resource names intentionally match the current service and database to avoid creating a duplicate app or database.

After sync, verify `GET /health` reports `database_backend=postgresql` and `postgres_configured=true` before using real data.

## API
- `GET /health`, `GET /api/meta`
- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `PATCH /api/profile`, `GET /api/profiles/{username}`
- `POST /api/posts`, `GET /api/posts`, `GET /api/posts/mine`
- `POST /api/posts/{id}/confirm`, `PATCH /api/posts/{id}`, `DELETE /api/posts/{id}`
- `POST /api/posts/{id}/comments`, `PUT /api/posts/{id}/signals/{kind}`, `PUT /api/posts/{id}/save`
- `POST /api/posts/{id}/reports`, `GET /api/saved`, `GET /api/discovery/topics`, `GET /api/admin/audit`, `DELETE /api/account`

## Test coverage and status
`tests/test_lub_api.py` covers health metadata, product rules, fridge timing, exclusion of pending posts from the public feed, explicit publishing after the fridge, ownership enforcement, signal-count privacy, and visibility isolation for hidden profiles.

`.github/workflows/lub-api-tests.yml` is configured to run these tests. The first observed GitHub Actions run did not start the job because GitHub reported: "The job was not started because your account is locked due to a billing issue." Therefore these automated tests are **not verified as passing**. Do not interpret the existence of test files or a workflow as a successful test run.

## Run locally
Python 3.12+: create a virtual environment, run `pip install -r requirements.txt`, set a strong `SECRET_KEY`, optionally set `DATABASE_URL`, then run `uvicorn main:app --host 0.0.0.0 --port 8000`. Visit `/` and `/docs`. To run regression tests, install `requirements-dev.txt` and run `python -m pytest -q`. The Render Blueprint build command also runs these tests before deployment.

## Environment variables
- `DATABASE_URL`: intended to be the internal PostgreSQL connection URL.
- `SECRET_KEY`: strong random secret; never commit it.
- `ENVIRONMENT=production`.
- `ADMIN_EMAIL`: optional account allowed to read audit events.
- `TOKEN_HOURS`: token lifetime (default 24).
- `PYTHON_VERSION=3.12.8` on Render.

## Honest production gaps
This is an MVP, **not ready for unrestricted public launch**. Still missing or unverified: PostgreSQL connection activation, email verification, password reset, HttpOnly-cookie session design and CSRF protection, durable rate limiting, abuse detection, human moderation and appeals, notification delivery, search, recommendation-diversity measurement, migration tooling, backup/restore drills, accessibility review, full browser end-to-end tests, and a verified passing API test run. The current token is stored in sessionStorage, not an HttpOnly cookie. Do not store highly sensitive personal information.

The current Render Postgres instance is on a temporary free plan and is scheduled to expire on 13 November 2026. It needs a durable plan and backup policy before relying on community data.

Slow social should slow impulsive publishing, not block ordinary reading or require an AI council for every post. Recommendations must be measured for quality and bias rather than advertised as neutral by default.
