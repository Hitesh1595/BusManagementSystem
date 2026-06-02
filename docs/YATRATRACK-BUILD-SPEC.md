# YatraTrack — Production Build Specification

**Version:** 1.0
**Date:** 2026-05-30
**Status:** Authoritative — ready for development handoff
**Author:** Hitesh Singh
**Supersedes:** `MASTER-PLAN.md`, `school-bus-management-system.md`, `school-bus-revision-2-additions.md`, `school-bus-revision-3-chat-removal.md` (kept for history; this document is the single source of truth)

---

## 0. How to use this document (for the development agent)

This is the complete, self-contained specification for building YatraTrack. Read it top to bottom before writing code.

- **Section 2 (Decisions Made)** is binding. Every previously-open question has a resolved answer. Do not re-litigate; if a decision blocks you, raise it explicitly.
- **Phases are sequential.** Build **MVP (Phase 1 → Phase 2)** first and ship the Week-8 demo. Do not start V2 work until MVP acceptance criteria pass.
- **`§21 Phased Build Plan`** is your step-by-step task list with per-step acceptance criteria. Treat each step's acceptance criteria as the definition of done.
- **`§6 Data Model`** is the full schema. All tables, columns, enums, and indexes are listed even when the feature is V2 — create V2 tables only in the V2 migration, but design MVP migrations so V2 columns can be added without rewrites.
- **Guiding constraints (non-negotiable):** keep it **simple to use**, keep **server cost and maintenance minimal**, but **include everything a child-safety transport product genuinely requires**. When two designs are equally correct, pick the one with fewer moving parts.
- **Anything marked `[LAUNCH-BLOCKING]`** is a business input (domain, phone number, pilot data) needed before go-live, not before coding. Use the documented placeholder and keep building.

---

## 1. Product Identity

| Field | Value |
|---|---|
| **Product Name** | YatraTrack |
| **Meaning** | Yatra (journey) + Track (GPS tracking) |
| **Tagline** | बच्चों का सफर, Safe & Tracked. |
| **Positioning** | Browser-based school transport management platform for Indian schools |
| **Target Market** | India only (MVP). INR, IST, Razorpay (Future), MSG91 (Future) |
| **Domain** | `yatratrack.in` (primary) / `yatratrack.app` (redirect) — `[LAUNCH-BLOCKING]` to register |
| **WhatsApp** | `+91XXXXXXXXXX` — `[LAUNCH-BLOCKING]` |
| **Contact Email** | `hello@yatratrack.in` — `[LAUNCH-BLOCKING]` |

### 1.1 Actors & roles

| Role | enum value | Description | school_id |
|---|---|---|---|
| Super Admin | `super_admin` | Manages multiple schools, platform settings (**V2 UI**) | `NULL` |
| School Admin | `school_admin` | Manages fleet, routes, drivers, requests, settings. Primary paying customer. | required |
| Driver | `driver` | Receives route, shares GPS, marks attendance. Admin-created. | required |
| Parent/Guardian | `parent` | Self-registers with school code, registers children, requests transport, tracks bus, gets alerts. | required |
| Student | *(not a user)* | Passive — tracked via attendance, linked to a parent. No login. | — |

---

## 2. Decisions Made (authoritative — overrides all prior docs)

Every previously-open question and every identified gap is resolved here. The "ID" maps to the original open-question/gap label for traceability.

### 2.1 Product & scope
| ID | Decision |
|---|---|
| OQ-2 | **India-only** for MVP/V2. Global = Future. Currency INR, timezone `Asia/Kolkata`. |
| OQ-4 | **English UI in MVP, i18n-ready from day 1** (react-i18next, all strings externalized into locale files; no hard-coded UI strings). Hindi + one regional language = V2. Landing page copy stays Hinglish. |
| OQ-6 | Min device: **Android 9+ / Chrome 90+, iOS 15+ Safari** (browser MVP). Capacitor V2 targets **Android 9+**. |
| OQ-19 | Capacitor driver app = **Android only (V2)**; iOS = Future. |

### 2.2 Auth & registration
| ID | Decision |
|---|---|
| OQ-3 | **Hybrid registration.** Parents **self-register using a per-school join code** (`schools.join_code`). Drivers and school admins are **created by an admin**. Super-admin bootstrapped via seed. |
| — | **Email verification deferred to V2.** MVP gate for self-registration is the school join code only. `users.email_verified` column exists now (default `false`, unused in MVP). |
| G5 | **Password reset is in MVP** (`forgot-password`/`reset-password`) via **Resend transactional email**. Distinct from user-facing *email notifications* (V13). Tokens in `auth_tokens` table, hashed, 1-hour expiry. |
| OQ-11 | Refresh token expiry = **30 days**, with rotation + family theft detection. Access token = **15 min**. |
| G6 | `super_admin` has `school_id = NULL`; bypasses app-scope and (V2) RLS by role. |

### 2.3 Data model gaps closed
| ID | Decision |
|---|---|
| G1 | **`trips.scheduled_departure_at TIMESTAMPTZ`** added. Set at trip generation from the route's first stop `arrival_time` on `scheduled_date`. Drives no-show, ETA, and absent-mark deadline. |
| G2 | **School-as-location modeled.** `schools.school_location` (Point). `attendance_records.drop_type (stop\|school)` + nullable `drop_stop_id`. **Morning** trips: board at stops → drop at school. **Evening** trips: board at school → drop at stops. |
| G3 | **`notifications` table added** (M9 in-app notifications, P0). |
| G4 | **`audit_logs` table added** (driver-phone disclosure, entity changes, compliance). |
| G7 | **`users.notification_prefs JSONB` added** (backs `/notifications/preferences`). |
| G9 | **No file upload, no object storage.** Avatars/logos are text/initials in UI. `schools.logo_url` is an optional pasteable external URL only. V2 reports are generated on demand and **streamed** (no storage). |
| — | Re-added: `attendance_records.marked_location`, `trips.reassignment_reason`, `trips.current_stop_order`. |
| — | `transport_requests.status` enum = `pending\|approved\|rejected\|assigned`. Single `parent_id` per student (multi-guardian = Future). |

### 2.4 Trip & safety semantics
| ID | Decision |
|---|---|
| OQ-12 | Trip end is **blocked** → `pending_safeguard_check` until every boarded student is dropped/accounted. Not warn-only. |
| OQ-13 | Attendance is **flexible** (mark any boarded student any time); **batch-submitting a stop is the explicit "stop complete" trigger** for not-boarded detection. No forced sequential stop order. |
| OQ-14 | Parent absent-mark allowed **until `trip.status = in_progress`** (driver start = cutoff). |
| — | **Trip generation:** admin "Generate today's trips" endpoint **+** optional daily APScheduler job at **06:00 IST** from active routes (toggle in school settings). |
| G8 | **APScheduler jobs added:** `check_driver_no_show` (every 5 min during school hours), `check_vehicle_compliance` (daily). **`driver_no_show` added to `alerts.type`.** |
| OQ-15 | Driver feedback visibility (V2): **aggregate only to driver** (average + count); admin sees full text + comments. |

### 2.5 Infrastructure & operations (minimal cost/maintenance)
| ID | Decision |
|---|---|
| **ARCH** | **No Celery in MVP.** Periodic jobs run via **APScheduler in-process**; GPS buffer flush is an **asyncio** background task. Celery is (re)introduced in **V2 only** if push fan-out / report generation load requires it. |
| G10 | Timezone **`Asia/Kolkata`** app-wide. Store UTC `TIMESTAMPTZ`; render IST. `schools.timezone` column for future multi-region. |
| G11 / M2 | **MVP = app-level `school_id` scoping.** **V2 = PostgreSQL RLS + super-admin UI.** `school_id` columns + JWT claim present from day 1. M2 reworded "multi-school-**ready**." |
| OQ-8 | Map tiles: **Stadia Maps** (200k/mo free) prod; OSM dev only. |
| OQ-9 | Geocoding: **MapTiler** prod (100k/mo); Nominatim public dev only. |
| OQ-10 | Redis persistence: **AOF, `appendfsync everysec`** (GPS-buffer durability). |
| OQ-17 | Retention: app logs **30d**, GPS logs **90d**, attendance **1y**, audit_logs **7y**, payments **7y**. |
| OQ-18 | Driver phone: **school-level toggle only** (per-driver opt-out = Future). |
| OQ-5 | Bulk CSV import = **V2** (MVP relies on parent self-service, so no mass manual entry). |
| — | Pagination `limit`/`offset` (default 50, max 100); error envelope `{error:{code,message,details}}`; soft-delete via `is_active`. |

### 2.6 `[LAUNCH-BLOCKING]` — business inputs, do not block coding
OQ-1 pilot school & real capacity numbers · OQ-7/20/21/22 domain, WhatsApp number, contact email, branding assets · OQ-16 exact compliance-report fields (ship the default template in §15.2, marked "confirm with transport authority").

---

## 3. Architecture

### 3.1 Principles
1. **Single ASGI process** — FastAPI + Socket.IO mounted together (`python-socketio` ASGIApp). Not two services.
2. **Modular monolith** — feature modules with explicit `include_router()`. No auto-discovery, no plugin registry (Future).
3. **Minimal moving parts** — MVP runtime = **1 app process + PostgreSQL + Redis**. No worker process, no object storage, no message broker beyond Redis.
4. **Simple to use** — every role's primary task is a few taps with sensible defaults (see §9 UX rules).
5. **Graceful degradation** — WebSocket loss shows clear loading state; REST still serves core data; stale GPS shows "Tracking paused" with last-known position + timestamp (never stale-as-live).
6. **Multi-school-ready** — `school_id` everywhere from day 1; full multi-tenancy (RLS) switches on in V2 with no schema rewrite.

### 3.2 Component diagram (MVP)

```
+-------------------------------------------------------------+
|                       CLIENTS (browser)                      |
|  Parent SPA      Driver SPA       Admin SPA                  |
|  (React+Leaflet) (React+Leaflet)  (React+charts)             |
|  GPS: receive    GPS: send        GPS: monitor               |
+----------------------------+--------------------------------+
                             | HTTPS / WSS
                             v
+-------------------------------------------------------------+
|                  Caddy 2 (auto-HTTPS, reverse proxy)         |
+----------------------------+--------------------------------+
                             v
+-------------------------------------------------------------+
|        SINGLE ASGI PROCESS (FastAPI + Socket.IO)            |
|                                                             |
|  REST API        Socket.IO            In-process workers:   |
|   auth, CRUD,     GPS broadcast,       - APScheduler        |
|   biz logic       rooms, safety        (no-show, compliance,|
|                   events               cleanup, trip-gen)   |
|                                        - asyncio GPS flush  |
+----------------+---------------------------+----------------+
                 v                           v
        +----------------+          +------------------+
        | PostgreSQL 16  |          | Redis 7 (AOF)    |
        | + PostGIS 3.4  |          | - GPS buffer     |
        | - all app data |          | - rate limiting  |
        | - geospatial   |          | - account lockout|
        | - partitioned  |          | - (V2) SIO adapter|
        |   gps_logs     |          | - (V2) corridor  |
        +----------------+          +------------------+
```

> **V2 additions:** Capacitor Android driver app; web-push; Socket.IO Redis adapter for horizontal scale; optional Celery worker if report/push load grows; route-deviation corridor cache.

### 3.3 GPS tracking — critical path

```
Driver device  (MVP: browser watchPosition every 5s | V2: @capacitor/geolocation in background)
  → Socket.IO client emits "location_update" {trip_id, lat, lng, speed, heading, accuracy, ts}
    → Socket.IO handler (single ASGI process), SYNCHRONOUS, sub-ms:
       3a. authorize (driver of this trip?) + rate-limit (≤1 / 3s / connection)
       3b. broadcast to room "trip:{trip_id}" → all subscribed parents + admin
       3c. push point to Redis list  gps:buffer:{trip_id}
       3d. ETA: straight-line distance to next stop / rolling avg speed
           if within 200m of next stop → emit "bus_approaching" to that stop's parents
       3e. (V2) route-deviation: ST_DWithin(point, redis_corridor, 500m); 2 consecutive misses → alert
  → asyncio task every 30s: batch-INSERT buffered points into gps_logs (monthly partition); on shutdown, flush
  → Parent SPA: Leaflet marker animates; ETA updates; if no update >30s → "Tracking paused" + last-known + timestamp
```

### 3.4 Offline GPS (V2)
Driver loses signal → client buffers points in IndexedDB (watchPosition keeps firing) → on reconnect, emit `location_batch` → server inserts to `gps_logs` but does **not** re-broadcast stale points; resumes live from current position. Parents saw "Tracking paused" during the gap. Trip history later shows the full path.

### 3.5 Module → directory map
`auth` · `schools` · `vehicles` (+ drivers) · `routes` (+ stops + transport requests) · `tracking` (trips, GPS, Socket.IO handlers, `safety.py`) · `notifications` · `communication` (broadcasts V2, complaints V2) · `reports` (V2) · `payments` (V2 structure, Future gateways). Full tree in §23.

---

## 4. Tech Stack (final)

| Layer | Technology | MVP? | Notes |
|---|---|---|---|
| Language | Python 3.12+ | ✅ | |
| Backend | FastAPI 0.115+ | ✅ | async, auto OpenAPI |
| ORM | SQLAlchemy 2.0 async | ✅ | `pool_size=20, max_overflow=10, pool_timeout=30` |
| Migrations | Alembic | ✅ | |
| Geospatial ORM | GeoAlchemy2 | ✅ | PostGIS types |
| Real-time | python-socketio 5.x | ✅ | mounted on same ASGI app |
| **Scheduler** | **APScheduler 3.x (in-process)** | ✅ | replaces Celery in MVP |
| Task queue | Celery 5.x + Redis | ❌ V2 | only if push/report load needs it |
| Auth | PyJWT + passlib[bcrypt] | ✅ | bcrypt cost 12 |
| DB | PostgreSQL 16 + PostGIS 3.4 | ✅ | ACID + geospatial |
| Cache | Redis 7 (AOF) | ✅ | GPS buffer, rate-limit, lockout |
| Email (transactional) | Resend | ✅ | password reset only in MVP (3k/mo free) |
| Frontend | React 19 + Vite 6 | ✅ | single SPA, role-based |
| UI | shadcn/ui + Tailwind CSS 4 | ✅ | |
| i18n | react-i18next | ✅ | English only in MVP, strings externalized |
| Maps | Leaflet 1.9 + react-leaflet | ✅ | |
| Tiles | Stadia Maps (prod) / OSM (dev) | ✅ | |
| Geocoding | MapTiler (prod) / Nominatim (dev) | ✅ | |
| State | Zustand | ✅ | live GPS state |
| HTTP client | ky | ✅ | |
| Socket client | socket.io-client | ✅ | |
| PDF / Excel | reportlab / openpyxl | ❌ V2 | pure Python, streamed (no storage) |
| Error tracking | Sentry | ✅ | Python + React |
| Logging | structlog | ✅ | JSON, scrubbed |
| Reverse proxy | Caddy 2 | ✅ | auto-HTTPS |
| Containers | Docker + Compose | ✅ | |
| Testing | pytest, pytest-asyncio, httpx | ✅ | |
| E2E / load | Playwright / locust | ❌ V2 | |
| Lint/format | Ruff | ✅ | |
| Frontend test | Vitest + RTL | ✅ | |
| CI/CD | GitHub Actions | ✅ | |
| Uptime | UptimeRobot | ✅ | |
| PWA + web-push | Vite PWA + pywebpush/VAPID | ❌ V2 | |
| Driver native | Capacitor + @capacitor/geolocation | ❌ V2 | Android only |
| Payments | Razorpay (primary) / Stripe (fallback) | ❌ Future | |

---

## 5. Environments & Configuration

### 5.1 Environments
| Env | LOG_LEVEL | Tiles | Geocoding | Email | Notes |
|---|---|---|---|---|---|
| `dev` | DEBUG | OSM | Nominatim public | Resend test/sandbox | Docker Compose locally |
| `staging` | WARNING | Stadia | MapTiler | Resend | mirrors prod |
| `prod` | WARNING | Stadia | MapTiler | Resend | Railway |

### 5.2 Environment variables (canonical list)
```
# Core
APP_ENV=dev|staging|prod
APP_TIMEZONE=Asia/Kolkata
SECRET_KEY=<jwt signing secret>
FRONTEND_URL=https://app.yatratrack.in     # CORS allow-origin (no wildcard)

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/yatratrack
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30

# Redis
REDIS_URL=redis://host:6379/0

# Auth
ACCESS_TOKEN_TTL_MIN=15
REFRESH_TOKEN_TTL_DAYS=30
ACCOUNT_LOCKOUT_THRESHOLD=5
ACCOUNT_LOCKOUT_TTL_MIN=15
BCRYPT_ROUNDS=12

# Email (transactional)
RESEND_API_KEY=<key>
EMAIL_FROM="YatraTrack <no-reply@yatratrack.in>"

# Maps / Geocoding
STADIA_API_KEY=<key>
MAPTILER_API_KEY=<key>

# Observability
SENTRY_DSN=<dsn>
LOG_LEVEL=DEBUG|WARNING
LOG_RETENTION_DAYS=30

# Scheduling
TRIP_AUTOGEN_ENABLED=true            # per-deploy default; school setting can override
TRIP_AUTOGEN_HOUR=6                  # 06:00 IST
SCHOOL_HOURS_START=6
SCHOOL_HOURS_END=18

# GPS
GPS_FLUSH_INTERVAL_SEC=30
GPS_STALE_THRESHOLD_SEC=30
GPS_RETENTION_DAYS=90
```

### 5.3 `schools.settings` JSONB (feature flags & tunables)
```jsonc
{
  "driver_phone_visible": false,        // show driver phone to parents during active trip
  "trip_autogen_enabled": true,         // daily 06:00 IST trip generation
  "bus_approaching_radius_m": 200,      // proximity for "bus approaching"
  "payments_enabled": false,            // V2
  "feedback_enabled": false             // V2
}
```

---

## 6. Data Model

**Conventions:** UUID PKs (`gen_random_uuid()`) except high-volume `gps_logs`/`audit_logs` (BIGSERIAL). All timestamps `TIMESTAMPTZ` stored UTC. Geospatial columns are `geography(Point|LineString, 4326)`. Every tenant table carries `school_id` (nullable only on `users`/`audit_logs` for `super_admin`/system rows). Soft-delete via `is_active`. `created_at`/`updated_at` default `now()`.

### 6.1 Enum types
```sql
CREATE TYPE user_role        AS ENUM ('super_admin','school_admin','driver','parent');
CREATE TYPE vehicle_type     AS ENUM ('bus','van','car','minibus');
CREATE TYPE schedule_type    AS ENUM ('morning','evening','both');
CREATE TYPE request_status   AS ENUM ('pending','approved','rejected','assigned');
CREATE TYPE trip_status      AS ENUM ('scheduled','in_progress','pending_safeguard_check','completed','cancelled','incident');
CREATE TYPE attendance_status AS ENUM ('boarded','absent','absent_parent_marked');
CREATE TYPE drop_type        AS ENUM ('stop','school');
CREATE TYPE alert_type       AS ENUM ('child_not_boarded','child_not_dropped','driver_no_show','sos','route_deviation','incident','insurance_expiry','driver_behavior_pattern');
CREATE TYPE alert_severity   AS ENUM ('critical','high','medium','low');
CREATE TYPE auth_token_type  AS ENUM ('password_reset','email_verification');
CREATE TYPE notification_type AS ENUM ('trip_started','trip_ended','attendance','child_not_boarded','child_not_dropped','bus_approaching','broadcast','alert','generic');
-- V2:
CREATE TYPE billing_cycle    AS ENUM ('one_time','monthly','quarterly','term','annual');
CREATE TYPE invoice_status   AS ENUM ('draft','sent','paid','overdue','cancelled');
CREATE TYPE payment_gateway  AS ENUM ('razorpay','stripe','manual','offline');
CREATE TYPE payment_status   AS ENUM ('pending','completed','failed','refunded');
CREATE TYPE complaint_against AS ENUM ('driver','route','vehicle','general');
CREATE TYPE complaint_status AS ENUM ('open','in_review','resolved','closed');
CREATE TYPE priority         AS ENUM ('low','medium','high','urgent');
CREATE TYPE report_type      AS ENUM ('compliance','attendance','incident','trip_summary');
CREATE TYPE report_format    AS ENUM ('pdf','xlsx');
CREATE TYPE report_status    AS ENUM ('pending','generating','completed','failed');
```

### 6.2 Core tables (MVP)

```sql
CREATE TABLE schools (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name          VARCHAR(200) NOT NULL,
  address       TEXT,
  phone         VARCHAR(20),
  email         VARCHAR(255),
  logo_url      TEXT,                              -- optional pasteable external URL (no upload)
  timezone      VARCHAR(64) NOT NULL DEFAULT 'Asia/Kolkata',
  school_location geography(Point,4326),           -- drop/board point for morning/evening trips
  join_code     VARCHAR(12) NOT NULL UNIQUE,        -- parents self-register with this
  settings      JSONB NOT NULL DEFAULT '{}'::jsonb,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id      UUID REFERENCES schools(id),       -- NULL only for super_admin
  email          VARCHAR(255) NOT NULL,
  password_hash  VARCHAR(255) NOT NULL,
  full_name      VARCHAR(200) NOT NULL,
  phone          VARCHAR(20),
  role           user_role NOT NULL,
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  email_verified BOOLEAN NOT NULL DEFAULT FALSE,    -- verification flow = V2
  notification_prefs JSONB NOT NULL DEFAULT '{}'::jsonb,
  push_subscription  JSONB,                          -- V2 web-push
  last_login_at  TIMESTAMPTZ,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_users_email_lower ON users (lower(email));   -- case-insensitive unique
CREATE INDEX idx_users_school_role ON users (school_id, role);

CREATE TABLE students (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id      UUID NOT NULL REFERENCES schools(id),
  parent_id      UUID NOT NULL REFERENCES users(id),
  full_name      VARCHAR(200) NOT NULL,
  grade          VARCHAR(20),
  section        VARCHAR(20),
  pickup_address TEXT,
  pickup_location geography(Point,4326),
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_students_parent ON students (parent_id);
CREATE INDEX idx_students_pickup ON students USING GIST (pickup_location);
```

### 6.3 Fleet & routing (MVP)

```sql
CREATE TABLE vehicles (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id      UUID NOT NULL REFERENCES schools(id),
  plate_number   VARCHAR(20) NOT NULL,
  vehicle_type   vehicle_type NOT NULL DEFAULT 'bus',
  capacity       INT NOT NULL CHECK (capacity > 0),
  make           VARCHAR(60), model VARCHAR(60), year INT,
  insurance_expiry DATE,
  fitness_expiry   DATE,
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (school_id, plate_number)
);

CREATE TABLE routes (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id      UUID NOT NULL REFERENCES schools(id),
  name           VARCHAR(120) NOT NULL,
  description    TEXT,
  vehicle_id     UUID REFERENCES vehicles(id),
  driver_id      UUID REFERENCES users(id),
  route_path     geography(LineString,4326),
  schedule_type  schedule_type NOT NULL DEFAULT 'both',
  version        INT NOT NULL DEFAULT 1,            -- optimistic locking
  is_active      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE route_stops (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  route_id    UUID NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
  name        VARCHAR(120) NOT NULL,
  location    geography(Point,4326) NOT NULL,
  address     TEXT,
  stop_order  INT NOT NULL,
  arrival_time TIME,                                 -- local (school timezone)
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (route_id, stop_order)
);
CREATE INDEX idx_route_stops_location ON route_stops USING GIST (location);

CREATE TABLE student_route_assignments (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id   UUID NOT NULL REFERENCES schools(id),
  student_id  UUID NOT NULL REFERENCES students(id),
  route_id    UUID NOT NULL REFERENCES routes(id),
  stop_id     UUID NOT NULL REFERENCES route_stops(id),
  assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_active   BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE (student_id, route_id)
);
CREATE INDEX idx_sra_route ON student_route_assignments (route_id, stop_id) WHERE is_active;

CREATE TABLE transport_requests (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id        UUID NOT NULL REFERENCES schools(id),
  parent_id        UUID NOT NULL REFERENCES users(id),
  student_id       UUID NOT NULL REFERENCES students(id),
  pickup_address   TEXT,
  pickup_location  geography(Point,4326),
  status           request_status NOT NULL DEFAULT 'pending',
  assigned_route_id UUID REFERENCES routes(id),
  assigned_stop_id  UUID REFERENCES route_stops(id),
  admin_notes      TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_treq_school_status ON transport_requests (school_id, status, created_at DESC);
```

### 6.4 Trips & GPS (MVP)

```sql
CREATE TABLE trips (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id        UUID NOT NULL REFERENCES schools(id),
  route_id         UUID NOT NULL REFERENCES routes(id),
  driver_id        UUID NOT NULL REFERENCES users(id),
  vehicle_id       UUID NOT NULL REFERENCES vehicles(id),
  status           trip_status NOT NULL DEFAULT 'scheduled',
  scheduled_date   DATE NOT NULL,
  scheduled_departure_at TIMESTAMPTZ NOT NULL,        -- G1: drives no-show / ETA / absent cutoff
  slot             VARCHAR(10) NOT NULL CHECK (slot IN ('morning','evening')),  -- a 'both' route yields 2 trips/day
  current_stop_order INT,                              -- progress pointer for ETA + bus_approaching
  started_at       TIMESTAMPTZ,
  ended_at         TIMESTAMPTZ,
  safeguarding_checked BOOLEAN NOT NULL DEFAULT FALSE,
  original_driver_id   UUID REFERENCES users(id),      -- substitute flow (V2)
  reassigned_at        TIMESTAMPTZ,
  reassignment_reason  VARCHAR(120),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_trips_status_date ON trips (status, scheduled_date);
CREATE INDEX idx_trips_route_date  ON trips (route_id, scheduled_date);
CREATE INDEX idx_trips_school_active ON trips (school_id, status) WHERE status IN ('scheduled','in_progress','pending_safeguard_check');
CREATE UNIQUE INDEX idx_trips_route_date_slot ON trips (route_id, scheduled_date, slot);  -- 'both' route ⇒ 2 trips/day

CREATE TABLE gps_logs (
  id          BIGSERIAL,
  trip_id     UUID NOT NULL,
  location    geography(Point,4326) NOT NULL,
  speed       REAL, heading REAL, accuracy REAL,
  recorded_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (id, recorded_at)
) PARTITION BY RANGE (recorded_at);
-- Monthly partitions created ahead by APScheduler; cleanup drops partitions > GPS_RETENTION_DAYS.
CREATE INDEX idx_gps_trip_time ON gps_logs (trip_id, recorded_at DESC);
CREATE INDEX idx_gps_location  ON gps_logs USING GIST (location);
```

### 6.5 Safety (MVP)

```sql
CREATE TABLE attendance_records (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id     UUID NOT NULL REFERENCES schools(id),
  trip_id       UUID NOT NULL REFERENCES trips(id),
  student_id    UUID NOT NULL REFERENCES students(id),
  stop_id       UUID REFERENCES route_stops(id),       -- board stop (nullable for school-board evening)
  status        attendance_status NOT NULL,
  marked_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  marked_by     UUID REFERENCES users(id),             -- driver, or parent for absent_parent_marked
  marked_location geography(Point,4326),
  drop_type     drop_type,                             -- 'stop' | 'school' (null until dropped)
  drop_stop_id  UUID REFERENCES route_stops(id),       -- set when drop_type='stop'
  dropped_at    TIMESTAMPTZ,                            -- non-null = dropped/accounted
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (trip_id, student_id)
);
CREATE INDEX idx_att_trip_stop ON attendance_records (trip_id, stop_id);
CREATE INDEX idx_att_school_trip ON attendance_records (school_id, trip_id);
CREATE INDEX idx_att_student ON attendance_records (student_id, created_at DESC);
-- "on bus now": status='boarded' AND dropped_at IS NULL

CREATE TABLE alerts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id       UUID NOT NULL REFERENCES schools(id),
  trip_id         UUID REFERENCES trips(id),
  type            alert_type NOT NULL,
  severity        alert_severity NOT NULL,
  title           VARCHAR(200) NOT NULL,
  description     TEXT,
  triggered_by    UUID REFERENCES users(id),
  acknowledged_by UUID REFERENCES users(id),
  acknowledged_at TIMESTAMPTZ,
  resolved_at     TIMESTAMPTZ,
  location        geography(Point,4326),
  metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,   -- e.g. {student_id, stop_id}
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_alerts_school_sev ON alerts (school_id, severity, created_at DESC);
CREATE INDEX idx_alerts_trip_unresolved ON alerts (trip_id) WHERE resolved_at IS NULL;
```

### 6.6 Notifications, auth tokens, audit (MVP)

```sql
CREATE TABLE notifications (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id   UUID NOT NULL REFERENCES schools(id),
  user_id     UUID NOT NULL REFERENCES users(id),
  type        notification_type NOT NULL,
  title       VARCHAR(200) NOT NULL,
  body        TEXT,
  data        JSONB NOT NULL DEFAULT '{}'::jsonb,    -- {trip_id, student_id, ...}
  is_read     BOOLEAN NOT NULL DEFAULT FALSE,
  read_at     TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notif_user ON notifications (user_id, is_read, created_at DESC);

CREATE TABLE refresh_tokens (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES users(id),
  token_hash VARCHAR(255) NOT NULL,
  device_id  VARCHAR(120),
  family_id  UUID NOT NULL,
  issued_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_rt_hash ON refresh_tokens (token_hash);
CREATE INDEX idx_rt_user ON refresh_tokens (user_id, revoked_at);
CREATE INDEX idx_rt_family ON refresh_tokens (family_id);

CREATE TABLE auth_tokens (             -- password reset (MVP), email verification (V2)
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES users(id),
  token_hash VARCHAR(255) NOT NULL,
  type       auth_token_type NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at    TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_authtok_hash ON auth_tokens (token_hash);

CREATE TABLE audit_logs (
  id          BIGSERIAL PRIMARY KEY,
  school_id   UUID REFERENCES schools(id),
  user_id     UUID REFERENCES users(id),
  action      VARCHAR(80) NOT NULL,        -- e.g. 'driver_phone_viewed','vehicle.update'
  entity_type VARCHAR(40),
  entity_id   UUID,
  old_values  JSONB,
  new_values  JSONB,
  ip_address  INET,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_school_time ON audit_logs (school_id, created_at DESC);
CREATE INDEX idx_audit_entity ON audit_logs (entity_type, entity_id);
```

### 6.7 V2 tables (create in the V2 migration)

```sql
CREATE TABLE broadcasts (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id  UUID NOT NULL REFERENCES schools(id),
  sender_id  UUID NOT NULL REFERENCES users(id),
  route_id   UUID REFERENCES routes(id),    -- NULL = school-wide
  title      VARCHAR(200) NOT NULL,
  body       TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_broadcast_school ON broadcasts (school_id, created_at DESC);

CREATE TABLE trip_feedback (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id     UUID NOT NULL REFERENCES schools(id),
  trip_id       UUID NOT NULL REFERENCES trips(id),
  parent_id     UUID NOT NULL REFERENCES users(id),
  driver_id     UUID NOT NULL REFERENCES users(id),
  rating        SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment       TEXT,
  is_flagged    BOOLEAN NOT NULL DEFAULT FALSE,   -- auto if rating<=2
  admin_reviewed BOOLEAN NOT NULL DEFAULT FALSE,
  admin_notes   TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (trip_id, parent_id)
);
CREATE INDEX idx_feedback_driver ON trip_feedback (driver_id, created_at DESC);
CREATE INDEX idx_feedback_flag ON trip_feedback (school_id, is_flagged, admin_reviewed);

CREATE TABLE complaints (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id     UUID NOT NULL REFERENCES schools(id),
  submitted_by  UUID NOT NULL REFERENCES users(id),
  against_type  complaint_against NOT NULL,
  against_id    UUID,
  trip_id       UUID REFERENCES trips(id),
  subject       VARCHAR(200) NOT NULL,
  description   TEXT NOT NULL,
  status        complaint_status NOT NULL DEFAULT 'open',
  priority      priority NOT NULL DEFAULT 'medium',
  assigned_to   UUID REFERENCES users(id),
  resolution_notes TEXT,
  resolved_at   TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_complaint_school ON complaints (school_id, status, created_at DESC);

CREATE TABLE reports (             -- request log; file is STREAMED on download, not stored
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id    UUID NOT NULL REFERENCES schools(id),
  generated_by UUID NOT NULL REFERENCES users(id),
  type         report_type NOT NULL,
  format       report_format NOT NULL,
  date_from    DATE NOT NULL, date_to DATE NOT NULL,
  route_ids    UUID[],
  status       report_status NOT NULL DEFAULT 'completed',  -- synchronous in MVP-V2 scale
  error_message TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Payments (V2 structure; gateway = Future)
CREATE TABLE fee_schedules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id),
  route_id UUID REFERENCES routes(id),
  name VARCHAR(120) NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  currency CHAR(3) NOT NULL DEFAULT 'INR',
  billing_cycle billing_cycle NOT NULL,
  effective_from DATE NOT NULL, effective_to DATE,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE invoices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id),
  parent_id UUID NOT NULL REFERENCES users(id),
  student_id UUID NOT NULL REFERENCES students(id),
  fee_schedule_id UUID REFERENCES fee_schedules(id),
  amount NUMERIC(10,2) NOT NULL,
  status invoice_status NOT NULL DEFAULT 'draft',
  due_date DATE, paid_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_invoice_parent ON invoices (parent_id, status);
CREATE TABLE payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  school_id UUID NOT NULL REFERENCES schools(id),
  invoice_id UUID NOT NULL REFERENCES invoices(id),
  amount NUMERIC(10,2) NOT NULL,
  currency CHAR(3) NOT NULL DEFAULT 'INR',
  gateway payment_gateway NOT NULL,
  gateway_payment_id VARCHAR(120),
  gateway_order_id VARCHAR(120),
  status payment_status NOT NULL DEFAULT 'pending',
  receipt_no VARCHAR(40),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 6.8 Multi-tenancy strategy
- **MVP:** every query filters by `school_id` derived from the JWT claim, injected by a dependency (`get_school_scope`). A shared SQLAlchemy query helper enforces it; reviewers check every new query.
- **V2:** enable RLS as defense-in-depth:
  ```sql
  ALTER TABLE vehicles ENABLE ROW LEVEL SECURITY;
  CREATE POLICY school_isolation ON vehicles
    USING (school_id = current_setting('app.current_school_id')::uuid
           OR current_setting('app.is_super_admin', true) = 'true');
  ```
  Middleware runs `SET LOCAL app.current_school_id = :sid` (and `app.is_super_admin`) per request/transaction.

### 6.9 Retention (enforced by APScheduler jobs / partition drops)
| Data | Retention | Mechanism |
|---|---|---|
| `gps_logs` | 90 days | drop monthly partitions older than 90d |
| App logs | 30 days | logrotate (VPS) / platform (Railway) |
| `attendance_records` | 1 year | periodic delete job (V2) |
| `audit_logs` | 7 years | retained; archival policy (Future) |
| `payments`/`invoices` | 7 years | retained (financial/compliance) |

---

## 7. Authentication & Authorization

### 7.1 Tokens
- **Access token (JWT):** 15-min TTL. Claims: `sub` (user_id), `school_id` (nullable for super_admin), `role`, `exp`, `iat`, `jti`. Sent as `Authorization: Bearer`.
- **Refresh token:** opaque random (32 bytes), stored **hashed** in `refresh_tokens`. Delivered as `HttpOnly; Secure; SameSite=Strict` cookie (path `/api/v1/auth`). **Never localStorage.** 30-day TTL.
- **Rotation + theft detection:** each `/refresh` issues a new refresh token in the same `family_id` and revokes the previous. Re-use of an already-revoked token ⇒ revoke the **entire family** (forces re-login on all devices) + audit log.

### 7.2 Registration flows
| Who | How |
|---|---|
| **Parent** | `POST /auth/register` with `{join_code, email, password, full_name, phone}`. Server validates `join_code` → creates `parent` scoped to that school, `is_active=true`, `email_verified=false`. |
| **Driver** | Created by admin: `POST /drivers` (creates a `users` row, role=driver, temp password emailed via Resend or shown once). |
| **School admin** | Created by super_admin (V2) or by bootstrap seed (MVP). |
| **Super admin** | Seed/CLI only. |

### 7.3 Password reset (MVP)
1. `POST /auth/forgot-password {email}` → always returns 200 (no enumeration). If user exists, create `auth_tokens(type=password_reset)`, email a one-time link (`https://app.../reset?token=…`), 1-hr expiry.
2. `POST /auth/reset-password {token, new_password}` → validate hash+expiry+unused, set new `password_hash`, mark `used_at`, **revoke all refresh-token families** for that user.

### 7.4 Account lockout
Redis `login_attempts:{lower(email)}` increments on failed login; at `ACCOUNT_LOCKOUT_THRESHOLD` (5) set TTL `ACCOUNT_LOCKOUT_TTL_MIN` (15) and reject with generic message. Reset on success.

### 7.5 RBAC matrix (representative)
| Resource / action | parent | driver | school_admin | super_admin |
|---|---|---|---|---|
| Own profile R/W | ✅ | ✅ | ✅ | ✅ |
| Schools CRUD | — | — | own (R/settings) | ✅ all |
| Vehicles / routes / stops CRUD | — | read assigned | ✅ | ✅ |
| Drivers manage | — | — | ✅ | ✅ |
| Students (own children) | ✅ | — | ✅ all | ✅ |
| Transport request submit | ✅ | — | review/assign | ✅ |
| Trip start/end/attendance | — | ✅ (own trips) | — | — |
| Trip generate / cancel / reassign | — | — | ✅ | ✅ |
| Track trip (join room) | ✅ (own child) | ✅ (own trip) | ✅ | ✅ |
| Alerts ack/resolve | — | — | ✅ | ✅ |
| Mark child absent | ✅ (own child) | — | — | — |

Enforcement: FastAPI dependency `require_role(*roles)` + per-object `school_id`/ownership checks in services. **Never trust the frontend.**

---

## 8. API Reference

Base path `/api/v1`. All responses JSON. Auth via `Authorization: Bearer <access>` unless noted. Standard error envelope:
```json
{ "error": { "code": "string_code", "message": "human readable", "details": {} } }
```
Common codes: `unauthorized` (401), `forbidden` (403), `not_found` (404), `validation_error` (422), `conflict` (409), `rate_limited` (429), `locked` (423). Lists are paginated: `?limit=50&offset=0` → `{ "items": [...], "total": int, "limit": int, "offset": int }`.

### 8.1 Auth — `/auth`
| Method | Path | Auth | Body / Notes |
|---|---|---|---|
| POST | `/register` | public | `{join_code,email,password,full_name,phone}` → parent. 409 if email exists, 422 if bad join_code. |
| POST | `/login` | public | `{email,password}` → `{access_token, user:{...}}` + Set-Cookie refresh. 423 if locked. |
| POST | `/refresh` | cookie | rotates refresh, returns new `{access_token}`. Reuse ⇒ family revoke. |
| POST | `/logout` | bearer | revokes current refresh family; clears cookie. |
| POST | `/forgot-password` | public | `{email}` → 200 always. |
| POST | `/reset-password` | public | `{token,new_password}`. |
| GET | `/me` | bearer | current user profile. |
| PUT | `/me` | bearer | `{full_name?,phone?,notification_prefs?}`. |

**`POST /login` 200:**
```json
{ "access_token":"<jwt>",
  "user":{"id":"uuid","email":"a@b.com","full_name":"...","role":"parent","school_id":"uuid"} }
```

### 8.2 Schools — `/schools`
| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/` | super_admin (V2) | create school + join_code |
| GET | `/` | super_admin (V2) | list |
| GET | `/{id}` | admin(own)/super | details |
| PUT | `/{id}` | admin(own)/super | profile, `school_location`, `logo_url` |
| PUT | `/{id}/settings` | admin(own)/super | merge `settings` JSONB |
| POST | `/{id}/regenerate-join-code` | admin(own)/super | rotate `join_code` |

### 8.3 Vehicles — `/vehicles`
CRUD (`POST` `GET` `GET /{id}` `PUT /{id}` `DELETE /{id}`=soft). Validation: `plate_number` unique per school, `capacity>0`. `DELETE` blocked (409) if vehicle has an active/scheduled trip.

### 8.4 Drivers — `/drivers`
| Method | Path | Notes |
|---|---|---|
| POST | `/` | admin creates driver user (role=driver) |
| GET | `/` | list (school-scoped) |
| GET | `/{id}` | detail |
| PUT | `/{id}` | update |
| POST | `/{id}/assign` | `{vehicle_id}` assign default vehicle (audit-logged) |
| GET | `/{id}/schedule` | upcoming trips |
| GET | `/{id}/trips` | trip history |

### 8.5 Routes & stops — `/routes`
```
POST   /routes                         {name,description,schedule_type,vehicle_id?,driver_id?}
GET    /routes                         list
GET    /routes/{id}                    route + ordered stops
PUT    /routes/{id}                    {..., version}   # optimistic lock → 409 on stale version
DELETE /routes/{id}                    soft delete
POST   /routes/{id}/stops              {name,location:{lat,lng},address,arrival_time}
PUT    /routes/{id}/stops/{stop_id}
DELETE /routes/{id}/stops/{stop_id}
PUT    /routes/{id}/stops/reorder      {ordered_stop_ids:[...]}
GET    /routes/{id}/students           assigned students (+ stop)
POST   /routes/{id}/students           {student_id, stop_id}  # capacity-checked vs vehicle.capacity → 409
```
`route_path` is auto-built (LineString from ordered stops) or accepted explicitly. Stop coordinates entered via map click or geocoded address.

### 8.6 Transport requests — `/transport-requests`
```
POST /transport-requests        {student_id, pickup_address, pickup_location:{lat,lng}}  # parent
GET  /transport-requests        admin: all (filter status); parent: own
GET  /transport-requests/{id}
PUT  /transport-requests/{id}   admin: {status:'approved'|'rejected'|'assigned', assigned_route_id?, assigned_stop_id?, admin_notes?}
GET  /transport-requests/suggest-stop?lat=&lng=        # top-3 nearest stops
```
**suggest-stop 200:** geocode (if address) → `ST_Distance` vs `route_stops` →
```json
{ "suggestions":[ {"stop_id":"uuid","route_id":"uuid","name":"Sector 12 Gate","distance_m":180,"arrival_time":"07:25"}, ... ] }
```
On `status='assigned'`, server creates the `student_route_assignments` row (capacity-checked).

### 8.7 Trips & GPS — `/trips`
```
POST   /trips                      admin: {route_id, scheduled_date, slot}  # manual create
POST   /trips/generate             admin: {scheduled_date}  # generate for all active routes (idempotent)
GET    /trips                      filter: ?date=&route_id=&status=
GET    /trips/{id}                 detail (+ driver.phone conditionally — see §10.5)
PUT    /trips/{id}/start           driver: status→in_progress, started_at=now
PUT    /trips/{id}/end             driver: safeguarding gate → completed | pending_safeguard_check (§10.2)
PUT    /trips/{id}/cancel          admin: status→cancelled (+ notify parents)
PUT    /trips/{id}/reassign        admin (V2): {driver_id, vehicle_id?, reason}
GET    /trips/{id}/gps-log         historical trace (GeoJSON LineString)
GET    /trips/active               admin: all active trips for dashboard map
```
**`GET /trips/{id}` 200 (parent, active, phone enabled):**
```json
{ "id":"uuid","status":"in_progress","route":{"id":"uuid","name":"Route A"},
  "vehicle":{"plate_number":"DL1PC1234"},
  "driver":{"name":"Ramesh Kumar","phone":"+919876543210"},   // null unless §10.5 conditions met
  "current_stop_order":3,"started_at":"2026-05-30T07:10:00Z",
  "scheduled_departure_at":"2026-05-30T07:00:00Z" }
```

### 8.8 Attendance & drop-off — `/trips/{trip_id}/...`  (driver)
```
POST /trips/{trip_id}/stops/{stop_id}/attendance
  Body:    { "attendance":[ {"student_id":"uuid","status":"boarded"}, {"student_id":"uuid","status":"absent"} ] }
  Effect:  UPSERT on (trip_id,student_id); this submission = "stop complete" → not-boarded detection (§10.1).
  200:     { "processed": 5, "alerts_triggered": 1 }

GET  /trips/{trip_id}/attendance                       full roster + status
GET  /trips/{trip_id}/stops/{stop_id}/attendance       per-stop

POST /trips/{trip_id}/drop
  Body:    { "student_ids":["uuid",...], "drop_type":"school" }            # morning: all at school, ONE tap
           or { "student_ids":["uuid"], "drop_type":"stop", "stop_id":"uuid" }  # evening: at a stop
  Effect:  set dropped_at=now, drop_type, drop_stop_id; auto-resolve matching child_not_dropped alerts (§10.2)
  200:     { "dropped": 12 }
```

### 8.9 Parent absent-marking — `/trips/{trip_id}/absent`
```
POST   /trips/{trip_id}/absent/{student_id}    parent: create attendance(status=absent_parent_marked). Allowed only if trip.status='scheduled'. → emits child_absent_marked to driver.
DELETE /trips/{trip_id}/absent/{student_id}    parent: cancel, only if trip not in_progress.
GET    /trips/{trip_id}/absences               driver: list of pre-marked absences.
```

### 8.10 Alerts — `/alerts`
```
GET  /alerts                 admin: filter ?type=&severity=&resolved=
PUT  /alerts/{id}/acknowledge admin
PUT  /alerts/{id}/resolve     admin → if last unresolved child_not_dropped for a trip, atomic trip completion (§10.2)
```

### 8.11 Notifications — `/notifications`
```
GET  /notifications           paginated, ?unread=true
PUT  /notifications/{id}/read
PUT  /notifications/read-all
PUT  /notifications/preferences  {prefs JSONB}
POST /notifications/subscribe    (V2 web-push VAPID)
DELETE /notifications/subscribe  (V2)
```

### 8.12 Parent dashboard — `/parents/dashboard` (V2 aggregation; works MVP for 1 child)
```json
{ "children":[ { "student":{"id","name","grade"},
                 "route":{"id","name"}, "stop":{"id","name","arrival_time"},
                 "active_trip":{ "id","status","driver":{"name","phone"},
                                 "current_location":{"lat","lng","updated_at"},
                                 "eta_to_stop_seconds":420 } ,
                 "today_attendance":{"status","marked_at"}, "absent_marked":false } ] }
```

### 8.13 V2 endpoints (summary; contracts mirror the patterns above)
```
# Broadcasts
POST /broadcasts {route_id?, title, body}        GET /broadcasts
# Feedback
POST /trips/{id}/feedback {rating,comment?}       GET /drivers/{id}/feedback (admin, full)
GET  /feedback?flagged=true                       PUT /feedback/{id}/review {admin_notes}
GET  /drivers/me/rating  (driver: aggregate only)
# Complaints
POST /complaints {against_type,against_id?,trip_id?,subject,description}
GET  /complaints   GET /complaints/{id}   PUT /complaints/{id}/assign   PUT /complaints/{id}/resolve {notes}   PUT /complaints/{id}/status {status}
# Reports (streamed download; generated synchronously at MVP/V2 scale)
POST /reports/generate {type,format,date_from,date_to,route_ids?} → 200 streams file (Content-Disposition)
GET  /reports   (request history)
# Analytics
GET  /analytics/dashboard | /routes | /attendance | /trips | /driver-ratings
# Payments (V2 structure; gateway Future)
GET/POST /fee-schedules   GET/POST /invoices   POST /invoices/bulk-generate
POST /payments/record (manual/offline)   [Future] /payments/initiate|verify|webhook|{id}/receipt
```

### 8.14 Health — `/health` (public)
```json
{ "status":"ok", "db":"connected", "redis":"connected", "last_gps_event_at":"2026-05-30T07:11:02Z" }
```
Returns 503 if DB unreachable. `redis:"degraded"` does not fail health (see §17.3 degradation).

---

## 9. Real-Time (Socket.IO) & Client UX Rules

### 9.1 Connection & auth
- Client connects with `?token=<access_jwt>` query param (header unsupported by some proxies).
- Server validates JWT on `connect`; invalid/expired ⇒ `raise ConnectionRefusedError('unauthorized')`.
- On access-token expiry mid-connection, server emits `token_expired`; client refreshes then reconnects.
- **MVP:** single instance, in-memory Socket.IO. **V2:** `socketio.AsyncRedisManager` for horizontal scale.

### 9.2 Rooms
- `trip:{trip_id}` — parents of assigned children + the driver + admins.
- `school:{school_id}` — admins (alerts) and school-wide broadcasts (V2).
- `join_trip` authorization: requester's child is assigned to the trip's route **OR** is the trip's driver **OR** is a school admin of that school. Else reject.

### 9.3 Events
**Client → Server**
| Event | Payload | Auth check |
|---|---|---|
| `join_trip` | `{trip_id}` | room auth (§9.2) |
| `leave_trip` | `{trip_id}` | — |
| `location_update` | `{trip_id,lat,lng,speed,heading,accuracy,ts}` | must be trip's driver; rate ≤1/3s |
| `location_batch` | `{trip_id,points:[...]}` | driver; offline backfill (V2), not re-broadcast |

**Server → Client**
| Event | Payload | Audience |
|---|---|---|
| `location_update` | `{trip_id,lat,lng,speed,heading,ts,eta_next_stop_s}` | trip room |
| `bus_approaching` | `{trip_id,stop_id,distance_m,eta_s}` | parents at that stop |
| `trip_started` / `trip_ended` | `{trip_id,...}` | trip room |
| `tracking_paused` | `{trip_id,last_lat,last_lng,last_updated_at}` | trip room |
| `attendance_update` | `{trip_id,student_id,student_name,status,stop_name}` | that child's parent |
| `child_not_boarded` | `{trip_id,student_id,student_name,stop_name}` | parent + `school:{id}` |
| `child_not_dropped` | `{trip_id,student_id,student_name,severity:"critical"}` | `school:{id}` |
| `child_absent_marked` | `{trip_id,student_id,student_name}` | driver |
| `route_deviation` (V2) | `{trip_id,distance_from_route_m}` | `school:{id}` |
| `alert_new` | `{alert}` | `school:{id}` |
| `broadcast` (V2) | `{broadcast_id,title,body,route_id,sender_name,created_at}` | route/school room |
| `trip_reassigned` (V2) | `{trip_id,new_driver_name,vehicle_plate}` | new driver + parents |
| `notification` | `{notification}` | the user |

### 9.4 Rate limiting (Redis sliding window)
`ratelimit:auth:{ip}` 5/min · `ratelimit:api:{user}` 100/min · `ratelimit:loc:{sid}` 1/3s (drop excess silently). On Redis outage, limiting is skipped (logged), not fatal.

### 9.5 Client UX rules (simplicity is a requirement, not a nicety)
- **Driver screen:** one primary action visible at a time. Big touch targets (≥56px). "Start Trip" → per-stop roster with large Boarded/Absent toggles → "**Drop all at school**" single button (morning) → "End Trip". "Keep screen on" banner (MVP). Absent-marked students shown greyed with "Parent: won't ride".
- **Parent screen:** live map is the home screen during a trip; ETA + last-updated timestamp always visible; "Tracking paused" banner when GPS stale >30s; driver-call button only when permitted (§10.5); "Mark absent today" on the upcoming-trip card.
- **Admin:** setup wizard (school → vehicle → route+stops → done); live fleet map with status colors; alerts panel with CRITICAL pinned to top + sound.
- **Global:** optimistic UI with rollback on error; skeleton loaders; offline/disconnected banner; all copy via i18n keys (English values in MVP).

---

## 10. Safety System (`app/tracking/safety.py`) — MVP, P0

This is the product's core differentiator. All four behaviors interconnect so no false alerts fire.

### 10.1 Child not-boarded
- **Trigger:** `POST /trips/{id}/stops/{stop_id}/attendance` (the batch submit = explicit "stop complete").
- **Logic:** query `student_route_assignments WHERE route_id = trip.route_id AND stop_id = :stop_id AND is_active`. For each assigned student **not** in the submitted list **and not** already `absent_parent_marked`:
  - create `alerts(type=child_not_boarded, severity=high, metadata={student_id,stop_id})`
  - emit `child_not_boarded` to the parent + `school:{id}`
  - create `notifications` rows (parent + admins)
- Parent-marked-absent students are silently skipped (logged as expected absence).

### 10.2 Child not-dropped (safeguarding gate)
- **Trigger:** `PUT /trips/{id}/end`.
- **Logic:** `SELECT student_id FROM attendance_records WHERE trip_id=:id AND status='boarded' AND dropped_at IS NULL`.
  - **None unaccounted** → atomic transition to `completed`, `safeguarding_checked=true`, emit `trip_ended`.
  - **Any unaccounted** → per student create `alerts(type=child_not_dropped, severity=critical)`; emit `child_not_dropped` to `school:{id}`; set `trip.status='pending_safeguard_check'`; respond `200 {status:"pending_safeguard_check", unresolved_students:[...]}`.
- **Resolution (two paths, one atomic guard):**
  - **Driver path:** `POST /trips/{id}/drop` marks the missed student dropped → auto-resolves that student's alert.
  - **Admin path:** `PUT /alerts/{id}/resolve`.
  - After either, if no unresolved `child_not_dropped` alerts remain for the trip, run:
    ```sql
    UPDATE trips SET status='completed', safeguarding_checked=true
    WHERE id=:trip_id AND status='pending_safeguard_check';   -- rows_affected guards double-fire
    ```
    Emit `trip_ended` only if `rows_affected > 0` (idempotent; concurrent caller updates 0 rows, emits nothing).

### 10.3 Parent absent-marking
- `POST /trips/{id}/absent/{student_id}` before `in_progress` → `attendance(status=absent_parent_marked, marked_by=parent)`; emit `child_absent_marked` to driver. Driver UI greys the student; if a stop has no remaining boarders, suggest "Skip this stop?". Cancellable until `in_progress`.

### 10.4 Morning vs evening drop semantics
| schedule slot | board | drop | "drop all" action |
|---|---|---|---|
| morning | at each `route_stop` (`stop_id` set) | at school (`drop_type='school'`) | one tap at school |
| evening | at school (`stop_id` NULL, board recorded at start) | at each student's stop (`drop_type='stop'`, `drop_stop_id`) | per-stop drop |

Not-dropped detection is identical for both: any `boarded` row with `dropped_at IS NULL` at trip end is unaccounted.

### 10.5 Driver phone disclosure (privacy-controlled)
`driver.phone` is returned by `GET /trips/{id}` and `/parents/dashboard` **only if** requester is the child's parent **AND** `trip.status='in_progress'` **AND** `school.settings.driver_phone_visible=true`. Every disclosure writes `audit_logs(action='driver_phone_viewed')`. UI masks to `98765 ***10`; full number only in the `tel:` href. Otherwise `phone:null` and no card shown.

---

## 11. Background Jobs (APScheduler, in-process — MVP)

Registered on app startup (`AsyncIOScheduler`), timezone `Asia/Kolkata`. All jobs emit structured logs (`task_name, duration_ms, status, school_id`) and are **idempotent**.

| Job | Schedule | Logic |
|---|---|---|
| `flush_gps_buffer` | every 30s (asyncio, not APScheduler) | drain `gps:buffer:{trip_id}` lists → batch INSERT into `gps_logs`. Flush on shutdown. |
| `generate_daily_trips` | 06:00 IST daily | for each active route with `trip_autogen_enabled`, create today's trip(s) per slot (idempotent via `UNIQUE(route_id,date,slot)`); set `scheduled_departure_at` from first stop. |
| `check_driver_no_show` | every 5 min, 06:00–18:00 IST | trips `status='scheduled' AND scheduled_departure_at + 15min < now()` → `alerts(type=driver_no_show, severity=high)` + notify admins (once per trip). |
| `check_vehicle_compliance` | 07:00 IST daily | insurance/fitness expiry at 30/7/1 days → `alerts(type=insurance_expiry)`; on/after expiry → `vehicles.is_active=false` + alert. |
| `ensure_gps_partitions` | 00:30 IST daily | create next-month `gps_logs` partition if missing. |
| `cleanup_gps_logs` | 01:00 IST daily | drop `gps_logs` partitions older than `GPS_RETENTION_DAYS` (90). |
| `auto_resolve_sos` (V2) | every 5 min | SOS unacknowledged >30 min auto-resolve (configurable). |

> **Single-instance assumption:** APScheduler runs in the one always-on web process. When V2 scales horizontally, move scheduled jobs to Celery beat (single beat) or add a Redis lock so only one instance fires each job.

---

## 12. Notifications & Broadcasts

### 12.1 In-app notifications (MVP)
Every safety/trip event writes a `notifications` row **and** emits a `notification` Socket.IO event to the user if connected. The bell icon shows unread count; `/notifications` lists; mark-read endpoints update. Categories per `notification_type` enum.

### 12.2 Channels roadmap
| Channel | Phase | Mechanism |
|---|---|---|
| In-app (Socket.IO + persisted) | MVP | as above |
| Web push | V2 | Service Worker + VAPID + `pywebpush`; `users.push_subscription` |
| Email notifications | V2 | Resend; per-user `notification_prefs` |
| SMS | Future | MSG91 (India) for critical alerts |

> Transactional email (password reset) is MVP via Resend and is **separate** from the V2 "email notifications" channel.

### 12.3 Broadcasts (V2)
Admin one-way announcements; `broadcasts` table; `POST /broadcasts {route_id?,title,body}`. Delivery: emit `broadcast` to `route:{id}` room or `school:{id}`; also write `notifications` rows for persistence. No replies (use complaints/phone).

---

## 13. Frontend (Single React SPA, role-based)

### 13.1 Structure
One Vite + React 19 app, role-based routing/layouts (parent / driver / admin); super_admin console is V2. Tailwind 4 + shadcn/ui; Zustand for live state; react-leaflet maps; `socket.io-client`; `ky` HTTP; `react-i18next` (English values only in MVP, all strings keyed).

```
web/src/
  main.tsx, App.tsx (role router)
  lib/ (api client, socket, auth store, i18n)
  components/ (ui/, Map, BusMarker, AlertBadge, ...)
  features/
    auth/        (login, register-with-join-code, forgot/reset)
    parent/      (dashboard, track-map, child-detail, mark-absent)
    driver/      (today-route, trip-run, attendance, drop-off)
    admin/       (setup-wizard, vehicles, routes+stops editor, requests, fleet-map, alerts, settings)
  locales/en/*.json
```

### 13.2 Screens by role (MVP)
**Auth:** Login · Register (join code → email/password) · Forgot/Reset password.

**Parent:** Dashboard (child card: route, stop, today status) · **Live Track** (Leaflet map, moving bus, ETA, last-updated, "Tracking paused" banner, driver-call button when permitted) · Request Transport (address → map pin → nearest-stop suggestions → submit) · Mark Absent (toggle on upcoming trip) · Notifications.

**Driver:** Today's Route (ordered stops, student counts, pre-marked absences) · **Run Trip** (Start → per-stop big Boarded/Absent toggles → submit stop → "Drop all at school" → End) · "Keep screen on" banner.

**Admin:** **Setup Wizard** · Vehicles CRUD · Routes + Stops map editor (click to add stop, drag to reorder, geocode address) · Transport Requests (map overlay, approve/assign with capacity guard) · **Fleet Map** (all active trips, status colors, click bus → driver/route/speed/passengers) · Alerts panel (CRITICAL pinned + sound) · School Settings (driver-phone toggle, autogen toggle, join code).

### 13.3 V2 frontend
PWA (installable, offline shell) + web-push opt-in · multi-child dashboard (card per child, N trip rooms) · broadcasts viewer · complaints form · feedback prompt after trip · analytics charts (Recharts) · payments (invoices, mark paid) · driver app via Capacitor (Android) reusing the driver feature module with `@capacitor/geolocation`.

### 13.4 Map/tile config
Dev: OSM tiles + Nominatim. Prod: Stadia tiles (`STADIA_API_KEY`) + MapTiler geocoding. Provider URL chosen by `APP_ENV`.

---

## 14. Landing Page (`landing/`, static, Cloudflare Pages)

Separate React + Vite + Tailwind static build (no backend). Design tokens & sections are fixed:

**Palette:** Primary indigo `#4f46e5` · bg `#ffffff`/`#fafafa` · accent `#eef2ff` · WhatsApp `#25d366` · headings `#1e1b4b` · body `#6b7280` · border `#e5e7eb` · 3px indigo top stripe · radial indigo hero glow `rgba(99,102,241,0.07)`. **Indian identity via copy only** (Hinglish + "Made for Indian Schools" badge) — no saffron/warm colors.

**Sections:** (1) Sticky nav: logo · Features · Pricing · Contact · `Contact Us` (outline) + `💬 WhatsApp` (green). (2) Hero: 🇮🇳 badge · `बच्चों का सफर, Safe & Tracked.` · Hinglish subtitle · `💬 WhatsApp Us` + `✉️ Contact Us` · 4 trust badges. (3) Dashboard preview: CSS map mockup, pulsing bus marker, route line, stop dots, LIVE badge + 3 stat cards. (4) Features grid (6): GPS Tracking · Safety Alerts · Attendance · Fleet Management · No App Needed · Multi-School. (5) How it works (3 steps): School Setup → Parents Join → Track Live. (6) Built for everyone (3 cards): Admin · Parents · Driver. (7) Pricing: Hinglish + WhatsApp/Contact + "No spam · No sales pressure". (8) Footer: logo · Made with ❤️ in India · © 2026 YatraTrack.

**CTAs:** WhatsApp `https://wa.me/91XXXXXXXXXX?text=Hi, I'm interested in YatraTrack for my school` · Contact `mailto:hello@yatratrack.in`. **Replace placeholders `[LAUNCH-BLOCKING]`.** **Not included:** waitlist, city chips, book-a-demo, free-trial, trial badge.

---

## 15. Reports, Analytics & Compliance (V2)

### 15.1 Reports (streamed, no storage)
`POST /reports/generate {type,format,date_from,date_to,route_ids?}` generates the file **in-process** with `reportlab` (PDF) / `openpyxl` (xlsx) and **streams it back** (`Content-Disposition: attachment`). A `reports` row records the request for history. No object storage, no async queue at MVP/V2 data volumes; if a school ever exceeds in-request generation time, move this single job to Celery (the only thing that would reintroduce Celery).

### 15.2 Default compliance template `[LAUNCH-BLOCKING confirm fields]`
- **Trip summary:** total / completed / cancelled / on-time %.
- **Attendance:** per-route attendance %, absentee patterns.
- **Incidents:** alerts list (type, severity, timestamps, resolution).
- **Driver performance:** trips/driver, rating avg (if feedback enabled).
- **Vehicle compliance:** insurance/fitness status per vehicle.
> Confirm mandatory fields/format with a real transport authority before first compliance export.

### 15.3 Analytics endpoints
`/analytics/dashboard` (fleet, active trips, pending requests, today's incidents, on-time %) · `/routes` · `/attendance` · `/trips` · `/driver-ratings`. Charts via Recharts. All school-scoped.

---

## 16. Payments (V2 structure, Future gateway)

### 16.1 Day-1 abstraction
`app/payments/gateways/base.py`:
```python
class PaymentGateway(ABC):
    async def create_order(self, amount: Decimal, currency: str, metadata: dict) -> OrderResult: ...
    async def verify_payment(self, gateway_payment_id, gateway_order_id, signature) -> VerifyResult: ...
    async def process_webhook(self, payload: bytes, headers: dict) -> WebhookResult: ...
    async def initiate_refund(self, gateway_payment_id, amount: Decimal) -> RefundResult: ...
```
Implementations: `razorpay.py` (primary), `stripe.py` (fallback) — **Future**.

### 16.2 Flows
- **V2 (manual):** admin creates fee schedule → invoices generated → parent pays offline → admin records payment (`gateway='offline'`) → receipt number issued.
- **Future (gateway):** parent "Pay Now" → `create_order` → hosted checkout → webhook + `verify_payment` → invoice `paid` → receipt → notify.

### 16.3 Financial safety
Amounts `NUMERIC(10,2)` (never float) · currency stored per record · idempotency keys on payment ops · mandatory webhook signature verification · every status change audit-logged · no card data stored locally (hosted checkout).

---

## 17. Security & Guardrails

### 17.1 Must have
HTTPS everywhere (Caddy auto-TLS) · 15-min access JWT with `school_id`+`role` · refresh in HttpOnly/Secure/SameSite=Strict cookie with rotation + family theft detection · account lockout (5 / 15-min Redis) · RBAC at API layer (never frontend-only) · `school_id` scoping on **every** query (app-level MVP, RLS V2) · Pydantic validation on all inputs · rate limiting (auth 5/min, API 100/min, location 1/3s) · Socket.IO JWT auth + room authorization · GPS never exposed to unauthorized users · payment amounts DECIMAL · CORS restricted to `FRONTEND_URL` · `/api/v1` versioning · structured JSON logs with request context · **child safeguarding check on every trip end** · driver phone only during active trip + admin opt-in + masked + audit-logged · sensitive data scrubbed from all logs.

### 17.2 Must NOT have
No native-app dependency for parents/admins · no paid/proprietary libs (all OSS; managed services are swappable) · no vendor lock-in · **no file upload / object storage** (decision) · no card data stored locally · no blocking work on the Socket.IO event loop (safety/ETA checks are sub-ms in-memory) · no refresh tokens in localStorage · no plugin registry/auto-discovery in MVP · no cross-tenant leakage · no two-way in-app chat (removed; complaints for async, phone for urgent) · no exact phone/GPS in logs · no trip completion without safeguarding check · no "not-boarded" alerts for parent-marked-absent students.

### 17.3 Redis degradation
Redis is required for full real-time, but its loss must not lose data: GPS points fall back to direct PostgreSQL writes; rate limiting + lockout temporarily disabled (logged); route-deviation (V2) skipped until restored; `/health` surfaces `redis:"degraded"` within 5 min. No request fails solely due to Redis being down.

---

## 18. Logging & Monitoring (all free, minimal maintenance)

### 18.1 Stack
| Tool | Purpose |
|---|---|
| Sentry | error tracking (Python + React SDK), 5k/mo free |
| structlog | JSON logs: `request_id, user_id, school_id, method, path, status_code, duration_ms` |
| `/health` | `{status, db, redis, last_gps_event_at}` |
| UptimeRobot | pings `/health` every 5 min, email on 2 consecutive failures |

### 18.2 Logging config
- Levels: dev DEBUG, staging/prod WARNING (`LOG_LEVEL`).
- Processor chain: `add_log_level → add_timestamp → add_request_context → scrub_sensitive → JSONRenderer` (in `app/core/logging.py`).
- **Scrubbing:** phones masked to last 4 (`***1234`), GPS rounded to 2 decimals, emails domain-only (`***@school.com`), **tokens/passwords never logged** (also redact `?token=` from logged URLs).
- Scheduled jobs log `task_name, task_id, school_id, duration_ms, status`.
- Retention: file logs (VPS) via `docker/logrotate.conf` (`LOG_RETENTION_DAYS` default 30); Railway/Docker stdout handled by platform.
- **V2:** Prometheus/Grafana (WS connections, GPS/sec, latency p95), Loki log aggregation, alerts on >10% error rate / >500ms p95 / 0 GPS events in 5 min during school hours.

---

## 19. Testing Strategy

| Type | Tooling | Target | Gate |
|---|---|---|---|
| Unit | pytest + pytest-asyncio | service functions (safety logic, ETA, token rotation) mocked DB | part of coverage |
| Integration | httpx + real PostgreSQL/PostGIS (Docker) | every endpoint: auth, CRUD, transport flow, trip start/end, attendance, **safety alerts** | key flows fully covered |
| Frontend | Vitest + React Testing Library | components, stores, map state | — |
| E2E (V2) | Playwright | two sessions (driver+parent): start trip → GPS → parent sees bus; safety alert flows; ~5 critical paths | — |
| Load (V2) | locust | 500 concurrent, 50 active trips | — |

- `tests/factories.py`: `create_school/user/vehicle/route(+stops)/student/trip`.
- **CI gate:** Ruff clean + pytest green + **coverage ≥70% on new business logic** to merge.
- **Mandatory safety tests:** not-boarded fires for unmarked assigned student; no alert for parent-absent student; not-dropped blocks completion → `pending_safeguard_check`; atomic completion is idempotent under concurrent resolve+drop.

---

## 20. Hosting, Deployment & CI/CD

### 20.1 Tiers
| Tier | Setup | Cost | Capacity |
|---|---|---|---|
| Dev/Demo | Render free + Neon free + Upstash free + Cloudflare Pages | $0 | dev only (cold starts make WS impractical) |
| **MVP Prod** | **Railway (app + PostgreSQL + Redis) + Cloudflare Pages (web+landing)** | **~$12–18/mo** | ~500 concurrent |
| Growth | Hetzner VPS (Docker Compose) + Neon Pro | ~$5–30/mo | 2k–5k concurrent |
| Scale | Hetzner ×2 + LB + managed DB + Socket.IO Redis adapter | ~$50–80/mo | 10k+ |

**PostGIS note:** Railway default PG lacks PostGIS — use a custom `FROM postgres:16` + `postgresql-16-postgis-3` image, or Neon/Supabase (PostGIS preinstalled). Verify `SELECT PostGIS_Version();` before Phase 1 completes.

### 20.2 Containers
Multi-stage Dockerfiles (backend, web, landing). `docker-compose.yml` (dev): app + postgres/postgis + redis (AOF on). Caddy for prod TLS + reverse proxy. App image runs the single ASGI process (uvicorn) which hosts FastAPI + Socket.IO + APScheduler + the asyncio GPS flusher.

### 20.3 Migrations & bootstrap
Alembic autogenerate + reviewed migrations; `alembic upgrade head` on deploy. Bootstrap seed/CLI creates the first school (+ `join_code`) and first `school_admin` (and a `super_admin` for V2).

### 20.4 CI/CD (GitHub Actions)
PR: Ruff → pytest (+coverage gate) → build. Main: build images → deploy backend (Railway) → deploy web+landing (Cloudflare Pages) → `alembic upgrade head`. Secrets via GitHub/Railway env. UptimeRobot watches `/health` post-deploy.

---

## 21. Phased Build Plan (step-by-step)

Build in order. Each step lists tasks and **acceptance criteria = definition of done**. Do not advance until criteria pass.

### §21.0 Git Workflow & Tag Convention

**Branch strategy**

| Branch | Purpose |
|---|---|
| `main` | Always deployable; protected — no direct push ever |
| `dev` | Integration target; CI must be green before any merge |
| `feat/<scope>-<slug>` | One branch per task; PR → `dev`; delete after merge |
| `release/<version>` | Cut from `dev` at milestone; only bug-fixes land here |

**Commit message format** — Conventional Commits, enforced by pre-commit hook:

```
<type>(<scope>): <short description, imperative, ≤72 chars>

Types : feat | fix | test | chore | docs | refactor | perf | ci | security
Scopes: auth | trips | safety | gps | socket | frontend | db | jobs | config | api
```

Example: `feat(safety): add atomic not-dropped gate with idempotency guard`

**Tag-per-step table** — tag on `dev` once all acceptance criteria pass, then merge to `main`:

| Step | Step tag | Release tag | Milestone |
|---|---|---|---|
| 1 | `step-1` | — | Infra + CI green |
| 2 | `step-2` | — | Auth complete |
| 3 | `step-3` | `v0.3.0-alpha` | Entity CRUD complete |
| 4 | `step-4` | — | GPS + real-time |
| 5 | `step-5` | — | Safety system |
| **6** | `step-6` | **`v1.0.0-mvp`** | **Week-8 demo — ship MVP** |
| 7 | `step-7` | `v1.1.0` | Multi-tenancy hardening |
| 8 | `step-8` | `v1.2.0` | Capacitor driver app |
| 9 | `step-9` | `v1.3.0` | Deviation + push + SOS |
| 10 | `step-10` | `v1.4.0` | Substitute driver + broadcasts |
| 11 | `step-11` | `v1.5.0` | Reports + feedback + payments |
| **12** | `step-12` | **`v2.0.0`** | **Production hardened — V2 ship** |

**Tagging command (annotated tags, not lightweight):**

```bash
git tag -a step-N -m "Step N: <Name> — acceptance criteria passed"
git push origin step-N          # push step tag
git tag -a v1.0.0-mvp -m "MVP Week-8 demo complete"
git push origin v1.0.0-mvp     # push release tag (milestone steps only)
```

**Rules:**
1. Never merge a branch with failing tests. CI green = required.
2. Tags are immutable after push. Bug on a shipped milestone → new patch tag (`v1.0.1`), never re-tag.
3. `CHANGELOG.md` entry at every semver tag (use `git-cliff` or `conventional-changelog`).
4. Staging auto-deploys from `main` HEAD. Production Railway deploy requires a semver tag push trigger.
5. If a step's acceptance fails after tagging, create `fix/<slug>` → re-PR → re-tag with a patch suffix (`step-3-fix1`).

---

### PHASE 1 — Foundation (Weeks 1–3)

**Step 1 — Scaffolding & core infra**
- Monorepo (`backend/`, `web/`, `landing/`); `docker-compose.yml` = app + postgres/postgis + redis(AOF).
- FastAPI modular-monolith layout (§23); SQLAlchemy 2.0 async (pool 20/10/30); Alembic; Pydantic settings (`config.py`); Ruff + pre-commit.
- `app/core/logging.py` (structlog chain + scrubbing); Sentry (Python SDK); `/health`.
- APScheduler bootstrap + asyncio GPS-flusher skeleton; CORS = `FRONTEND_URL`; `/api/v1` prefix.
- pytest + `tests/factories.py`; GitHub Actions (lint+test+coverage).
- **Acceptance:** `docker compose up` starts all services; `SELECT PostGIS_Version()` works; `/health` 200 with db+redis; `pytest` green; JSON logs show masked phone/GPS; CI pipeline green.
- **Git:** `git tag -a step-1 -m "Step 1: Scaffolding & core infra — acceptance passed" && git push origin step-1`

**Step 2 — Auth & users**
- JWT access (15m, claims) + refresh (30d, HttpOnly cookie) with rotation + family theft detection (`refresh_tokens`).
- Parent self-register via `join_code`; admin-created drivers/admins; bootstrap seed (first school + admin).
- Login/logout/refresh; account lockout (Redis); password reset via Resend (`auth_tokens`); `GET/PUT /me`.
- `require_role` dependency + `school_id` scope dependency.
- **Acceptance:** all auth endpoints pass integration tests; refresh reuse revokes family; lockout after 5 fails, unlocks after 15m; access token carries `school_id`+`role`; password-reset email sends in dev (Resend sandbox); parent cannot register without valid join_code.
- **Git:** `git tag -a step-2 -m "Step 2: Auth & users — acceptance passed" && git push origin step-2`

**Step 3 — Schools & entity CRUD**
- Schools CRUD + settings + `join_code` regen + `school_location`.
- Vehicles CRUD (plate unique/school, capacity); Drivers manage + assign; Routes CRUD (optimistic `version`); Stops CRUD + reorder + GIST; Students (parent-owned); Transport requests + `suggest-stop` (geocode → `ST_Distance` top-3); assignment with capacity guard.
- App-level `school_id` filtering on every query (shared helper).
- **Acceptance:** full CRUD works; transport-request flow completes end-to-end; suggest-stop returns nearest within 1 km; School-A data invisible to School-B users; capacity guard returns 409 on overflow; stale `version` update returns 409.
- **Git:** `git tag -a step-3 -m "Step 3: Schools & entity CRUD — acceptance passed" && git push origin step-3` then `git tag -a v0.3.0-alpha -m "Alpha: entity layer complete" && git push origin v0.3.0-alpha`

### PHASE 2 — Core GPS, Safety & Frontend (Weeks 4–8)

**Step 4 — Trips & real-time GPS**
- Trip model + `POST /trips` + `POST /trips/generate` + `generate_daily_trips` job + `check_driver_no_show` job.
- Socket.IO mounted on ASGI; connect-auth; `join_trip` room auth; `location_update` (driver-only, 1/3s); broadcast to room; Redis GPS buffer + 30s asyncio flush; monthly partitions; ETA (straight-line) + `bus_approaching`; `tracking_paused` at >30s.
- **Acceptance:** driver shares location → parent sees update <1s; GPS persists to partitioned `gps_logs`; unauthorized socket rejected; rate limit enforced; stale GPS shows "tracking paused"; no-show alert fires 15 min past `scheduled_departure_at`.
- **Git:** `git tag -a step-4 -m "Step 4: Trips & real-time GPS — acceptance passed" && git push origin step-4`

**Step 5 — Safety system (`safety.py`)**
- Attendance batch endpoint (UPSERT) = stop-complete trigger; not-boarded detection; drop-off endpoints (school/stop); not-dropped gate → `pending_safeguard_check`; atomic completion guard; parent absent-marking; driver phone disclosure (§10.5) + audit log.
- Socket events: `attendance_update`, `child_not_boarded`, `child_not_dropped`, `child_absent_marked`.
- **Acceptance:** unmarked assigned student → parent gets `child_not_boarded` <2s; parent-absent student → no alert + driver sees greyed; end trip with boarded-not-dropped → CRITICAL alert + status `pending_safeguard_check`, cannot reach `completed`; resolving last alert (admin) or marking drop (driver) completes trip exactly once (idempotent under concurrency).
- **Git:** `git tag -a step-5 -m "Step 5: Safety system — acceptance passed" && git push origin step-5`

**Step 6 — Frontend MVP + integration/demo**
- React SPA: auth pages, parent (dashboard/track/request/absent), driver (route/run/attendance/drop), admin (wizard/vehicles/routes editor/requests/fleet map/alerts/settings); i18n English; map config by env; graceful WS degradation.
- Integration tests for the full demo flow; CI coverage gate ≥70%.
- **Acceptance (Week-8 demo):** admin sets up vehicle+route → parent registers (join code) + requests + assigned → driver starts trip + shares GPS → parent tracks live with ETA → driver marks attendance → not-boarded + not-dropped alerts fire correctly → end-to-end in one session; works on mobile Chrome/Safari; CI green ≥70%.
- **Git (MVP ship):**
  ```bash
  git tag -a step-6 -m "Step 6: Frontend MVP + integration demo — acceptance passed"
  git tag -a v1.0.0-mvp -m "YatraTrack v1.0.0-mvp — Week-8 demo complete, ready for pilot"
  git push origin step-6 v1.0.0-mvp
  # Then merge dev → main and deploy to staging for demo
  ```

### V2 — Production features (Weeks 9–16)

**Step 7 — Multi-tenancy hardening:** PostgreSQL RLS policies + `SET LOCAL` middleware; super_admin role + school CRUD UI; OWASP pass. *Acc:* cross-tenant query blocked even via raw SQL. *Tag:* `git tag -a step-7 -m "Step 7: Multi-tenancy" && git tag -a v1.1.0 -m "v1.1.0" && git push origin step-7 v1.1.0`

**Step 8 — Capacitor driver app (Android):** wrap driver module; `@capacitor/geolocation` background GPS; secure refresh-token storage + header auth; APK. *Acc:* GPS tracks with screen off. *Tag:* `git tag -a step-8 -m "Step 8: Capacitor driver app" && git tag -a v1.2.0 -m "v1.2.0" && git push origin step-8 v1.2.0`

**Step 9 — Deviation, push, SOS, incidents:** route-deviation (Redis-cached corridor, 2 consecutive misses); web-push (VAPID); SOS + driver incident; alert dashboard. *Acc:* deviation alert <5s; push on Chrome/Firefox; SOS visible <2s. *Tag:* `git tag -a step-9 -m "Step 9: Deviation + push + SOS" && git tag -a v1.3.0 -m "v1.3.0" && git push origin step-9 v1.3.0`

**Step 10 — Substitute driver, multi-child, broadcasts:** `reassign` + `trip_reassigned`; aggregated parent dashboard (N rooms); broadcasts table + event. *Acc:* reassigned driver gets trip; parent sees all children; broadcast delivered + persisted. *Tag:* `git tag -a step-10 -m "Step 10: Sub-driver + broadcasts" && git tag -a v1.4.0 -m "v1.4.0" && git push origin step-10 v1.4.0`

**Step 11 — Feedback, complaints, reports, analytics, payments structure:** feedback (aggregate-to-driver) + auto-flag; complaints; streamed PDF/Excel reports; Recharts analytics; fee/invoice/manual-payment. *Acc:* report streams correctly; flagged-rating pattern alert; dashboard <2s. *Tag:* `git tag -a step-11 -m "Step 11: Reports + payments" && git tag -a v1.5.0 -m "v1.5.0" && git push origin step-11 v1.5.0`

**Step 12 — E2E + production hardening:** Playwright (driver+parent), offline GPS buffering (IndexedDB sync), locust 500/50, EXPLAIN ANALYZE tuning, prod Docker + deploy docs. *Acc:* E2E pass; load pass; offline sync after 5-min disconnect. *Tag:*
```bash
git tag -a step-12 -m "Step 12: E2E + production hardening — V2 complete"
git tag -a v2.0.0 -m "YatraTrack v2.0.0 — production hardened, V2 feature-complete"
git push origin step-12 v2.0.0
# Railway: production deploy triggered by v2.0.0 tag push
```

### Future (post-launch)
Razorpay/Stripe gateway · plugin architecture extraction · route optimization · driver-behavior analytics · SMS (MSG91) · RFID/QR attendance · historical trip replay · white-label · React Native app · iOS driver app · multi-guardian · global/multi-currency · bulk CSV import · per-driver phone opt-out · email verification.

---

## 22. Edge Cases & Mitigations

| Edge case | Mitigation |
|---|---|
| Driver GPS pauses (background/lock) | MVP: "Tracking paused" + staleness + "keep screen on". V2: Capacitor background GPS. |
| Offline GPS (tunnel/rural) | V2: IndexedDB buffer → `location_batch` on reconnect; not re-broadcast; parents saw "paused". |
| Driver no-show | `check_driver_no_show` job: 15 min past `scheduled_departure_at` → admin alert; admin reassigns/cancels. |
| Child not boarded | stop-complete submit → HIGH alert to parent+admin <2s. |
| Child not dropped | trip-end gate → CRITICAL + `pending_safeguard_check` until resolved. |
| Parent marks absent after start | rejected (only before `in_progress`); contact admin. |
| Driver forgets attendance | trip can't complete with boarded-not-dropped; unmarked assigned at a completed stop → not-boarded alerts. |
| SOS false alarm (V2) | confirm tap; admin ack; auto-resolve 30 min. |
| Battery drain | reduce GPS to 10s when battery <20%; warn; suggest charging. |
| Browser tab closed (driver) | MVP: auto-pause + "paused"; reopen to resume. V2: Capacitor handles. |
| WebSocket failure | graceful: "Connecting…"; REST serves core data; GPS → last-known + staleness. |
| Concurrent route edits | optimistic `version` → 409; admin resolves. |
| Large school (50+ buses) | admin map clustering; route/status filters; paginated APIs. |
| Insurance/fitness expiry | daily job: 30/7/1-day warnings; auto-deactivate on expiry. |
| Token theft | refresh family revoke on reused rotated token. |
| Brute force login | lockout 5 / 15-min Redis. |
| Redis down | direct PG writes; limiting/lockout skipped (logged); health degraded; no data loss. |
| Data export / account deletion (DPDP) | JSON export endpoint (Future); deletion anonymizes, retains financial/audit records. |

---

## 23. Project Structure

```
backend/
  app/
    main.py            # FastAPI + Socket.IO mount + APScheduler start + include_router()
    config.py          # Pydantic settings (env)
    database.py        # async engine/session
    deps.py            # get_db, get_current_user, require_role, get_school_scope
    middleware.py      # CORS, rate limiting, school scope, request_id
    core/
      logging.py       # structlog chain + scrubbing
      scheduler.py     # APScheduler jobs registration
      socketio.py      # Socket.IO server + connection auth
    auth/  schools/  vehicles/  routes/
    tracking/          # trips, gps, socket_handlers.py, safety.py
    notifications/
    communication/     # broadcasts (V2), complaints (V2)
    reports/           # (V2) reportlab/openpyxl streaming
    payments/
      gateways/ base.py  razorpay.py(Future)  stripe.py(Future)
  tests/ factories.py ...
  alembic/  docker/logrotate.conf  Dockerfile
web/                   # React SPA (parent/driver/admin) — §13
landing/               # static marketing site — §14
docker-compose.yml  Caddyfile  .github/workflows/ci.yml
```
Each backend module: `router.py · models.py · schemas.py · services.py · tests/`. Registration is explicit in `main.py` (no auto-discovery).

---

## 24. Open / Launch-Blocking Register

These do **not** block development — build with placeholders, resolve before go-live.

| Item | Needed for | Placeholder used |
|---|---|---|
| OQ-1 Pilot school + real capacity | hosting tier sizing | assume 1 school, ~10 buses, ~500 students → MVP-Prod tier |
| OQ-7/22 Domain | SSL, PWA manifest, email sender | `yatratrack.in` |
| OQ-20 WhatsApp number | landing CTA | `+91XXXXXXXXXX` |
| OQ-21 Contact email | landing CTA, sender | `hello@yatratrack.in` |
| OQ-16 Compliance fields | V2 compliance report | default template (§15.2) |
| Branding assets (logo) | UI/landing | text/initials avatars; `logo_url` optional |

**Everything else is decided in §2 and built per §21.** If any decision proves wrong during build, change it here in §2 first (single source of truth), then propagate.

---

*End of specification. This document supersedes all prior planning docs in `docs/`.*





