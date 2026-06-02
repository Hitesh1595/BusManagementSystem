# School Bus / Vehicle Management System - Product Plan

> ⚠️ **SUPERSEDED — kept for history only.** The single authoritative source of truth is [`YATRATRACK-BUILD-SPEC.md`](./YATRATRACK-BUILD-SPEC.md) (v1.0, 2026-05-30). Several details here (timeline, attendance/alert enums, RLS timing) are stale; do not build from this doc.

**Date:** 2026-05-26
**Author:** Planner Agent
**Status:** REVISED - Incorporating Architect + Critic Feedback (Iteration 1)
**Complexity:** HIGH
**Estimated Scope:** ~40 files across 6 modules, 2 phases (MVP) + V2 + Future

---

## Table of Contents

1. [RALPLAN-DR Summary](#1-ralplan-dr-summary)
2. [PRD - Product Requirements Document](#2-prd---product-requirements-document)
3. [Architecture Overview](#3-architecture-overview)
4. [Tech Stack Recommendation](#4-tech-stack-recommendation)
5. [Feature List - MVP / V2 / Future](#5-feature-list---mvp--v2--future)
6. [Database Schema](#6-database-schema)
7. [API Design](#7-api-design)
8. [Task Breakdown - Phased Implementation](#8-task-breakdown---phased-implementation)
9. [Hosting Strategy](#9-hosting-strategy)
10. [Payment Integration Plan](#10-payment-integration-plan)
11. [Testing Strategy](#11-testing-strategy)
12. [Monitoring & Observability](#12-monitoring--observability)

---

## 1. RALPLAN-DR Summary

### Principles (5)

1. **Browser-First for Parents and Admins, Capacitor-Wrapped for Drivers** - Parent and admin roles use mobile browser PWA. Driver role uses a Capacitor.js-wrapped build of the same React codebase to enable reliable background GPS tracking via native geolocation plugin.
2. **Modular Monolith, Plugin-Ready** - Feature modules live in separate directories (`app/tracking/`, `app/vehicles/`, `app/chat/`, etc.) with explicit `include_router()` registration in `main.py`. No auto-discovery or plugin registry for MVP. Directory structure preserves refactorability for V2 plugin extraction.
3. **Minimal Infra, Maximum Scale** - Use async Python, connection pooling, and edge caching to serve thousands of concurrent users on a single $12-18/mo hosting setup (single ASGI process).
4. **Data Sovereignty** - All data lives in a single relational DB. No vendor lock-in. Export everything. Single-school for MVP; multi-tenant by design in V2.
5. **Graceful Degradation** - When WebSocket connections fail, the app shows meaningful loading states. Core data (routes, schedules, attendance history) is accessible via REST API. GPS tracking degrades to "last known position with staleness timestamp" rather than showing stale data as live.

### Decision Drivers (Top 3)

| # | Driver | Weight | Rationale |
|---|--------|--------|-----------|
| 1 | **Real-time WebSocket performance** | Critical | GPS tracking demands sustained concurrent connections (1 driver broadcasting to N parents). Framework must handle async natively. |
| 2 | **Minimal hosting cost** | High | Target audience is schools (budget-sensitive). System must run on $12-18/mo initially and scale to $50-100/mo for thousands of users. |
| 3 | **Developer velocity with Python** | High | Solo dev. Must ship demoable MVP in 6 weeks. Framework must have good ORM, auth, and docs out of the box. |

### Viable Options with Pros/Cons

#### Backend Framework

| Option | Pros | Cons |
|--------|------|------|
| **Option A: FastAPI + SQLAlchemy** | Native async/await, ~3200 concurrent WS connections per instance, auto-generated OpenAPI docs, Pydantic validation built-in | No built-in admin panel, no ORM migrations out of box (need Alembic), auth must be hand-rolled or use 3rd party, smaller ecosystem than Django |
| **Option B: Django + Channels** | Built-in admin panel (huge for school admin portal), mature ORM with migrations, battle-tested auth/permissions, massive ecosystem, Django REST Framework | ~1800 concurrent WS connections per instance, requires Redis for channel layer, heavier memory footprint, sync-first (Channels adds complexity), slower API throughput |

**Decision: Option A - FastAPI + SQLAlchemy**
**Rationale:** Real-time GPS tracking is the core differentiator. FastAPI's native async handles nearly 2x the WebSocket connections of Django Channels on equivalent hardware. The admin panel gap is filled by a custom React-based dashboard (needed anyway for the clean UI requirement). SQLAlchemy 2.0 with async support + Alembic provides equivalent ORM capability. Authentication via custom JWT is straightforward.
**Invalidation of Option B:** Django Channels requires Redis as a mandatory dependency (adds cost and complexity), and the sync-to-async bridge introduces latency on the critical GPS path. The built-in admin saves time but doesn't meet the "clean UI" requirement -- a custom dashboard is needed regardless.

#### Database

| Option | Pros | Cons |
|--------|------|------|
| **Option A: PostgreSQL + PostGIS** | 1000+ spatial functions, ACID compliance, mature, free on Supabase/Neon/Railway, excellent with SQLAlchemy, geofencing built-in | Slightly more complex setup than MongoDB for simple point queries, PostGIS extension must be enabled |
| **Option B: MongoDB** | Fast simple geospatial queries, flexible schema for rapid prototyping, Atlas free tier (512MB) | Limited geospatial operations vs PostGIS, no ACID by default, harder to enforce data integrity for financial/attendance records, ODM less mature than SQLAlchemy |

**Decision: Option A - PostgreSQL + PostGIS**
**Rationale:** School transport data is inherently relational (students belong to schools, ride on routes, driven by drivers, paid for by parents). Financial records (payments) and attendance require ACID guarantees. PostGIS provides geofencing, route deviation detection, and proximity queries that MongoDB cannot match. Free PostgreSQL available on Neon (free tier: 0.5GB), Supabase (free tier: 500MB), or Railway ($5/mo).
**Invalidation of Option B:** MongoDB's lack of ACID guarantees is unacceptable for payment records and attendance data. Its geospatial subset cannot support geofencing or route deviation alerts without application-level computation.

#### Frontend

| Option | Pros | Cons |
|--------|------|------|
| **Option A: React (Vite) + Leaflet.js** | Largest ecosystem, most Leaflet/map integrations available, huge talent pool, excellent WebSocket libraries, PWA support | Larger bundle size, more boilerplate, virtual DOM overhead for frequent map updates |
| **Option B: Svelte (SvelteKit) + Leaflet.js** | Smallest bundle size (~40% less than React), compiled to vanilla JS (fastest DOM updates for map markers), simpler state management, excellent for real-time UIs | Smaller ecosystem, fewer map component libraries, smaller talent pool |

**Decision: Option A - React (Vite) + Leaflet.js**
**Rationale:** The ecosystem advantage is decisive for a project with map tracking, real-time updates, chat UI, payment forms, and admin dashboards. `react-leaflet` is mature and well-maintained. PWA capabilities (installable, offline shell) provide the "app-like" experience without a native app. Vite keeps the dev experience fast. Shadcn/ui provides the clean UI foundation at zero cost.
**Alternative kept viable:** Svelte remains a strong option if the team prefers it. The architecture is frontend-agnostic by design.

#### Real-Time / GPS Transport

| Option | Pros | Cons |
|--------|------|------|
| **Option A: Native WebSocket (FastAPI)** | Zero additional dependencies, built into FastAPI, full control, no external service cost | Must implement pub/sub pattern manually, horizontal scaling requires shared state (Redis) |
| **Option B: Socket.IO (python-socketio)** | Room-based broadcasting (perfect for route-based groups), automatic reconnection, fallback to long-polling, client library handles edge cases | Additional dependency, slightly more overhead than raw WS, Python server implementation less performant than Node.js version |

**Decision: Option B - Socket.IO (python-socketio)**
**Rationale:** Room-based broadcasting is a natural fit -- each active route is a "room" that the driver publishes to and subscribed parents receive from. Automatic reconnection handles the mobile browser going to background/foreground. Long-polling fallback handles older browsers and restrictive networks. The `python-socketio` library integrates cleanly with FastAPI's ASGI server. **Note:** FastAPI and Socket.IO run in the SAME ASGI process via `python-socketio`'s ASGIApp mount -- not two separate services.

#### Hosting

| Option | Pros | Cons |
|--------|------|------|
| **Option A: Railway** | Git-push deploy, auto-detection of Python, managed PostgreSQL addon, $5/mo hobby plan, easy env vars, built-in metrics | No free tier (removed), costs start immediately, less control than VPS |
| **Option B: Self-hosted VPS (Hetzner/DigitalOcean)** | Full control, $4-6/mo for 2GB RAM, can run DB + app + Redis on one box, no vendor lock-in, predictable cost | Manual setup (Docker Compose), manual SSL (Caddy/Certbot), manual backups, no auto-scaling |
| **Option C: Render (free tier) + Neon (free tier)** | $0/mo to start, free PostgreSQL (Neon), free web service (Render), automatic deploys | Cold starts on free tier (30s spin-up), 512MB RAM limit, service sleeps after 15min inactivity, not suitable for always-on WebSocket |

**Decision: Tiered approach**
- **Development/Demo:** Option C (Render free + Neon free) - $0/mo
- **Production MVP:** Option A (Railway) - ~$12-18/mo (single app service + PostgreSQL addon + Redis addon)
- **Scale:** Option B (Hetzner VPS with Docker Compose) - $6-12/mo for 2-4GB RAM, unlimited control

### ADR (Architectural Decision Record)

| Field | Value |
|-------|-------|
| **Decision** | FastAPI + PostgreSQL/PostGIS + React/Vite + Socket.IO + Leaflet.js, running as single ASGI process |
| **Drivers** | Real-time WebSocket performance, minimal hosting cost, Python developer velocity |
| **Alternatives Considered** | Django+Channels, MongoDB, Svelte, raw WebSocket, various hosting tiers |
| **Why Chosen** | FastAPI delivers 2x WS throughput vs Django Channels at lower memory. PostgreSQL ensures ACID for payments/attendance with PostGIS for geospatial. React ecosystem provides the richest map/UI component library. Socket.IO rooms map directly to route-based broadcasting. Single ASGI process keeps hosting cost at ~$12-18/mo. |
| **Consequences** | No built-in admin (must build custom dashboard). Must manage Alembic migrations manually. Redis required for Socket.IO scaling beyond single instance. Plugin infrastructure deferred to V2 -- modular monolith preserves refactorability. Multi-tenancy (RLS) deferred to V2 -- MVP is single-school. |
| **Follow-ups** | Extract plugin architecture in V2 after product-market fit is validated. Evaluate Svelte migration if bundle size becomes an issue at scale. Consider managed WebSocket service (Ably/Pusher free tier) if self-hosted Socket.IO hits limits. Add Capacitor.js driver app wrapper for production background GPS in V2. |

---

## 2. PRD - Product Requirements Document

### 2.1 Vision Statement

A browser-based school transport management platform that lets schools manage vehicle fleets, parents request and track transport in real-time, and drivers receive optimized routes -- all without installing a native app. Driver GPS tracking uses a Capacitor.js-wrapped PWA for reliable background location in production (V2); MVP uses browser with "keep screen on" workaround.

### 2.2 Actors

| Actor | Description | Key Motivations |
|-------|-------------|-----------------|
| **Parent/Guardian** | Registers children, requests transport, tracks bus in real-time | Safety of child, punctuality, transparency |
| **Driver** | Receives route assignments, shares GPS location, marks attendance (V2) | Clear instructions, minimal distraction, easy attendance |
| **School Admin** | Manages vehicles, routes, drivers, students | Operational efficiency, safety compliance |
| **Super Admin** | Manages multiple schools (V2), platform configuration | Platform growth, multi-tenant management |
| **Student** | Passive actor -- tracked via attendance, associated with parent and route | (No direct system interaction) |

### 2.3 User Stories & Acceptance Criteria

#### Epic 1: Vehicle & Fleet Management

**US-1.1** As a School Admin, I want to register vehicles with details (plate number, capacity, type, insurance expiry) so I can manage my fleet.
- AC: CRUD operations on vehicles. Validation on plate number uniqueness per school. Insurance expiry alerts 30 days before.

**US-1.2** As a School Admin, I want to assign drivers to vehicles so I know who operates each vehicle.
- AC: One driver per vehicle at a time. Driver must have valid license. Assignment history tracked.

**US-1.3** As a School Admin, I want to create and manage routes (name, stops, schedule, assigned vehicle) so transport is organized.
- AC: Route has ordered list of stops with GPS coordinates. Stop can be searched by address (geocoding). Route visualized on map.

#### Epic 2: Transport Request & Assignment

**US-2.1** As a Parent, I want to register my child and request school transport so my child can ride the bus.
- AC: Parent submits pickup address + child details. System suggests nearest route/stop (Nominatim geocode -> ST_Distance query -> top 3 nearest stops). Admin approves or assigns alternative. Parent notified of assignment.

**US-2.2** As a School Admin, I want to review transport requests and assign students to routes so buses are not overloaded.
- AC: Dashboard shows pending requests with map overlay. Capacity check prevents over-assignment. Bulk approval supported.

**US-2.3** As a Driver, I want to see my assigned route with stops and student list so I know my schedule.
- AC: Driver dashboard shows today's route, ordered stops, student count per stop, parent contact info (masked). Turn-by-turn not required (use native maps link).

#### Epic 3: Real-Time GPS Tracking

**US-3.1** As a Driver, I want to start a trip and share my live location so parents can track the bus.
- AC: "Start Trip" button activates Geolocation API (`watchPosition`). Location sent via WebSocket every 5-10 seconds. **MVP:** Browser-based with "keep screen on" warning -- GPS pauses if browser goes to background. **V2:** Capacitor.js-wrapped app with `@capacitor/geolocation` plugin for reliable background tracking. Battery usage warning shown.

**US-3.2** As a Parent, I want to see the bus location on a live map so I know when to expect it.
- AC: Map shows bus icon moving in real-time. ETA to child's stop shown (calculated from current position + route). Last-updated timestamp visible. "Bus has arrived" notification when within 200m of stop. When GPS data is stale (>30s old), show "Tracking paused" indicator with last-known position and staleness timestamp.

**US-3.3** As a School Admin, I want to see all active trips on a dashboard map so I can monitor fleet status.
- AC: Admin map shows all active buses with color-coded status (on-time, delayed). Click bus to see driver, route, passenger count, speed.

#### Epic 4: Notifications & Alerts (MVP: In-App Only)

**US-4.1** As a Parent, I want in-app notifications when the bus trip starts and ends.
- AC: In-app notification when trip starts and ends. Real-time via Socket.IO. **V2:** Browser push notification (via Service Worker) triggered when bus is within configurable distance.

**US-4.2** As a School Admin, I want alerts when a bus deviates from its assigned route. (V2)
- AC: System compares live GPS to route corridor (PostGIS buffer cached in Redis). Alert triggered if bus is >500m from route for 2 consecutive GPS updates. Alert shown on admin dashboard. Detection within 5 seconds of GPS update.

**US-4.3** As a Parent, I want to trigger an SOS alert that notifies the school immediately. (V2)
- AC: SOS button on parent dashboard. Creates high-priority alert on admin dashboard with sound. Logs timestamp, parent, child, bus. Admin must acknowledge.

**US-4.4** As a Driver, I want to report incidents (breakdown, accident, delay) so the school can respond. (V2)
- AC: Quick-select incident type + optional note. Creates alert on admin dashboard. Affected parents notified automatically.

#### Epic 5: Communication (V2)

**US-5.1** As a Parent, I want to chat with the school admin about transport issues.
- AC: In-app messaging. Threaded conversations. Admin sees all parent messages in a unified inbox.

#### Epic 6: Attendance Tracking (V2)

**US-6.1** As a Driver, I want to mark student attendance at each stop so parents know their child boarded.
- AC: At each stop, driver sees student list. Tap to mark "boarded" / "not present." Parent notified in real-time.

#### Epic 7: Admin Dashboard & Analytics (V2)

**US-7.1** As a School Admin, I want a dashboard showing fleet overview, active trips, alerts, and key metrics.
- AC: Dashboard shows: total vehicles, active trips, pending requests, today's incidents, on-time percentage.

#### Epic 8: Payment (Future-Ready Structure, V2)

**US-8.1** As a School Admin, I want to set transport fee schedules per route/term.
- AC: CRUD on fee schedules. Supports one-time, monthly, term-based billing.

#### Epic 9: Multi-School Support (V2)

**US-9.1** As a Super Admin, I want to onboard new schools with isolated data.
- AC: Tenant creation with school name, domain, admin user. All data scoped by `school_id`. No cross-tenant data leakage.

### 2.4 Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| **Response Time** | API: <200ms p95. Map update: <500ms latency. |
| **Concurrent Users** | MVP: 500 simultaneous. Scale: 5,000+. |
| **Uptime** | 99.5% during school hours (6AM-6PM). |
| **Data Retention** | GPS logs: 90 days (auto-cleanup via daily Celery job dropping old partitions). Attendance: 1 year. Payments: 7 years. |
| **Security** | HTTPS everywhere. JWT with refresh token rotation in HttpOnly cookies. RBAC (role-based access). Account lockout after 5 failed attempts. |
| **Accessibility** | WCAG 2.1 AA for parent-facing UI. |
| **Offline Tolerance** | Driver app buffers GPS when offline (IndexedDB), syncs on reconnect. Parent app shows last-known position with staleness indicator. |

---

## 3. Architecture Overview

### 3.1 System Components

```
+------------------------------------------------------------------+
|                        CLIENT LAYER                               |
|                                                                   |
|  +------------------+  +------------------+  +------------------+ |
|  | Parent PWA       |  | Driver App       |  | Admin Dashboard  | |
|  | (React + Leaflet)|  | (React + Leaflet)|  | (React + Charts) | |
|  | Browser-based    |  | MVP: Browser     |  | Browser-based    | |
|  | GPS: No          |  | V2: Capacitor.js |  | GPS: No          | |
|  |                  |  | @capacitor/geo   |  |                  | |
|  +--------+---------+  +--------+---------+  +--------+---------+ |
|           |                      |                      |         |
+-----------+----------------------+----------------------+---------+
            |                      |                      |
            v                      v                      v
+------------------------------------------------------------------+
|                     API GATEWAY / REVERSE PROXY                   |
|                        (Caddy / Nginx)                            |
|              SSL termination, rate limiting, CORS                 |
+------------------------------------------------------------------+
            |                      |                      |
            v                      v                      v
+------------------------------------------------------------------+
|              APPLICATION LAYER (Single ASGI Process)              |
|                                                                   |
|  +--------------------------------------------------------------+|
|  | FastAPI + Socket.IO (python-socketio mounted on same ASGI)   ||
|  |                                                               ||
|  | REST API:            Socket.IO:           Sync in handler:    ||
|  |  Auth, CRUD,          GPS broadcast,       Route deviation    ||
|  |  Biz Logic            Chat messages,       detection (via     ||
|  |                       Room management      Redis-cached       ||
|  |                                            PostGIS geometry)  ||
|  +--------------------------------------------------------------+|
|                                                                   |
|  +------------------+                                             |
|  | Celery Workers   |  (Separate process, same codebase)         |
|  | (Background Jobs)|                                             |
|  | - Notification    |                                            |
|  |   dispatch        |                                            |
|  |   (email/SMS/push)|                                            |
|  | - ETA calculation |                                            |
|  | - Report gen      |                                            |
|  | - GPS log cleanup |                                            |
|  |   (daily: drop    |                                            |
|  |    partitions >   |                                            |
|  |    90 days)       |                                            |
|  | - Insurance expiry|                                            |
|  |   checks          |                                            |
|  +------------------+                                             |
+------------------------------------------------------------------+
            |                      |                     |
            v                      v                     v
+------------------------------------------------------------------+
|                        DATA LAYER                                 |
|                                                                   |
|  +------------------+  +------------------+  +------------------+ |
|  | PostgreSQL       |  | Redis            |  | S3-Compatible    | |
|  | + PostGIS        |  | - Socket.IO pub  |  | Object Storage   | |
|  | - All app data   |  | - Session cache  |  | - Documents      | |
|  | - Geospatial     |  | - GPS buffer     |  | - Receipts       | |
|  | - Audit logs     |  | - Rate limiting  |  | - Profile photos | |
|  |                  |  | - Route corridor |  |                  | |
|  | pool_size=20     |  |   geometry cache |  |                  | |
|  | max_overflow=10  |  | - Account lockout|  |                  | |
|  | pool_timeout=30  |  |   tracking       |  |                  | |
|  +------------------+  +------------------+  +------------------+ |
+------------------------------------------------------------------+
```

### 3.2 Data Flow - GPS Tracking (Critical Path)

```
Driver Phone (MVP: Browser | V2: Capacitor App)
    |
    | 1. watchPosition() fires every 5s
    |    MVP: Browser Geolocation API (pauses when screen locked)
    |    V2:  @capacitor/geolocation (works in background)
    v
Socket.IO Client (driver app)
    |
    | 2. Emit "location_update" {lat, lng, speed, heading, timestamp, trip_id}
    v
Socket.IO Handler (FastAPI ASGI process) -- SYNCHRONOUS processing:
    |
    | 3a. Broadcast to room "trip:{trip_id}" --> All subscribed parents receive
    | 3b. Buffer in Redis (batch write every 30s to reduce DB writes)
    | 3c. Route deviation check (SYNCHRONOUS):
    |     - On trip start: compute PostGIS ST_Buffer(route_path, 500m),
    |       serialize corridor geometry, cache in Redis key "corridor:{trip_id}"
    |     - Every GPS update: Shapely `Point.within(cached_corridor)` check in Python
    |       (geometry deserialized from Redis WKB; sub-millisecond, no DB round-trip)
    |     - If outside corridor for 2 CONSECUTIVE updates:
    |       enqueue Celery task for notification dispatch ONLY.
    |       Detection is synchronous. Notification is async.
    | 3d. Calculate ETA: distance_to_next_stop / avg_speed
    |     If within 500m of stop --> Emit "bus_approaching" to parents at that stop
    v
PostgreSQL (batch insert GPS logs every 30s from Redis buffer)
    |
    | 4. GPS log stored: {trip_id, lat, lng, speed, heading, timestamp}
    |    Partitioned by month. Daily Celery job drops partitions > 90 days.
    v
Parent Phone Browser
    |
    | 5. Socket.IO receives "location_update"
    | 6. Leaflet map updates bus marker position (smooth animation)
    | 7. ETA display updates
    | 8. If GPS data is stale (>30s): show "Tracking paused" with
    |    last-known position + staleness timestamp
    | 9. If "bus_approaching" --> In-app notification (MVP)
    |    V2: Browser push notification via Service Worker
```

### 3.3 Data Flow - Offline GPS Handling

```
Driver enters tunnel / loses signal
    |
    | 1. Socket.IO disconnects
    | 2. Client-side buffer stores GPS points in IndexedDB
    |    (navigator.geolocation.watchPosition still fires)
    v
Signal restored
    |
    | 3. Socket.IO reconnects automatically (built-in)
    | 4. Client sends buffered points as batch: "location_batch" event
    | 5. Server processes batch (insert to DB, but does NOT re-broadcast stale points)
    | 6. Server resumes live broadcasting from current position
    v
Parent sees:
    - During offline: "Tracking paused - Last updated X minutes ago" with stale indicator
    - On reconnect: Bus marker jumps to current position (no replay of buffered path)
    - Trip history later shows complete path including offline segment
```

### 3.4 Modular Monolith Structure (MVP)

```
app/
  main.py             # FastAPI app + Socket.IO mount + explicit include_router() calls
  config.py           # Pydantic settings, env-based config
  database.py         # SQLAlchemy async engine (pool_size=20, max_overflow=10, pool_timeout=30)
  deps.py             # Dependency injection (get_db, get_current_user, etc.)
  middleware.py       # CORS, rate limiting, school_id scoping

  auth/               # JWT, RBAC, user management
    router.py
    models.py
    schemas.py
    services.py
    tests/

  schools/            # School CRUD (single-school MVP, multi-tenant V2)
    router.py
    models.py
    schemas.py
    services.py
    tests/

  vehicles/           # Vehicle + Driver management
    router.py
    models.py
    schemas.py
    services.py
    tests/

  routes/             # Route + Stop + Transport Request management
    router.py
    models.py
    schemas.py
    services.py
    tests/

  tracking/           # Trip, GPS, Socket.IO handlers
    router.py
    models.py
    schemas.py
    services.py
    socket_handlers.py  # Socket.IO event handlers (includes route deviation detection)
    tests/

  notifications/      # In-app notifications (V2: push, email, SMS)
    router.py
    models.py
    schemas.py
    services.py
    tests/

# Explicit registration in main.py (NO auto-discovery):
# app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
# app.include_router(schools.router, prefix="/api/v1/schools", tags=["schools"])
# app.include_router(vehicles.router, prefix="/api/v1/vehicles", tags=["vehicles"])
# app.include_router(routes.router, prefix="/api/v1/routes", tags=["routes"])
# app.include_router(tracking.router, prefix="/api/v1/trips", tags=["trips"])
# app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["notifications"])
```

Feature flags via simple school settings check (no plugin activation system):

```python
# Simple feature flag check in endpoints:
if school.settings.get("payments_enabled"):
    # include payment-related data in response
```

**V2: Plugin Architecture Extraction** - After product-market fit is validated, extract the modular monolith into a proper plugin registry with auto-discovery, event bus, and per-tenant feature flags. The directory structure is already organized to support this refactor.

---

## 4. Tech Stack Recommendation

### Every Layer - All Free/OSS

| Layer | Technology | License | Why |
|-------|-----------|---------|-----|
| **Language** | Python 3.12+ | PSF | User requirement. Async support mature. |
| **Backend Framework** | FastAPI 0.115+ | MIT | Native async, auto OpenAPI docs, Pydantic validation, WebSocket support. |
| **ORM** | SQLAlchemy 2.0 (async) | MIT | Best Python ORM. Async session support. PostGIS integration via GeoAlchemy2. |
| **Migrations** | Alembic | MIT | SQLAlchemy's official migration tool. Auto-generates from model changes. |
| **Real-Time** | python-socketio 5.x | MIT | Room-based pub/sub, auto-reconnect, long-polling fallback. **Mounts directly onto FastAPI ASGI app -- single process.** |
| **Task Queue** | Celery 5.x + Redis | BSD | Background jobs: notification dispatch, report generation, GPS log cleanup. |
| **Auth** | PyJWT + passlib + bcrypt | MIT | JWT access tokens + refresh tokens in HttpOnly cookies. bcrypt password hashing. RBAC via custom middleware. |
| **Validation** | Pydantic v2 | MIT | Built into FastAPI. Request/response validation. Settings management. |
| **Database** | PostgreSQL 16 + PostGIS 3.4 | PostgreSQL/GPL | Relational + geospatial. ACID. Free managed options available. |
| **Cache/Broker** | Redis 7 | BSD | Socket.IO adapter, Celery broker, GPS buffer, route corridor cache, rate limiting, account lockout tracking. |
| **Geospatial ORM** | GeoAlchemy2 | MIT | SQLAlchemy extension for PostGIS. Geometry/Geography column types. |
| **Frontend** | React 19 (Vite 6) | MIT | Component-based UI. Largest ecosystem. PWA support. |
| **UI Components** | shadcn/ui + Tailwind CSS 4 | MIT | Copy-paste components. No runtime dependency. Clean, accessible. |
| **Maps** | Leaflet.js 1.9 + react-leaflet | BSD | Lightweight (42KB). Real-time marker updates. |
| **Map Tiles** | Stadia Maps or MapTiler (free tiers) | Commercial/Free | Stadia: free 200k tiles/mo. MapTiler: free 100k tiles/mo. **Do not use OSM tile servers directly in production** (usage policy prohibits heavy use). Dev only: OSM tiles are fine. |
| **Charts** | Recharts or Chart.js | MIT | Admin analytics dashboards (V2). |
| **State Management** | Zustand | MIT | Lightweight (1KB). Perfect for real-time state (bus positions). |
| **HTTP Client** | Axios or ky | MIT | API calls from frontend. |
| **PWA** | Vite PWA Plugin | MIT | Service Worker generation. Offline shell. Install prompt. |
| **Driver Native Wrapper (V2)** | Capacitor.js + @capacitor/geolocation | MIT | Wraps same React codebase as Android/iOS WebView. Native geolocation plugin enables background GPS tracking. ~1 day to scaffold. |
| **Email** | SMTP (built-in) or Resend free tier | N/A | Transactional emails. Resend: 3,000/mo free. |
| **Geocoding** | Nominatim (OSM) for dev; MapTiler Geocoding for production | ODbL / Commercial Free | Nominatim: free, self-hostable, dev only (public instance rate-limited). MapTiler: free 100k geocoding requests/mo for production. |
| **Error Tracking** | Sentry | BSL (free tier) | Free tier: 5,000 errors/mo. Python SDK + React SDK. 1-hour setup. |
| **Logging** | structlog | MIT | JSON structured logs with request_id, user_id, school_id per request. |
| **Reverse Proxy** | Caddy 2 | Apache 2.0 | Automatic HTTPS. Simple config. Built-in rate limiting. |
| **Containerization** | Docker + Docker Compose | Apache 2.0 | Consistent dev/prod environments. Single-command deployment. |
| **Testing** | pytest + pytest-asyncio + httpx | MIT | FastAPI test client. Async test support. |
| **E2E Testing** | Playwright | Apache 2.0 | Multi-browser, two-session tests (driver + parent). |
| **Linting/Formatting** | Ruff | MIT | Replaces flake8 + isort + black. Extremely fast. |
| **Frontend Testing** | Vitest + React Testing Library | MIT | Fast, Vite-native testing. |
| **CI/CD** | GitHub Actions | Free (public) | Automated testing, linting, deployment. |
| **Uptime Monitoring** | UptimeRobot | Free tier | Pings `/health` every 5 minutes. Email alert on downtime. |

---

## 5. Feature List - MVP / V2 / Future

### MVP (Phase 1-2, Weeks 1-6) -- Multi-School from Day 1

| # | Feature | Priority |
|---|---------|----------|
| M1 | User registration & login (parent, driver, admin) with JWT auth + RBAC + refresh token rotation in HttpOnly cookies + account lockout | P0 |
| M2 | Multi-school setup: super admin creates schools; all data scoped by `school_id` in JWT claims and application-level filtering; PostgreSQL RLS policies as defense-in-depth | P0 |
| M3 | Vehicle CRUD (register, edit, deactivate buses) | P0 |
| M4 | Driver management (register, assign to vehicle) | P0 |
| M5 | Route management (create routes, add ordered stops with GPS, assign vehicle) | P0 |
| M6 | Student registration + transport request (parent requests pickup, admin approves, assigns to route/stop with nearest-stop suggestion) | P0 |
| M7 | Driver trip flow (start trip, share GPS via browser, end trip) | P0 |
| M8 | Real-time map tracking (parent sees bus live on Leaflet map, ETA to stop) | P0 |
| M9 | Basic notifications: trip started, trip ended (in-app only via Socket.IO, no push for MVP) | P0 |
| M10 | Basic admin view: active trips on map | P1 |

**Week 6 Demo Success Criteria:** Admin registers a vehicle + route. Parent requests and gets assigned. Driver starts trip and shares GPS. Parent sees bus moving on Leaflet map. End-to-end in one browser session.

### V2 (Weeks 7-14) -- Production Features

| # | Feature | Priority |
|---|---------|----------|
| V1 | Capacitor.js driver app wrapper (same React codebase, @capacitor/geolocation for background GPS) | P1 |
| V3 | PWA + service worker + web push notifications (bus approaching stop, trip started/ended) | P1 |
| V4 | Route deviation alerts (synchronous detection in Socket.IO handler, PostGIS corridor cached in Redis) | P1 |
| V5 | Student attendance marking (driver marks boarded/absent at each stop, parent notified) | P1 |
| V6 | SOS button (parent triggers emergency alert, admin acknowledges) | P1 |
| V7 | Driver incident reporting (breakdown, delay, accident quick-report) | P1 |
| V8 | Parent-to-admin messaging (simple threaded chat via Socket.IO) | P2 |
| V9 | Broadcast announcements (admin to route/all parents) | P2 |
| V10 | Payment structure (fee schedules, invoices, payment history -- no gateway yet) | P2 |
| V11 | Analytics dashboard (route efficiency, on-time %, attendance rates) | P2 |
| V12 | Offline GPS buffering (IndexedDB on driver device, sync on reconnect) | P2 |
| V13 | Email notifications (configurable per-user notification preferences) | P2 |

### Future (Post-Launch)

| # | Feature | Priority |
|---|---------|----------|
| F1 | Payment gateway integration — **Razorpay** (primary, India: UPI + cards + netbanking + wallets, 2% domestic fee). Stripe as fallback for international schools. Online payment, receipts, webhook verification. | P2 |
| F2 | Plugin architecture extraction (auto-discovery, event bus, per-tenant activation) | P2 |
| F3 | Route optimization (suggest optimal stop order based on student locations) | P3 |
| F4 | Driver behavior analytics (speed, harsh braking from GPS data) | P3 |
| F5 | Parent feedback / rating system | P3 |
| F6 | SMS notifications (via Twilio/MSG91 for critical alerts) | P3 |
| F7 | Student RFID/QR attendance (scan-based boarding confirmation) | P3 |
| F8 | Sibling management (one parent, multiple children, different routes) | P3 |
| F9 | Substitute driver assignment (handle driver absence) | P3 |
| F10 | Historical trip replay (playback any trip on map) | P3 |
| F11 | White-label / custom branding per school | P3 |
| F12 | Mobile native app (React Native, share 80% code) | P3 |
| F13 | AI-powered route optimization based on traffic patterns | P4 |

---

## 6. Database Schema

### 6.1 Key Tables / Models

```
+---------------------------------------------------------------+
|                        CORE MODELS                             |
+---------------------------------------------------------------+
|                                                                |
|  schools                         users                         |
|  --------                        -----                         |
|  id (PK, UUID)                   id (PK, UUID)                 |
|  name                            email (unique)                |
|  address                         password_hash                 |
|  phone                           full_name                     |
|  email                           phone                         |
|  logo_url                        role (enum: parent, driver,   |
|  settings (JSONB)                      school_admin,           |
|  is_active                             super_admin)            |
|  created_at                      school_id (FK -> schools)     |
|  updated_at                      is_active                     |
|                                  avatar_url                    |
|                                  push_subscription (JSONB)     |
|                                  notification_prefs (JSONB)    |
|                                  created_at                    |
|                                  updated_at                    |
|                                                                |
|  students                        vehicles                      |
|  --------                        --------                      |
|  id (PK, UUID)                   id (PK, UUID)                 |
|  full_name                       school_id (FK -> schools)     |
|  grade                           plate_number                  |
|  section                         vehicle_type (enum: bus, van, |
|  parent_id (FK -> users)                       car, minibus)  |
|  school_id (FK -> schools)       capacity                      |
|  pickup_address                  make                          |
|  pickup_location (PostGIS POINT) model                         |
|  is_active                       year                          |
|  created_at                      insurance_expiry              |
|                                  fitness_expiry                |
|                                  is_active                     |
|                                  created_at                    |
|                                                                |
+---------------------------------------------------------------+
|                   ROUTING & ASSIGNMENT                          |
+---------------------------------------------------------------+
|                                                                |
|  routes                          route_stops                   |
|  ------                          -----------                   |
|  id (PK, UUID)                   id (PK, UUID)                 |
|  school_id (FK -> schools)       route_id (FK -> routes)       |
|  name                            name                          |
|  description                     location (PostGIS POINT)      |
|  vehicle_id (FK -> vehicles)     address                       |
|  driver_id (FK -> users)         stop_order (int)              |
|  route_path (PostGIS LINESTRING) arrival_time (TIME)           |
|  schedule_type (enum: morning,   created_at                    |
|                evening, both)                                  |
|  is_active                                                     |
|  version (INT DEFAULT 1)         -- optimistic locking         |
|  created_at                      student_route_assignments     |
|                                  --------------------------    |
|                                  id (PK, UUID)                 |
|  transport_requests              student_id (FK -> students)   |
|  -------------------             route_id (FK -> routes)       |
|  id (PK, UUID)                   stop_id (FK -> route_stops)   |
|  parent_id (FK -> users)         assigned_at                   |
|  student_id (FK -> students)     is_active                     |
|  school_id (FK -> schools)                                     |
|  pickup_address                                                |
|  pickup_location (PostGIS POINT)                               |
|  status (enum: pending,                                        |
|          approved, rejected,                                   |
|          assigned)                                             |
|  assigned_route_id (FK -> routes)                              |
|  assigned_stop_id (FK -> route_stops)                          |
|  admin_notes                                                   |
|  created_at                                                    |
|  updated_at                                                    |
|                                                                |
+---------------------------------------------------------------+
|                      TRIP & GPS                                |
+---------------------------------------------------------------+
|                                                                |
|  trips                           gps_logs                      |
|  -----                           --------                      |
|  id (PK, UUID)                   id (PK, BIGSERIAL)            |
|  route_id (FK -> routes)         trip_id (FK -> trips)         |
|  driver_id (FK -> users)         location (PostGIS POINT)      |
|  vehicle_id (FK -> vehicles)     speed (float, km/h)           |
|  status (enum: scheduled,        heading (float, degrees)      |
|          in_progress,            accuracy (float, meters)      |
|          completed,              recorded_at (TIMESTAMPTZ)     |
|          cancelled,              created_at                    |
|          incident)                                             |
|  scheduled_date (DATE)           INDEX: (trip_id, recorded_at) |
|  started_at (TIMESTAMPTZ)        PARTITION: by month on        |
|  ended_at (TIMESTAMPTZ)                     recorded_at        |
|  created_at                                                    |
|                                                                |
|  attendance_records (V2)                                       |
|  ----------------------                                        |
|  id (PK, UUID)                                                 |
|  trip_id (FK -> trips)                                         |
|  student_id (FK -> students)                                   |
|  stop_id (FK -> route_stops)                                   |
|  status (enum: boarded, absent, late)                          |
|  marked_at (TIMESTAMPTZ)                                       |
|  marked_location (PostGIS POINT)                               |
|  created_at                                                    |
|                                                                |
+---------------------------------------------------------------+
|                   AUTHENTICATION                               |
+---------------------------------------------------------------+
|                                                                |
|  refresh_tokens                                                |
|  ---------------                                               |
|  id (PK, UUID)                                                 |
|  user_id (FK -> users)                                         |
|  token_hash (VARCHAR, indexed)                                 |
|  device_id (VARCHAR)                                           |
|  family_id (UUID, indexed)  -- token family for theft detection|
|  issued_at (TIMESTAMPTZ)                                       |
|  expires_at (TIMESTAMPTZ)                                      |
|  revoked_at (TIMESTAMPTZ, nullable)                            |
|  created_at                                                    |
|                                                                |
|  INDEX: (token_hash)                                           |
|  INDEX: (user_id, revoked_at)                                  |
|  INDEX: (family_id)                                            |
|                                                                |
+---------------------------------------------------------------+
|                   COMMUNICATION (V2)                           |
+---------------------------------------------------------------+
|                                                                |
|  conversations                   messages                      |
|  -------------                   --------                      |
|  id (PK, UUID)                   id (PK, UUID)                 |
|  school_id (FK -> schools)       conversation_id (FK)          |
|  type (enum: parent_admin,       sender_id (FK -> users)       |
|              parent_driver,      content (TEXT)                 |
|              broadcast)          is_read (BOOL)                |
|  route_id (FK, nullable)         created_at                    |
|  is_active                                                     |
|  created_at                                                    |
|                                                                |
|  conversation_participants       (replaces participant_ids     |
|  ----------------------------     UUID[] array)                |
|  id (PK, UUID)                                                 |
|  conversation_id (FK -> conversations)                         |
|  user_id (FK -> users)                                         |
|  joined_at (TIMESTAMPTZ)                                       |
|  INDEX: (conversation_id, user_id) UNIQUE                      |
|  INDEX: (user_id)                                              |
|                                                                |
|  alerts (V2)                                                   |
|  ----------                                                    |
|  id (PK, UUID)                                                 |
|  school_id (FK -> schools)                                     |
|  trip_id (FK -> trips, nullable)                               |
|  type (enum: sos, route_deviation, incident,                   |
|              driver_no_show, vehicle_issue,                     |
|              insurance_expiry)                                  |
|  severity (enum: critical, high, medium, low)                  |
|  title                                                         |
|  description                                                   |
|  triggered_by (FK -> users)                                    |
|  acknowledged_by (FK -> users, nullable)                       |
|  acknowledged_at (TIMESTAMPTZ, nullable)                       |
|  resolved_at (TIMESTAMPTZ, nullable)                           |
|  location (PostGIS POINT, nullable)                            |
|  metadata (JSONB)                                              |
|  created_at                                                    |
|                                                                |
+---------------------------------------------------------------+
|                      PAYMENTS (V2)                             |
+---------------------------------------------------------------+
|                                                                |
|  fee_schedules                   invoices                      |
|  --------------                  --------                      |
|  id (PK, UUID)                   id (PK, UUID)                 |
|  school_id (FK -> schools)       school_id (FK -> schools)     |
|  route_id (FK, nullable)         parent_id (FK -> users)       |
|  name                            student_id (FK -> students)   |
|  amount (DECIMAL 10,2)           fee_schedule_id (FK)          |
|  currency (default: INR)         amount (DECIMAL 10,2)         |
|  billing_cycle (enum: one_time,  status (enum: draft, sent,    |
|          monthly, quarterly,              paid, overdue,       |
|          term, annual)                    cancelled)           |
|  effective_from (DATE)           due_date (DATE)               |
|  effective_to (DATE, nullable)   paid_at (TIMESTAMPTZ, nullable|
|  is_active                       created_at                    |
|  created_at                                                    |
|                                  payments                      |
|                                  --------                      |
|                                  id (PK, UUID)                 |
|                                  invoice_id (FK -> invoices)   |
|                                  amount (DECIMAL 10,2)         |
|                                  currency                      |
|                                  gateway (enum: razorpay,      |
|                                          stripe, manual,       |
|                                          offline)             |
|                                  gateway_payment_id (nullable) |
|                                  gateway_order_id (nullable)   |
|                                  status (enum: pending,        |
|                                          completed, failed,    |
|                                          refunded)            |
|                                  receipt_url (nullable)        |
|                                  metadata (JSONB)              |
|                                  created_at                    |
|                                                                |
+---------------------------------------------------------------+
|                   AUDIT & SYSTEM                               |
+---------------------------------------------------------------+
|                                                                |
|  audit_logs                      notification_logs             |
|  ----------                      ------------------            |
|  id (PK, BIGSERIAL)             id (PK, UUID)                 |
|  school_id (FK)                  user_id (FK -> users)         |
|  user_id (FK -> users)           type (enum: push, email,      |
|  action (VARCHAR)                        sms, in_app)         |
|  entity_type (VARCHAR)           title                         |
|  entity_id (UUID)                body                          |
|  old_values (JSONB)              is_read (BOOL)                |
|  new_values (JSONB)              sent_at                       |
|  ip_address                      read_at (nullable)            |
|  created_at                      created_at                    |
|                                                                |
+---------------------------------------------------------------+
```

### 6.2 Key Indexes

```sql
-- Geospatial indexes
CREATE INDEX idx_route_stops_location ON route_stops USING GIST (location);
CREATE INDEX idx_students_pickup ON students USING GIST (pickup_location);
CREATE INDEX idx_gps_logs_location ON gps_logs USING GIST (location);

-- Query performance indexes
CREATE INDEX idx_trips_status_date ON trips (status, scheduled_date);
CREATE INDEX idx_trips_route_date ON trips (route_id, scheduled_date);
CREATE INDEX idx_gps_logs_trip_time ON gps_logs (trip_id, recorded_at DESC);
CREATE INDEX idx_attendance_trip ON attendance_records (trip_id);
CREATE INDEX idx_attendance_student ON attendance_records (student_id, created_at DESC);
CREATE INDEX idx_alerts_school_severity ON alerts (school_id, severity, created_at DESC);
CREATE INDEX idx_invoices_parent_status ON invoices (parent_id, status);
CREATE INDEX idx_messages_conversation ON messages (conversation_id, created_at DESC);
CREATE INDEX idx_users_school_role ON users (school_id, role);
CREATE INDEX idx_notification_logs_user ON notification_logs (user_id, is_read, created_at DESC);

-- Auth indexes
CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens (token_hash);
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens (user_id, revoked_at);
CREATE INDEX idx_refresh_tokens_family ON refresh_tokens (family_id);

-- Conversation participants
CREATE UNIQUE INDEX idx_conv_participants_unique ON conversation_participants (conversation_id, user_id);
CREATE INDEX idx_conv_participants_user ON conversation_participants (user_id);

-- Partitioning (gps_logs - high volume)
-- Partition gps_logs by month on recorded_at for efficient cleanup and querying
-- Daily Celery job drops partitions older than 90 days
```

### 6.3 Multi-Tenancy Strategy

**MVP (Single School):** All data belongs to one school. `school_id` column exists on all tables for forward-compatibility but is not enforced via RLS. Application-level filtering:

```python
# Every query scoped by school_id (from JWT claims)
def get_vehicles(db: Session, school_id: UUID):
    return db.query(Vehicle).filter(Vehicle.school_id == school_id).all()
```

**V2 (Multi-School):** Enable PostgreSQL RLS as defense-in-depth:

```sql
ALTER TABLE vehicles ENABLE ROW LEVEL SECURITY;
CREATE POLICY school_isolation ON vehicles
    USING (school_id = current_setting('app.current_school_id')::UUID);
```

---

## 7. API Design

### 7.1 Base URL Structure

```
/api/v1/                    # REST API (all routes prefixed)
/ws/                        # WebSocket / Socket.IO
/health                     # Health check endpoint
```

**API Versioning:** All routes use `/api/v1/` prefix. When breaking changes are needed, add `/api/v2/` router alongside. No URL rewriting.

**CORS Configuration:** `allow_origins=[settings.FRONTEND_URL]` in FastAPI CORS middleware. Do not use wildcard `*` in production.

### 7.2 Authentication

```
POST   /api/v1/auth/register            # Register new user (parent self-reg, admin creates others)
POST   /api/v1/auth/login               # Login -> {access_token} + Set-Cookie: refresh_token (HttpOnly, Secure, SameSite=Strict)
POST   /api/v1/auth/refresh             # Refresh access token (reads refresh_token from HttpOnly cookie, rotates it)
POST   /api/v1/auth/logout              # Invalidate refresh token family
POST   /api/v1/auth/forgot-password     # Send reset email
POST   /api/v1/auth/reset-password      # Reset with token
GET    /api/v1/auth/me                  # Current user profile
PUT    /api/v1/auth/me                  # Update profile
```

**JWT Security Details:**
- Access tokens: 15-minute expiry. Include `user_id`, `school_id`, `role` claims for stateless RBAC. Sent via `Authorization: Bearer` header.
- Refresh tokens: stored in `HttpOnly, Secure, SameSite=Strict` cookies. **NEVER in localStorage.**
- Refresh token rotation: each use issues a new refresh token + invalidates the old one.
- Refresh token family: if a rotated-out token is reused, invalidate entire family (theft detection).
- `refresh_tokens` table: `(id, user_id, token_hash, device_id, issued_at, expires_at, revoked_at, family_id)`.
- Account lockout: after 5 failed login attempts, lock account for 15 minutes. Track in Redis: `login_attempts:{user_id}` with TTL.

### 7.3 Schools

```
POST   /api/v1/schools                  # Create school (super admin, V2)
GET    /api/v1/schools                  # List schools (super admin, V2)
GET    /api/v1/schools/{id}             # Get school details
PUT    /api/v1/schools/{id}             # Update school
PUT    /api/v1/schools/{id}/settings    # Update school settings
```

### 7.4 Vehicles

```
POST   /api/v1/vehicles                 # Register vehicle
GET    /api/v1/vehicles                 # List vehicles (school-scoped)
GET    /api/v1/vehicles/{id}            # Get vehicle details
PUT    /api/v1/vehicles/{id}            # Update vehicle
DELETE /api/v1/vehicles/{id}            # Deactivate vehicle (soft delete)
```

### 7.5 Drivers

```
GET    /api/v1/drivers                  # List drivers (school-scoped)
POST   /api/v1/drivers/{id}/assign      # Assign driver to vehicle
GET    /api/v1/drivers/{id}/schedule    # Get driver's schedule
GET    /api/v1/drivers/{id}/trips       # Get driver's trip history
```

### 7.6 Routes & Stops

```
POST   /api/v1/routes                   # Create route
GET    /api/v1/routes                   # List routes (school-scoped)
GET    /api/v1/routes/{id}              # Get route with stops
PUT    /api/v1/routes/{id}              # Update route
DELETE /api/v1/routes/{id}              # Deactivate route

POST   /api/v1/routes/{id}/stops        # Add stop to route
PUT    /api/v1/routes/{id}/stops/{stop_id}  # Update stop
DELETE /api/v1/routes/{id}/stops/{stop_id}  # Remove stop
PUT    /api/v1/routes/{id}/stops/reorder    # Reorder stops

GET    /api/v1/routes/{id}/students     # Students assigned to route
POST   /api/v1/routes/{id}/students     # Assign student to route+stop
```

### 7.7 Transport Requests

```
POST   /api/v1/transport-requests       # Parent submits request
GET    /api/v1/transport-requests       # List requests (admin: all pending; parent: own)
GET    /api/v1/transport-requests/{id}  # Get request details
PUT    /api/v1/transport-requests/{id}  # Admin: approve/reject/assign
GET    /api/v1/transport-requests/suggest-stop?lat=x&lng=y&school_id=z
                                        # Suggest nearest stop for pickup location
```

**Suggest Nearest Stop Implementation:**
- Parent enters street address -> Nominatim geocodes (dev) / MapTiler geocodes (production) -> `ST_Distance` query against `route_stops` -> return top 3 nearest stops with distance in meters.

### 7.8 Trips & GPS

```
POST   /api/v1/trips                    # Create/schedule trip (admin or auto-generated)
GET    /api/v1/trips                    # List trips (filterable by date, route, status)
GET    /api/v1/trips/{id}               # Get trip details
PUT    /api/v1/trips/{id}/start         # Driver starts trip
PUT    /api/v1/trips/{id}/end           # Driver ends trip
PUT    /api/v1/trips/{id}/cancel        # Cancel trip
GET    /api/v1/trips/{id}/gps-log       # Historical GPS trace for trip
GET    /api/v1/trips/active             # All currently active trips (admin dashboard)
```

### 7.9 Attendance (V2)

```
POST   /api/v1/trips/{trip_id}/attendance           # Mark attendance (driver)
GET    /api/v1/trips/{trip_id}/attendance           # Get attendance for trip
GET    /api/v1/students/{student_id}/attendance     # Student attendance history
GET    /api/v1/students/{student_id}/attendance/export?format=csv  # Export
```

### 7.10 Alerts & SOS (V2)

```
POST   /api/v1/alerts/sos               # Parent triggers SOS
POST   /api/v1/alerts/incident          # Driver reports incident
GET    /api/v1/alerts                    # List alerts (admin, filterable)
PUT    /api/v1/alerts/{id}/acknowledge   # Admin acknowledges alert
PUT    /api/v1/alerts/{id}/resolve       # Admin resolves alert
```

### 7.11 Communication (V2)

```
POST   /api/v1/conversations            # Start new conversation
GET    /api/v1/conversations            # List user's conversations
GET    /api/v1/conversations/{id}       # Get conversation with messages
POST   /api/v1/conversations/{id}/messages  # Send message
PUT    /api/v1/messages/{id}/read       # Mark message as read

POST   /api/v1/broadcasts               # Admin sends broadcast
GET    /api/v1/broadcasts               # List broadcasts (admin)
```

### 7.12 Payments (V2 Structure Only)

```
GET    /api/v1/fee-schedules             # List fee schedules
POST   /api/v1/fee-schedules             # Create fee schedule (admin)
PUT    /api/v1/fee-schedules/{id}        # Update fee schedule

GET    /api/v1/invoices                  # List invoices (parent: own, admin: all)
POST   /api/v1/invoices                  # Generate invoice (admin)
POST   /api/v1/invoices/bulk-generate    # Bulk generate for route/school

POST   /api/v1/payments/initiate         # Create payment order (Future: Razorpay/Stripe)
POST   /api/v1/payments/verify           # Verify payment callback
GET    /api/v1/payments/{id}/receipt      # Download receipt
POST   /api/v1/payments/webhook          # Gateway webhook handler
```

### 7.13 Analytics (V2, Admin)

```
GET    /api/v1/analytics/dashboard       # Dashboard summary stats
GET    /api/v1/analytics/routes          # Route efficiency metrics
GET    /api/v1/analytics/attendance      # Attendance statistics
GET    /api/v1/analytics/trips           # Trip history & on-time stats
GET    /api/v1/analytics/payments        # Revenue & collection stats
```

### 7.14 Notifications

```
GET    /api/v1/notifications             # User's notifications (paginated)
PUT    /api/v1/notifications/{id}/read   # Mark as read
PUT    /api/v1/notifications/read-all    # Mark all as read
POST   /api/v1/notifications/subscribe   # Save push subscription (VAPID) (V2)
DELETE /api/v1/notifications/subscribe   # Unsubscribe from push (V2)
PUT    /api/v1/notifications/preferences # Update notification preferences (V2)
```

### 7.15 WebSocket Events (Socket.IO)

```
# Client -> Server
"join_trip"          {trip_id}               # Parent subscribes to trip updates
"leave_trip"         {trip_id}               # Parent unsubscribes
"location_update"    {trip_id, lat, lng, speed, heading, accuracy, timestamp}  # Driver sends GPS
"location_batch"     {trip_id, points: [...]}  # Driver sends buffered offline points (V2)
"chat_message"       {conversation_id, content}  # Send chat message (V2)
"typing"             {conversation_id}       # Typing indicator (V2)

# Server -> Client
"location_update"    {trip_id, lat, lng, speed, heading, timestamp, eta_next_stop}
"bus_approaching"    {trip_id, stop_id, distance_meters, eta_seconds}
"trip_started"       {trip_id, driver_name, vehicle_plate}
"trip_ended"         {trip_id}
"tracking_paused"    {trip_id, last_known_lat, last_known_lng, last_updated_at}
"attendance_update"  {trip_id, student_id, status}  # V2
"route_deviation"    {trip_id, distance_from_route_meters}  # V2, Admin only
"alert_new"          {alert}                 # V2, Admin: new alert
"chat_message"       {conversation_id, message}  # V2
"typing"             {conversation_id, user_id}  # V2
"notification"       {notification}          # Generic notification
```

### 7.16 WebSocket Security

- **Connection auth:** Socket.IO connection handshake must include JWT access token in query param: `?token={access_token}` (header not supported by some proxies).
- **Server validation:** Server validates token on `connect` event. Disconnect if invalid: `raise ConnectionRefusedError('unauthorized')`.
- **Room authorization on `join_trip`:** Verify `user.student.route_id == trip.route_id` OR user is driver of trip OR user is school admin. Reject unauthorized joins.
- **Rate limiting:** Max 1 `location_update` per 3 seconds per connection (Redis sliding window). Drop excess updates silently.
- **Driver identity check:** Reject `location_update` from connections not authenticated as the trip's assigned driver.
- **Token expiry:** If access token expires during active connection, server emits `"token_expired"` event. Client must reconnect with a fresh token (obtained via refresh endpoint).

### 7.17 Health Check

```
GET    /health                          # Returns: {status: "ok", db: "connected", redis: "connected", last_gps_event_at: "2026-05-26T10:00:00Z"}
```

---

## 8. Task Breakdown - Phased Implementation

### Phase 1: Foundation (Weeks 1-3)

**Step 1: Project Scaffolding & Core Infrastructure**
- Set up monorepo structure (backend + frontend)
- Docker Compose: FastAPI + PostgreSQL/PostGIS + Redis
- FastAPI project structure with modular monolith directory layout (NOT plugin architecture)
- SQLAlchemy 2.0 async setup with connection pool settings: `pool_size=20, max_overflow=10, pool_timeout=30`
- Alembic migrations
- Pydantic settings management (env-based config)
- Ruff linting + pre-commit hooks
- pytest setup with async fixtures + test factory module (`tests/factories.py`)
- CI/CD pipeline (GitHub Actions: lint, test, build)
- Sentry integration (Python SDK, 1-hour setup)
- structlog setup for JSON structured logging with `request_id`, `user_id`, `school_id`
- Health check endpoint: `GET /health` returns DB connectivity + Redis connectivity + last GPS event timestamp
- CORS middleware: `allow_origins=[settings.FRONTEND_URL]`
- **Acceptance:** `docker compose up` starts all services. `pytest` runs with 0 errors. Alembic creates tables. `/health` returns 200 with DB + Redis status. Structured JSON logs appear in stdout.

**Step 2: Authentication & User Management**
- JWT auth with access tokens (15-min expiry) containing `user_id`, `school_id`, `role` claims
- Refresh tokens stored in HttpOnly, Secure, SameSite=Strict cookies (NEVER localStorage)
- Refresh token rotation: each use issues new token + invalidates old
- Refresh token family tracking: reuse of rotated-out token invalidates entire family (theft detection)
- `refresh_tokens` table: `(id, user_id, token_hash, device_id, issued_at, expires_at, revoked_at, family_id)`
- User registration (email + password, bcrypt hashing)
- Role-based access control middleware (parent, driver, school_admin, super_admin)
- Login, logout, token refresh endpoints
- Account lockout: after 5 failed login attempts, lock for 15 minutes (tracked in Redis: `login_attempts:{user_id}` with TTL)
- Password reset flow (email-based)
- User profile CRUD
- **Acceptance:** All auth endpoints pass integration tests. RBAC correctly restricts access. Refresh token rotation works -- reuse of old token invalidates family. Account locks after 5 failures, unlocks after 15min. Access tokens include school_id and role claims.

**Step 3: Multi-School Setup & Entity CRUD**
- School model + CRUD (super admin creates/manages schools)
- Super admin role: can see all schools, create school admins, manage platform settings
- school_id on all tables — application-level filtering via JWT `school_id` claim (middleware extracts + injects into every query)
- PostgreSQL RLS policies as defense-in-depth: `CREATE POLICY school_isolation ON vehicles USING (school_id = current_setting('app.current_school_id')::UUID)` — enforced at DB level even if app code has a bug
- School settings (JSONB, feature flags: `payments_enabled`, `chat_enabled`, `driver_direct_chat`)
- Vehicle CRUD with validation (plate uniqueness per school, capacity)
- Driver management (user with role=driver, assign to vehicle)
- Route CRUD with PostGIS LINESTRING for route path
- Route stops with PostGIS POINT, ordered by stop_order
- Stop reordering endpoint
- Student registration (by parent) + student-route-stop assignment
- Transport request workflow (parent requests -> admin reviews -> assigns)
- Nearest-stop suggestion: parent enters address -> geocode -> `ST_Distance` query against route_stops -> return top 3 nearest stops
- **Acceptance:** Full CRUD works for all entities. Transport request flow completes end-to-end. Nearest stop returns correct result within 1km radius. Data created under School A is invisible to School B users. RLS policy blocks cross-tenant query even with raw SQL (verify via `psql`). Super admin can create and switch between schools.

### Phase 2: Core GPS & Frontend (Weeks 4-6)

**Step 4: Trip Management & Real-Time GPS Tracking**
- Trip model + scheduling: admin clicks "Generate Today's Trips" button to create trips from active routes. Optionally a daily Celery beat task at 6AM creates next-day trips automatically (configurable via school settings).
- Start/end trip endpoints (driver only)
- Socket.IO server mounted on FastAPI ASGI app (single process, NOT separate service)
- Socket.IO connection auth: validate JWT from `?token=` query param on connect. Reject invalid/expired tokens.
- Room authorization: `join_trip` verifies user's student is assigned to trip's route, OR user is trip's driver, OR user is school admin
- Rate limiting on `location_update`: max 1 per 3 seconds per connection (Redis sliding window)
- Reject `location_update` from non-driver connections
- Driver GPS ingestion via Socket.IO ("location_update" event)
- Room-based broadcasting (trip:{trip_id} room)
- Redis GPS buffer (batch write to PostgreSQL every 30s via asyncio background task started on app startup — NOT Celery, keeps GPS writes in-process and avoids cross-process coordination)
- Parent subscribes to trip -> receives live location updates
- ETA calculation (straight-line distance to next stop / average speed). Note: road-distance ETA is V2. MVP shows "~X min (approx)" with disclaimer in UI.
- GPS log storage with monthly partitioning
- "Tracking paused" state: when no GPS update received for >30s, emit `tracking_paused` event with last-known position and staleness timestamp to all room subscribers
- **Acceptance:** Driver shares location, parent sees bus update within 1s latency. GPS logs persist in PostgreSQL. ETA displayed and updates. Unauthorized Socket.IO connections rejected. Rate limiting enforced. Stale GPS shows "tracking paused" indicator.

**Step 5: Frontend MVP - Parent & Driver Views**
- React + Vite project setup with Tailwind + shadcn/ui
- Sentry React SDK integration
- Authentication pages (login, register, forgot password)
- Parent dashboard: assigned route, upcoming trips, live map
- Driver dashboard: today's route, stop list, "Start Trip" button (with "keep screen on" warning for MVP)
- Live tracking map (react-leaflet + Socket.IO client)
- Map tiles: OpenStreetMap for dev, Stadia Maps or MapTiler for production (add tile provider config)
- Graceful degradation: when WebSocket fails, show "Connecting..." state. Core data (routes, schedules) accessible via REST.
- "Tracking paused" visual indicator when GPS data is stale
- In-app notifications: trip started, trip ended (Socket.IO events rendered in UI)
- Basic admin view: active trips on map with bus markers
- Responsive design (mobile-first)
- **Acceptance:** Parent can register, see assigned route, track live bus. Driver can start trip and share location. Works on mobile Chrome/Safari. Stale GPS shows clear "tracking paused" indicator. WebSocket disconnection shows meaningful loading state.

**Step 6: Integration Testing & Demo Polish**
- Integration tests: auth flow, vehicle CRUD, route CRUD, trip start/end, GPS event handling (httpx + pytest-asyncio with real PostgreSQL test DB via Docker)
- Test data seeding: `tests/factories.py` with pytest fixtures for school, vehicle, route, driver user, parent user, student
- End-to-end demo flow testing: admin creates vehicle + route, parent registers + requests + gets assigned, driver starts trip + shares GPS, parent sees bus on map
- Bug fixes and polish from integration testing
- GitHub Actions CI gate: pytest on every PR, coverage report, block merge if <70% on new code
- **Acceptance:** All integration tests pass. Demo flow works end-to-end in one browser session. CI pipeline green. Coverage >70% on business logic.

---

**Week 6 Demo Success Criteria:**

Admin registers a vehicle + route. Parent requests transport and gets assigned to a stop. Driver starts trip and shares GPS. Parent sees bus moving on Leaflet map with ETA. End-to-end in one browser session.

---

### V2 Phase: Production Features (Weeks 7-14)

**Step 7: Multi-Tenancy & Security Hardening**
- PostgreSQL RLS policies for school isolation
- Super admin role + school CRUD
- school_id scoping middleware (defense-in-depth with RLS)
- Security audit (OWASP top 10 checklist)
- Rate limiting hardening (Caddy or FastAPI middleware)
- **Acceptance:** Creating data under School A is invisible to School B. RLS policies enforced at DB level.

**Step 8: Capacitor Driver App + Background GPS**
- Capacitor.js project wrapping existing React driver view
- `@capacitor/geolocation` plugin replacing browser Geolocation API for driver role
- Background location tracking (works when phone locked)
- APK build for Android testing
- **Acceptance:** Driver app tracks GPS in background with screen off. Same React codebase, compiled to APK.

**Step 9: Route Deviation, Notifications & Alerts**
- Route deviation detection (synchronous in Socket.IO handler):
  - On trip start: compute `ST_Buffer(route_path, 500m)`, cache corridor geometry in Redis key `corridor:{trip_id}`
  - Every GPS update: `ST_DWithin(current_pos, cached_corridor, 500m)` -- sub-millisecond with cached geometry
  - If outside corridor for 2 consecutive updates: enqueue Celery task ONLY for notification dispatch
- Web Push setup (VAPID keys, pywebpush)
- Push subscription save/delete endpoints
- "Bus approaching" notification (PostGIS proximity trigger)
- SOS button + driver incident reporting
- Alert dashboard (admin: list, acknowledge, resolve)
- In-app notification center (bell icon, unread count, mark read)
- **Acceptance:** Route deviation detected and alerted within 5 seconds of GPS update that exceeds corridor boundary. Push notifications work on Chrome/Firefox. SOS creates alert visible to admin within 2s.

**Step 10: Communication & Attendance**
- Conversation model with `conversation_participants` junction table
- Parent-to-admin chat (threaded) via Socket.IO
- Admin broadcast announcements
- Student attendance marking (driver UI at each stop)
- Attendance notification to parent (real-time via Socket.IO)
- Attendance history view + CSV export
- **Acceptance:** Messages delivered in real-time. Attendance marks notify parents instantly. CSV export works.

**Step 11: Admin Dashboard, Analytics & Payments**
- Admin dashboard (fleet overview, active trips map, alert panel, key metrics)
- Analytics: route efficiency, attendance rates, trip history
- Chart visualizations (Recharts)
- Fee schedule CRUD + invoice generation
- Payment model with gateway abstraction
- Manual/offline payment recording
- **Acceptance:** Dashboard loads in <2s. Analytics data matches raw DB queries. Invoices generated correctly.

**Step 12: E2E Tests & Production Hardening**
- Playwright E2E tests: two browser sessions (driver + parent), driver starts trip + shares GPS, parent sees bus moving. ~5 critical user flows.
- Offline GPS buffering (IndexedDB on driver, sync on reconnect)
- Load testing (locust: 500 concurrent users, 50 active trips)
- Database query optimization (EXPLAIN ANALYZE on critical queries)
- Docker production config (multi-stage build, health checks)
- Deployment documentation
- **Acceptance:** E2E tests pass. Load test passes at 500 concurrent users. Offline sync works after 5-minute disconnect.

---

## 9. Hosting Strategy

### Architecture Note

FastAPI + Socket.IO run in the **SAME ASGI process** -- `python-socketio`'s `ASGIApp` mounts directly onto the FastAPI application. This is NOT two separate services. This keeps hosting simple and cost-effective.

### Tier 1: Development / Demo ($0/mo)

| Component | Service | Cost | Limits |
|-----------|---------|------|--------|
| Backend | Render (free tier) | $0 | 512MB RAM, sleeps after 15min inactivity |
| Database | Neon (free tier) | $0 | 0.5GB storage, 190 compute hours/mo |
| Redis | Upstash (free tier) | $0 | 10,000 commands/day, 256MB |
| Frontend | Cloudflare Pages | $0 | Unlimited bandwidth, 500 builds/mo |
| File Storage | Cloudflare R2 | $0 | 10GB storage, 10M reads/mo |
| DNS/SSL | Cloudflare | $0 | Free plan |

**Limitations:** Cold starts make WebSocket impractical. Good for demos and development only.

### Tier 2: Production MVP (~$12-18/mo)

| Component | Service | Cost | Capacity |
|-----------|---------|------|----------|
| Backend (FastAPI + Socket.IO, single ASGI process) | Railway (single app service) | $5-10/mo | 1GB RAM, always-on, auto-deploy |
| Database (PostgreSQL + PostGIS) | Railway PostgreSQL addon | $5/mo | 1GB storage, managed backups. **⚠️ PostGIS note:** Railway's default PG template does NOT include PostGIS. Use a custom Dockerfile: `FROM postgres:16` + `RUN apt-get install -y postgresql-16-postgis-3` OR deploy via Railway's community PostGIS template. Verify with `SELECT PostGIS_Version();` before Phase 1 completes. Fallback: Neon (free, PostGIS enabled by default) or Supabase (free, PostGIS enabled). |
| Redis | Railway Redis addon | $2-3/mo | 256MB, persistent |
| Frontend | Cloudflare Pages | $0 | Same as Tier 1 |
| File Storage | Cloudflare R2 | $0 | Same as Tier 1 |
| DNS/SSL | Cloudflare | $0 | Same as Tier 1 |
| Error Tracking | Sentry (free tier) | $0 | 5,000 errors/mo |
| Uptime Monitoring | UptimeRobot (free tier) | $0 | 50 monitors, 5-min intervals |
| **Total** | | **~$12-18/mo** | **~500 concurrent users** |

### Tier 3: Growth ($25-50/mo)

| Component | Service | Cost | Capacity |
|-----------|---------|------|----------|
| All-in-one VPS | Hetzner CX22 (2 vCPU, 4GB RAM) | EUR 4.50/mo (~$5) | Docker Compose: app + DB + Redis |
| OR split: App VPS | Hetzner CX11 (1 vCPU, 2GB) | EUR 3.50/mo | FastAPI + Socket.IO + Celery |
| + Managed DB | Neon Pro or Supabase Pro | $25/mo | 10GB, auto-backups, branching |
| Frontend | Cloudflare Pages | $0 | Same |
| File Storage | Cloudflare R2 | $0 | Same |
| CDN | Cloudflare | $0 | Same |
| **Total** | | **~$5-30/mo** | **~2,000-5,000 concurrent** |

### Tier 4: Scale ($50-150/mo)

| Component | Service | Cost |
|-----------|---------|------|
| App (2 instances) | Hetzner CX22 x2 behind load balancer | $10/mo |
| Database | Hetzner managed PostgreSQL or Supabase Pro | $25-50/mo |
| Redis | Hetzner managed or Upstash Pro | $10/mo |
| File Storage | Cloudflare R2 | $0-5/mo |
| Load Balancer | Hetzner LB | $5/mo |
| **Total** | | **~$50-80/mo for 10,000+ users** |

### Monitoring & Observability (All Tiers)

| Component | Tool | Cost | Details |
|-----------|------|------|---------|
| **Error tracking** | Sentry | $0 (free tier: 5,000 errors/mo) | Python SDK + React SDK. 1-hour setup. |
| **Health check** | Custom endpoint | $0 | `GET /health` returns DB connectivity + Redis connectivity + last GPS event timestamp. |
| **Structured logging** | structlog (MIT) | $0 | JSON logs with `request_id`, `user_id`, `school_id` per request. |
| **Uptime monitoring** | UptimeRobot | $0 (free tier) | Pings `/health` every 5 minutes. Email alert on downtime. |
| **No dedicated metrics for MVP** | -- | -- | Sentry + structured logs are sufficient. Add Prometheus/Grafana in V2 if needed. |

### Scaling Path (No Architecture Changes)

```
Single instance (Tier 2, ~$12-18/mo)
    |
    | Add Redis adapter to Socket.IO (already in architecture)
    v
Horizontal scale: 2-3 app instances behind load balancer (Tier 4)
    |
    | Move DB to managed service, add read replica
    v
Vertical scale: bigger VPS (4 vCPU, 8GB) for $15/mo handles 5000+ concurrent
    |
    | Add CDN for static assets (already using Cloudflare)
    v
Microservice extraction: split GPS ingestion into separate service if needed
```

Key insight: PostgreSQL + PostGIS + Redis + FastAPI async can handle thousands of concurrent WebSocket connections on a single 2-4GB instance. Most school bus systems will never need more than Tier 3.

---

## 10. Payment Integration Plan

### 10.1 Day-1 Structure (No Gateway Required)

The payment module is built with a **gateway abstraction layer** ready for V2:

```python
# app/payments/gateways/base.py
class PaymentGateway(ABC):
    @abstractmethod
    async def create_order(self, amount: Decimal, currency: str, metadata: dict) -> OrderResult:
        pass

    @abstractmethod
    async def verify_payment(self, gateway_payment_id: str, gateway_order_id: str, signature: str) -> VerifyResult:
        pass

    @abstractmethod
    async def process_webhook(self, payload: bytes, headers: dict) -> WebhookResult:
        pass

    @abstractmethod
    async def initiate_refund(self, gateway_payment_id: str, amount: Decimal) -> RefundResult:
        pass
```

### 10.2 MVP Payment Flow (Manual/Offline) -- V2

```
Admin creates fee schedule -> System generates invoices
    -> Parent views invoice on dashboard
    -> Parent pays offline (cash/bank transfer)
    -> Admin marks invoice as "paid" (manual recording)
    -> Receipt generated (PDF)
```

### 10.3 Future Payment Flow (Gateway Integration)

```
Parent clicks "Pay Now" on invoice
    -> Backend calls gateway.create_order(amount, currency, metadata)
    -> Frontend receives order_id, opens gateway checkout (Razorpay/Stripe)
    -> Parent completes payment on gateway's hosted page
    -> Gateway redirects back + sends webhook
    -> Backend calls gateway.verify_payment(...)
    -> Invoice status updated to "paid"
    -> Receipt generated with transaction ID
    -> Parent + Admin notified
```

### 10.4 Financial Safety

- All amounts stored as `DECIMAL(10,2)` -- never float
- Currency stored with every record (support multi-currency future)
- Idempotency keys on all payment operations (prevent double-charge)
- Webhook signature verification mandatory
- Payment audit log (every status change logged with timestamp + actor)
- Refund flow built into abstraction (even if not exposed in V1 UI)
- No PCI data stored locally (gateway handles card data via hosted checkout)

---

## 11. Testing Strategy

### 11.1 Test Types

| Type | Framework | Target | Coverage Goal |
|------|-----------|--------|---------------|
| **Unit tests** | pytest + pytest-asyncio | Each service function tested in isolation with mocked DB | 80% coverage on business logic |
| **Integration tests** | pytest + httpx + real PostgreSQL (test DB via Docker) | API endpoints tested end-to-end: auth, vehicle CRUD, route CRUD, trip start/end, GPS event handling | Key flows fully covered |
| **E2E tests (V2)** | Playwright | Two browser sessions: driver + parent. Driver starts trip + shares GPS. Parent sees bus moving. ~5 critical user flows. | Critical paths covered |

### 11.2 Test Data Seeding

```python
# tests/factories.py
# Pytest fixtures for:
# - create_school() -> School
# - create_user(role="parent") -> User
# - create_vehicle(school) -> Vehicle
# - create_route(school, vehicle, driver) -> Route with stops
# - create_student(parent, school) -> Student
# - create_trip(route) -> Trip
```

### 11.3 Time Allocation

| Phase | Testing Focus |
|-------|---------------|
| Weeks 1-2 | Unit test fixtures + factory module. Auth integration tests. |
| Weeks 3-4 | Integration tests for every new endpoint added. |
| Weeks 5-6 | Full integration test suite for demo flow. CI gate enforced. |
| Weeks 7+ (V2) | Playwright E2E tests for critical paths. Load tests with locust. |

### 11.4 CI Gate

- GitHub Actions runs `pytest` on every PR
- Coverage report generated (pytest-cov)
- Block merge if coverage < 70% on new code
- Ruff linting must pass (zero warnings)

---

## 12. Monitoring & Observability

### 12.1 MVP Monitoring Stack (All Free)

| Component | Tool | Setup Time | Details |
|-----------|------|------------|---------|
| **Error tracking** | Sentry (free tier) | 1 hour | Python SDK catches unhandled exceptions. React SDK catches frontend errors. 5,000 errors/mo free. |
| **Health check endpoint** | Custom `/health` | 30 min | Returns JSON: `{status, db_connected, redis_connected, last_gps_event_at}`. Used by uptime monitor. |
| **Structured logging** | structlog (MIT) | 1 hour | Every request logged as JSON with `request_id`, `user_id`, `school_id`, `method`, `path`, `status_code`, `duration_ms`. |
| **Uptime monitoring** | UptimeRobot (free tier) | 15 min | Pings `GET /health` every 5 minutes. Email alert on 2 consecutive failures. |

### 12.2 V2 Monitoring Additions

- Prometheus + Grafana for metrics (WebSocket connection count, GPS events/sec, API latency percentiles)
- Alerting on: >10% error rate, >500ms p95 latency, 0 GPS events in 5 minutes during school hours
- Log aggregation (Loki or Papertrail free tier)

### 12.3 No Dedicated Metrics System for MVP

Sentry + structured JSON logs + `/health` endpoint + UptimeRobot are sufficient for a single-school MVP. Adding Prometheus/Grafana before product-market fit is premature optimization.

---

## Edge Cases & Mitigations

| Edge Case | Mitigation |
|-----------|------------|
| **Driver GPS pauses (browser background / screen lock)** | **MVP:** Show "Tracking paused" state on parent map with staleness timestamp. Warn driver to keep screen on. **V2:** Capacitor.js app with native geolocation -- works in background. |
| **Offline GPS (tunnel/rural)** | IndexedDB buffer on driver device (V2). Server shows "Tracking paused - Last updated X min ago" to parents. Batch sync on reconnect. |
| **Driver no-show** | If trip not started within 15min of schedule, auto-alert to admin. Admin can reassign or cancel. Parents notified. |
| **Route deviation (V2)** | Synchronous detection in Socket.IO handler: `ST_DWithin(current_pos, redis_cached_corridor, 500m)` checked every GPS update. 2 consecutive deviations trigger Celery notification task. Alerted within 5 seconds. |
| **SOS false alarm (V2)** | Require confirmation tap ("Are you sure?"). Admin must acknowledge. Auto-resolve after 30min if not escalated. |
| **Battery drain (driver)** | Reduce GPS frequency to 10s when battery <20%. Show warning. Suggest plugging in. |
| **Multiple children, one parent** | Parent has multiple students, each assigned to different routes. Dashboard shows all children's buses. |
| **Browser tab closed (driver)** | **MVP:** Trip auto-pauses, "Tracking paused" shown to parents. Driver re-opens browser to resume. **V2:** Capacitor app handles this natively. |
| **WebSocket connection failure** | Graceful degradation: app shows "Connecting..." state. Core data (routes, schedules, history) accessible via REST API. GPS degrades to "last known position with staleness timestamp." |
| **Concurrent route changes** | Optimistic locking (version column). Conflict returns 409. Admin resolves. |
| **Large school (50+ buses)** | Admin map clusters overlapping buses. Filters by route/status. Paginated API responses. |
| **Insurance/fitness expiry** | Celery daily job checks expiry dates. 30-day, 7-day, 1-day warnings. Vehicle auto-deactivated on expiry. |
| **Data export (GDPR/compliance)** | User data export endpoint (JSON). Account deletion with cascade (anonymize, don't delete financial records). |
| **Stale refresh token reuse (token theft)** | Refresh token family tracking. Reuse of rotated-out token invalidates entire family, forcing re-login on all devices. |
| **Brute force login** | Account lockout after 5 failed attempts, 15-minute cooldown. Tracked in Redis with TTL. |

---

## Guardrails

### Must Have
- All communication over HTTPS
- JWT access tokens (15-min expiry) with `school_id` and `role` claims for stateless RBAC
- Refresh tokens in HttpOnly, Secure, SameSite=Strict cookies with rotation and family-based theft detection
- Account lockout after 5 failed login attempts (15-minute Redis-tracked cooldown)
- RBAC enforced at API middleware level (not just frontend)
- school_id scoping on every data query (application-level for MVP, RLS for V2)
- Input validation on all endpoints (Pydantic)
- Rate limiting on auth endpoints (5/min) and API (100/min)
- Socket.IO connection auth via JWT. Room-level authorization for trip access.
- GPS data never exposed to unauthorized users
- Payment amounts as DECIMAL, never float
- CORS restricted to frontend domain only
- API versioned with `/api/v1/` prefix
- Structured JSON logging with request context

### Must NOT Have
- No native app dependency for parents/admins (everything works in browser)
- No paid/proprietary libraries (all OSS)
- No vendor-locked services (can migrate from any hosting)
- No direct phone number exposure between parent and driver
- No storing credit card data locally
- No blocking operations on the WebSocket event loop (route deviation detection is synchronous but sub-millisecond via cached geometry)
- Redis is a required dependency (GPS buffer, rate limiting, corridor cache, Celery broker). Redis failure degrades real-time features but does NOT cause data loss — GPS points re-route to direct PostgreSQL writes on Redis unavailability. Rate limiting temporarily disabled. Route deviation detection skipped until Redis restores. Health check (`GET /health`) surfaces Redis status within 5 minutes.
- No refresh tokens in localStorage (HttpOnly cookies only)
- No plugin registry / auto-discovery / event bus in MVP (modular monolith with explicit registration)
- No cross-tenant data leakage (school_id scoping enforced at both app layer AND PostgreSQL RLS)

---

## Success Criteria

### MVP (Week 6 Demo)
1. Admin registers a vehicle + route with stops on a map.
2. Parent registers, requests transport, and gets assigned to nearest stop.
3. Driver starts trip and shares GPS via browser.
4. Parent sees bus moving on Leaflet map with ETA to their stop.
5. End-to-end flow works in one browser session.
6. GPS latency from driver to parent map is under 1 second on average.
7. System handles 10 concurrent active trips with 100 subscribing parents on Railway ($12-18/mo).
8. Unauthorized Socket.IO connections are rejected. Rate limiting enforced.
9. CI pipeline green with >70% test coverage on business logic.

### V2 (Week 14)
10. Route deviation detected and alerted within 5 seconds.
11. Driver Capacitor app tracks GPS in background with screen off.
12. System handles 50 concurrent active trips with 500 subscribing parents.
13. Multi-school isolation enforced via RLS -- no cross-tenant data leakage.
14. All data is exportable. No vendor lock-in at any layer.

### Future
15. Payment gateway can be swapped from Razorpay to Stripe by changing one config value.
16. Adding a new feature module requires only creating a new directory + adding `include_router()` call.
