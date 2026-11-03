# Smart Support Ticket Management System

A portfolio support desk built with FastAPI, SQLAlchemy, PostgreSQL, JWT authentication, Celery, and Redis. Customers submit requests, agents work assigned tickets, and administrators manage the team and review reports.

## Features

- Customer signup, sign-in, ticket creation, and ticket conversations.
- Agent access to assigned tickets, customer replies, and status updates.
- Admin reports, agent creation and activation controls, and ticket assignment.
- Ticket status, priority, history, notifications, and recorded SLA breaches.
- Browser frontend, interactive API reference, and role-based API access.
- Docker Compose services for PostgreSQL, Redis, API, worker, and scheduler.

## Run locally on Windows

Requirements: Python 3.12 or later. Open PowerShell in this project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:DATABASE_URL = "sqlite:///./support.db"
$env:SECRET_KEY = [guid]::NewGuid().ToString() + [guid]::NewGuid().ToString()
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

In development mode, the app creates its SQLite tables at startup. If port 8000 is busy, change it to 8002 and use that port in the URLs below. Keep PowerShell open while using the app; press **Ctrl+C** to stop it.

- App: <http://127.0.0.1:8000/>
- API reference: <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/health>

The local SQLite setup does not run Redis or background SLA jobs. Use Docker Compose for PostgreSQL and scheduled tasks.

## Run with Docker Compose

Requirements: Docker Desktop with Compose. Copy `.env.example` to `.env`, replace `SECRET_KEY` with a long random value, and keep `POSTGRES_PASSWORD` and its password in `DATABASE_URL` matched. Then run:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open <http://127.0.0.1:8000/> or <http://127.0.0.1:8000/docs>. Stop with **Ctrl+C**. `docker compose down` removes the containers while preserving the named database volume.

## Create the first administrator

Public signup creates customers. From another PowerShell window in the project directory, create an admin account; the password prompt is hidden:

```powershell
.\.venv\Scripts\python.exe scripts\create_admin.py
```

For Docker, use `docker compose exec api python scripts/create_admin.py`. Sign in to the app home page with that admin email and password. Admins can see the **Reports** and **Team** sections.

## API overview

Routes use the `/api/v1` prefix. Register with `POST /api/v1/auth/register`; sign in with `POST /api/v1/auth/login` using form fields `username` (email) and `password`. Send the returned bearer token in the `Authorization` header.

Common routes:

- `POST /api/v1/tickets` and `GET /api/v1/tickets`
- `GET` or `PATCH /api/v1/tickets/{ticket_id}`
- `POST /api/v1/tickets/{ticket_id}/comments`
- `POST /api/v1/tickets/{ticket_id}/assign` (admin only; omit `agent_id` to unassign)
- `POST /api/v1/users/agents` and `PATCH /api/v1/users/{user_id}/activation` (admin only)
- `GET /api/v1/reports/summary`, `/api/v1/reports/agents`, and `/api/v1/reports/sla` (admin only)

## Development checks

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check .
```

GitHub Actions runs tests and Ruff on pushes and pull requests.

## Scope and production readiness

This is a portfolio MVP, not a production-hardened support platform. It does not send email, verify email addresses, rate-limit registration or sign-in, or provide first-response SLA tracking. The SLA task records resolution-time breaches for high and critical tickets. Local SQLite does not run background jobs.

Before deploying for real use, configure production credentials and secrets, TLS, backups, monitoring, and access controls. Add abuse protection, broader integration coverage, and operational alerting for the intended environment.
