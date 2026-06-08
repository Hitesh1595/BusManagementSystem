# YatraTrack — Project Guide (CLAUDE.md)

Browser-based school-bus transport platform for Indian schools: live GPS tracking, attendance, and child-safety alerts. Roles: **school_admin**, **driver**, **parent** (self-register), **super_admin**.

**Source of truth:** `docs/YATRATRACK-BUILD-SPEC.md` (v1.0). Build plan: `docs/superpowers/plans/2026-06-03-yatratrack-backend.md`. Older docs in `docs/` are superseded (kept for history).

## Status

Backend MVP **Steps 1–5 complete** (tags `step-1`…`step-5`, `v0.3.0-alpha`): auth, schools, vehicles/drivers, routes/stops, students/transport-requests, trips + real-time GPS, safety system. **Frontend (Step 6) built** — `frontend/` (React 19 SPA: parent · driver · school_admin; super_admin is a V2 placeholder) + `landing/` (static marketing site). Design: `docs/superpowers/specs/2026-06-07-yatratrack-frontend-design.md`. Work happens on the `dev` branch (no remote configured; commits are local).

## Tech stack

Python 3.12 · FastAPI · SQLAlchemy 2.0 async + GeoAlchemy2 · Alembic · python-socketio (mounted on the same ASGI app) · APScheduler (in-process) · PostgreSQL 16 + PostGIS 3.4 · Redis 7 (AOF) · PyJWT + passlib[bcrypt] · structlog · Resend (transactional email). Managed with **uv**. Lint **ruff**, tests **pytest**.

**Frontend** (`frontend/`): React 19 · Vite 6 · TypeScript · Tailwind CSS 4 · shadcn-style UI primitives · TanStack Query over **ky** · Zustand (live socket state) · React Router 7 · Leaflet + react-leaflet (OSM tiles + Nominatim geocoding in dev) · socket.io-client · react-i18next · Vitest. `landing/` is a static single-page marketing site (Tailwind Play CDN, no build step).

## Run & develop

Everything runs via Docker Compose from the **repo root**:

```bash
docker compose up -d --build        # app :8000, db :5432, redis :6379
curl localhost:8000/health          # {"status":"ok","db":"connected","redis":"connected"}
open http://localhost:8000/docs      # OpenAPI (no Authorize button yet — use curl with Bearer)
docker compose down                  # stop all (use -v to also wipe data volumes)
```

Backend dev commands (run inside `backend/` with `uv`; needs db+redis up and a `.env` — copy `.env.example`, it points at `localhost`):

```bash
cd backend
uv sync                              # install deps
uv run alembic upgrade head          # apply migrations (0001–0009)
uv run pytest --no-cov -q            # tests
uv run ruff check .                  # lint
uv run uvicorn app.main:app --reload --port 8000   # run without Docker
```

**Seed** (creates first school + admins, prints the parent join code):

```bash
docker compose exec app /app/.venv/bin/python -m scripts.seed
# defaults: admin@demo.school / Admin1234!  ·  super@yatratrack.in / Super1234!
```

**Frontend** (`frontend/`, needs the backend up; the Vite dev server proxies `/api` + `/socket.io` → `:8000`, so the app runs same-origin):

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
npm run build        # tsc --noEmit + vite build
npm run test         # Vitest
```

The static landing site needs no build: open `landing/index.html` or `npx serve landing`.

## Architecture essentials

- **Single ASGI process**: FastAPI + Socket.IO + APScheduler + an asyncio GPS-flush task, all in one process (`app/main.py`).
- **Modular monolith**: feature modules each have `models.py · schemas.py · services.py · router.py`, registered explicitly in `main.py`. Modules: `auth`, `schools`, `vehicles` (+ drivers), `routes` (+ stops + transport_requests), `students`, `tracking` (trips, GPS, `socket_handlers.py`, `safety.py`, `eta.py`, `gps_buffer.py`), `alerts`, `notifications`, `audit`.
- **Multi-tenancy**: every tenant query is scoped by `school_id` from the JWT claim via `app/deps.py` (`get_school_scope`, `require_role`) + `app/crud.py` (`get_scoped_or_404`, `scoped_select`). `super_admin` has `school_id=NULL` and bypasses scoping.
- **Real-time GPS**: driver emits `location_update` over Socket.IO → rate-limited (≤1/3s) → broadcast to `trip:{id}` room + buffered in Redis (`gps:buffer:{id}`) → flushed every 30s into the partitioned `gps_logs` table. ETA/`bus_approaching` computed in-process (no DB on the hot path).
- **Safety system** (`tracking/safety.py`, the core differentiator): not-boarded detection on stop-complete; the **safeguarding gate** blocks trip end until every boarded student is dropped — `_complete_trip` uses a `rowcount` guard so concurrent driver-drop + admin-resolve complete the trip **exactly once**.
- **Frontend** (`frontend/`): single Vite SPA with role-based lazy routes under `src/features/{auth,parent,driver,admin}`; shared contracts live in `src/lib` (typed `ky` client + 401→refresh-once interceptor, typed Socket.IO client, TS types mirroring the API) and `src/stores` (Zustand: `auth`, `liveTrip`). **Two backend reads were added for the UI**: the `notifications` router (bell — list/`{id}`/read/read-all/preferences) and `GET /trips/{id}/stops` (driver run-trip + parent live-track need stop geometry, but the `routes` module is admin-only).

## Conventions

- **Workflow: feature-first.** Implement features directly and verify by exercising the live API (in-process httpx ASGITransport or curl) — not test-first TDD. The committed pytest suite is intentionally light; don't gate work on it unless asked.
- **Auth**: 15-min access JWT (`Authorization: Bearer`) + 30-day refresh in an HttpOnly cookie with rotation + family theft detection. Parents self-register with a school `join_code`; drivers/admins are created. Password reset is single-use, 1-hr; in **dev** the reset link is logged (`auth.password_reset_dev_link`) since no email is sent.
- **API**: base `/api/v1`; error envelope `{"error":{code,message,details}}`; lists paginated `{items,total,limit,offset}`.
- **Frontend↔API**: collection roots need a **trailing slash** (`/vehicles/`, `/drivers/`, `/routes/`, `/students/`, `/transport-requests/`, `/trips/`) — without it FastAPI 307-redirects (cross-origin through the dev proxy). UI strings go through `react-i18next` (`t('key', 'English default')`); locale JSON under `src/locales` is English-only in MVP.
- **Rate limits** (env-tunable, `RATELIMIT_*`): `/api/v1/auth/*` 5/min per IP, other routes 100/min per user. Separate from account lockout (`ACCOUNT_LOCKOUT_*`, 5 failed logins → 15-min). Limiter currently keys on the direct connection IP — **needs `X-Forwarded-For` before running behind Caddy**.
- **Time**: store UTC `TIMESTAMPTZ`, render IST (`Asia/Kolkata`).
- **Commits**: Conventional Commits (`feat(scope): …`).

## Gotchas (learned the hard way)

- **Docker venv**: `backend/.dockerignore` MUST exclude `.venv/` — otherwise `COPY . .` overwrites the image's Linux venv with the host one (broken interpreter → `alembic: not found`).
- **Socket handlers import**: in `main.py` use `from app.tracking import socket_handlers as _socket_handlers` — a bare `import app.tracking.socket_handlers` rebinds the module-level name `app` over the FastAPI instance.
- `Alert` model: the JSONB attribute is `metadata_` (mapped to DB column `metadata`) because SQLAlchemy reserves `metadata`.
- `gps_logs` is **range-partitioned by month** (declarative DDL is hand-written in the migration); partitions are pre-created and maintained by the `ensure_gps_partitions` / `cleanup_gps_logs` jobs.

---

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
