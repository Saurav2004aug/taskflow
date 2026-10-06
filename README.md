# TaskFlow — Full-Stack Kanban Task Manager

[![CI](https://github.com/YOUR_GITHUB_USERNAME/taskflow/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_GITHUB_USERNAME/taskflow/actions)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-Open%20App-brightgreen)](https://taskflow-61mu.onrender.com)

A production-oriented full-stack Kanban task manager built with **React + TypeScript**, **Flask**, and **PostgreSQL**. It includes JWT authentication, drag-and-drop task management, search, filtering, dashboard statistics, Docker deployment, CI/CD, and browser-level E2E testing.

> **Live demo:** https://taskflow-61mu.onrender.com

## Highlights

- JWT authentication with scrypt password hashing
- Per-user data isolation
- Kanban drag-and-drop with optimistic UI and rollback on failure
- Fractional indexing so a card move updates one row instead of renumbering a column
- Debounced PostgreSQL search using `pg_trgm`
- Priority filters, due dates, overdue highlighting, pagination and dashboard statistics
- Login rate limiting and non-enumerating login responses
- PostgreSQL migrations protected by advisory locks
- Docker + Docker Compose + Render deployment configuration
- GitHub Actions CI
- Unit, integration and Playwright browser tests

## Architecture

```text
React + TypeScript SPA
        |
        | /api/*
        v
Flask + Gunicorn
        |
        v
PostgreSQL
```

The production container serves the built React application and Flask API from one origin.

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | React 19, TypeScript, Vite, CSS |
| Backend | Python 3.12, Flask 3, Gunicorn |
| Database | PostgreSQL 16, psycopg 3, pg_trgm |
| Auth | JWT, PyJWT, scrypt |
| Testing | unittest, node:test, Playwright |
| DevOps | Docker, Docker Compose, GitHub Actions, Render |

## Run locally

### Docker

```bash
docker compose up --build
```

Open:

```text
http://localhost:8000
```

### Development servers

```bash
cp .env.example .env
```

Start PostgreSQL, configure `DATABASE_URL` and `JWT_SECRET`, then:

```bash
cd backend
pip install -r requirements.txt
python run_dev.py
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

## Testing

Backend:

```bash
cd backend
python -m unittest discover -s tests -v
```

Frontend:

```bash
cd frontend
npm test
npm run typecheck
```

E2E:

```bash
cd frontend
npx playwright install chromium
E2E_BASE_URL=http://127.0.0.1:5000 npm run test:e2e
```

The E2E suite covers registration, task creation, drag-and-drop, persistence, search, editing, deletion, logout/login, multi-user isolation and mobile viewport behavior.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Authenticate |
| GET | `/api/auth/me` | Current user |
| GET | `/api/tasks` | List/search/filter tasks |
| POST | `/api/tasks` | Create task |
| GET/PATCH/PUT/DELETE | `/api/tasks/:id` | Manage task |
| GET | `/api/tasks/stats` | Dashboard statistics |
| GET | `/health` | Health check |

## Engineering decisions

### Fractional indexing

Instead of renumbering every card after a drag operation, task positions are represented as values between neighboring positions. Moving a card between `1.0` and `2.0` can assign `1.5`, reducing the database work to a single row update.

### Optimistic UI

The board updates immediately in the browser. If the API rejects the operation, the previous state is restored and the user sees an error.

### Database-level isolation

Every task query is scoped by `user_id`, so authenticated users cannot access another user's tasks.

### Real PostgreSQL tests

Backend tests run against PostgreSQL rather than replacing the production database with SQLite or mocks. This validates actual constraints, indexes and SQL behavior.

## Deployment

Deployment instructions are in [`docs/DEPLOY.md`](docs/DEPLOY.md).

The repository includes a Render blueprint and Docker configuration.

## Roadmap

- Refresh tokens using httpOnly cookies
- Shared boards with roles
- Real-time multi-tab synchronization
