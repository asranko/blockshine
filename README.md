# لُب (Lub) | NODO concept

An Arabic-first intentional social network focused on meaningful knowledge exchange instead of public popularity counters.

## Product rules implemented
- Four post intentions: أفيد، أتعلم، أوثّق ذكرى، أطلب مساعدة.
- Posts enter a 12-hour fridge and require explicit author confirmation after the full interval. Time expiry alone does not publish.
- No public like counter. Semantic signals: استفدت، فكرت، تواصلت معك.
- User profile visibility control, report workflow, and self-service account deletion.

## Architecture
- FastAPI serves the RTL web UI and JSON API.
- PostgreSQL in deployment; SQLite is only a local development fallback.
- SQLAlchemy models: users, posts, comments, semantic signals, saved posts, reports, audit events.
- Argon2 password hashing, signed expiring bearer tokens, server-side ownership checks.
- Health endpoint checks database connectivity.

## API
- GET /health, GET /api/meta
- POST /api/auth/register, POST /api/auth/login, GET /api/auth/me
- PATCH /api/profile, GET /api/profiles/{username}
- POST /api/posts, GET /api/posts, GET /api/posts/mine
- POST /api/posts/{id}/confirm, PATCH /api/posts/{id}, DELETE /api/posts/{id}
- POST /api/posts/{id}/comments, PUT /api/posts/{id}/signals/{kind}, PUT /api/posts/{id}/save
- POST /api/posts/{id}/reports, GET /api/saved, GET /api/discovery/topics, GET /api/admin/audit, DELETE /api/account

## Run locally
Python 3.11+: create a virtual environment, run `pip install -r requirements.txt`, set a strong `SECRET_KEY`, optionally set `DATABASE_URL`, then run `uvicorn main:app --host 0.0.0.0 --port 8000`. Visit `/` and `/docs`.

## Render environment
- `DATABASE_URL`: internal PostgreSQL URL.
- `SECRET_KEY`: strong random secret, never commit it.
- `ENVIRONMENT=production`.
- `ADMIN_EMAIL`: optional account allowed to read audit events.
- `TOKEN_HOURS`: token lifetime (default 24).

## Honest production gaps
This is an implementation-oriented MVP, not ready for an unrestricted public launch. Email verification, password reset, HttpOnly-cookie session design/CSRF protection, durable rate limiting, abuse detection, human moderation/appeals, notification delivery, search, recommendation-diversity measurement, migration tooling, backup/restore drills, accessibility review, and automated end-to-end tests remain. The current token is stored in sessionStorage, not an HttpOnly cookie. Do not store highly sensitive personal information.

The Render free Postgres instance created for validation expires after 30 days. It is temporary; select a durable database plan and backup policy before relying on community data.

Slow social should slow impulsive publishing, not block ordinary reading or require an AI council for every post. Recommendations must be measured for quality and bias rather than advertised as neutral by default.
