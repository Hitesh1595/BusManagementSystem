# YatraTrack — Master Reference Document

> ⚠️ **SUPERSEDED — kept for history only.** The single authoritative source of truth is [`YATRATRACK-BUILD-SPEC.md`](./YATRATRACK-BUILD-SPEC.md) (v1.0, 2026-05-30), which consolidates this doc + all revisions and resolves every open question. Build from that, not this.

**Date:** 2026-05-30  
**Status:** Pre-development — decisions locked, build not started  
**Author:** Hitesh Singh  

---

## 1. Product Identity

| Field | Value |
|---|---|
| **Product Name** | YatraTrack |
| **Meaning** | Yatra (journey) + Track (GPS tracking) |
| **Tagline** | बच्चों का सफर, Safe & Tracked. |
| **Positioning** | Browser-based school transport management platform for Indian schools |
| **Target Market** | India (primary). Razorpay for payments, MSG91/Twilio for SMS |
| **Domain** | yatratrack.app (or yatratrack.in) — to be registered |
| **WhatsApp** | +91 XXXXXXXXXX — to be filled |
| **Contact Email** | hello@yatratrack.in — to be set up |

---

## 2. Actors

| Role | Description |
|---|---|
| **School Admin** | Manages fleet, routes, drivers, transport requests. Primary paying customer. |
| **Parent/Guardian** | Registers children, requests transport, tracks bus live |
| **Driver** | Receives route, shares GPS, marks attendance |
| **Super Admin** | Manages multiple schools (V2) |
| **Student** | Passive — tracked via attendance, no direct system interaction |

---

## 3. Tech Stack (Final)

| Layer | Technology | Notes |
|---|---|---|
| **Language** | Python 3.12+ | |
| **Backend** | FastAPI 0.115+ | Native async, auto OpenAPI docs |
| **ORM** | SQLAlchemy 2.0 async | pool_size=20, max_overflow=10, pool_timeout=30 |
| **Migrations** | Alembic | |
| **Real-Time** | python-socketio 5.x | Mounted on same ASGI process as FastAPI |
| **Task Queue** | Celery 5.x + Redis | Background jobs, GPS cleanup |
| **Auth** | PyJWT + passlib + bcrypt | JWT in Bearer header, refresh in HttpOnly cookie |
| **Database** | PostgreSQL 16 + PostGIS 3.4 | ACID + geospatial |
| **Cache/Broker** | Redis 7 | Socket.IO, Celery, GPS buffer, rate limiting |
| **Geospatial ORM** | GeoAlchemy2 | PostGIS integration |
| **Frontend** | React 19 + Vite 6 | |
| **UI** | shadcn/ui + Tailwind CSS 4 | |
| **Maps** | Leaflet.js 1.9 + react-leaflet | |
| **Map Tiles** | Stadia Maps (prod) / OSM (dev) | Stadia: 200k tiles/mo free |
| **State** | Zustand | Lightweight, real-time GPS state |
| **Real-Time Client** | Socket.IO client | |
| **PDF** | reportlab | Pure Python, zero system deps |
| **Excel** | openpyxl | |
| **Geocoding** | Nominatim (dev) / MapTiler (prod) | MapTiler: 100k/mo free |
| **Error Tracking** | Sentry | Python + React SDKs |
| **Logging** | structlog | JSON structured logs |
| **Reverse Proxy** | Caddy 2 | Auto HTTPS |
| **Containers** | Docker + Docker Compose | |
| **Testing** | pytest + pytest-asyncio + httpx | |
| **E2E** | Playwright (V2) | |
| **Linting** | Ruff | |
| **CI/CD** | GitHub Actions | |
| **Payment (Future)** | Razorpay (primary) + Stripe (fallback) | |

---

## 4. Architecture Decisions

- **Single ASGI process**: FastAPI + Socket.IO mounted together — NOT two separate services
- **Modular monolith**: Feature modules in `app/auth/`, `app/vehicles/`, `app/routes/`, `app/tracking/`, `app/notifications/` with explicit `include_router()` — no auto-discovery
- **GPS buffer**: Redis → PostgreSQL batch write every 30s via asyncio background task (not Celery)
- **Route deviation detection**: Synchronous in Socket.IO handler using cached PostGIS geometry in Redis (sub-ms, no DB round-trip)
- **Multi-tenancy**: `school_id` on all tables. App-level filtering (MVP) + PostgreSQL RLS (V2)
- **Chat**: Removed entirely. Parents call driver via phone number (admin-controlled toggle)

---

## 5. Feature List

### MVP (Weeks 1–8, solo developer)

| # | Feature | Priority |
|---|---------|----------|
| M1 | User auth — JWT + RBAC + refresh token rotation + account lockout | P0 |
| M2 | Multi-school setup — school_id scoping + RLS | P0 |
| M3 | Vehicle CRUD | P0 |
| M4 | Driver management + vehicle assignment | P0 |
| M5 | Route management + ordered stops with GPS | P0 |
| M6 | Student registration + transport request + nearest-stop suggestion | P0 |
| M7 | Driver trip flow — start trip, share GPS, end trip | P0 |
| M8 | Real-time GPS tracking — parent sees live bus on Leaflet map + ETA | P0 |
| M9 | In-app notifications — trip started/ended via Socket.IO | P0 |
| M10 | Basic admin map — active trips overview | P1 |
| M11 | Attendance marking — driver marks boarded/absent per stop | P0 |
| M12 | Child not-boarded alert — parent + admin notified via Socket.IO | P0 |
| M13 | Child safeguarding — not-dropped alert on trip end (CRITICAL) | P0 |
| M14 | Parent marks child absent — driver sees skip indicator | P1 |

**Week 8 Demo Goal:** Admin sets up vehicle + route → parent requests + assigned → driver starts trip + shares GPS → parent tracks live → driver marks attendance → safety alerts fire correctly.

### V2 (Weeks 9–16)

| # | Feature | Priority |
|---|---------|----------|
| V1 | Capacitor.js driver app — background GPS via @capacitor/geolocation | P1 |
| V3 | PWA + web push notifications | P1 |
| V4 | Route deviation alerts — synchronous detection, PostGIS corridor cached in Redis | P1 |
| V5 | SOS button — parent triggers emergency, admin acknowledges | P1 |
| V6 | Driver incident reporting | P1 |
| V7 | Substitute driver flow | P1 |
| V8 | Multi-child parent dashboard | P1 |
| V9 | Broadcast announcements — admin to route/all parents (one-way, no reply) | P2 |
| V10 | Payment structure — fee schedules, invoices, manual recording | P2 |
| V11 | Analytics dashboard | P2 |
| V12 | Offline GPS buffering — IndexedDB + sync on reconnect | P2 |
| V13 | Email notifications | P2 |
| V14 | Feedback & rating — parent rates driver, auto-flag low ratings | P2 |
| V15 | Formal complaints system — form-based, tracked status | P2 |
| V16 | Compliance report generation — PDF/Excel via reportlab/openpyxl | P2 |

### Future

| # | Feature |
|---|---------|
| F1 | Razorpay payment gateway (UPI + cards + netbanking) |
| F2 | Plugin architecture extraction |
| F3 | Route optimization |
| F4 | Driver behavior analytics |
| F5 | SMS notifications via MSG91/Twilio |
| F6 | Student RFID/QR attendance |
| F7 | Historical trip replay |
| F8 | White-label per school |
| F9 | React Native mobile app |

---

## 6. Database — Key Tables

### Core
- `schools` — id, name, address, phone, email, logo_url, settings (JSONB), is_active
- `users` — id, email, password_hash, full_name, phone, role (enum), school_id, push_subscription (JSONB)
- `students` — id, full_name, grade, section, parent_id, school_id, pickup_address, pickup_location (PostGIS POINT)

### Fleet
- `vehicles` — id, school_id, plate_number, vehicle_type, capacity, make, model, year, insurance_expiry, fitness_expiry, is_active
- `routes` — id, school_id, name, vehicle_id, driver_id, route_path (PostGIS LINESTRING), schedule_type, is_active, version
- `route_stops` — id, route_id, name, location (PostGIS POINT), address, stop_order, arrival_time
- `student_route_assignments` — id, student_id, route_id, stop_id, assigned_at, is_active
- `transport_requests` — id, parent_id, student_id, school_id, pickup_location (PostGIS POINT), status (enum), assigned_route_id, assigned_stop_id

### Trips & GPS
- `trips` — id, route_id, driver_id, vehicle_id, status (enum: scheduled/in_progress/pending_safeguard_check/completed/cancelled/incident), scheduled_date, started_at, ended_at, safeguarding_checked, original_driver_id, reassigned_at
- `gps_logs` — id (BIGSERIAL), trip_id, location (PostGIS POINT), speed, heading, accuracy, recorded_at — **partitioned by month**

### Safety (MVP)
- `attendance_records` — id, trip_id, school_id, student_id, stop_id, status (enum: boarded/absent/absent_parent_marked), marked_at, marked_by, drop_stop_id, dropped_at — UNIQUE(trip_id, student_id)
- `alerts` — id, school_id, trip_id, type (enum: child_not_boarded/child_not_dropped/sos/route_deviation/incident/insurance_expiry), severity (enum: critical/high/medium/low), triggered_by, acknowledged_by, resolved_at

### Auth
- `refresh_tokens` — id, user_id, token_hash, device_id, family_id, issued_at, expires_at, revoked_at

### Communication (V2)
- `broadcasts` — id, school_id, sender_id, route_id (nullable = school-wide), title, body, created_at

### V2 Tables
- `trip_feedback` — UNIQUE(trip_id, parent_id), rating 1–5, is_flagged (auto if ≤2)
- `complaints` — status enum: open/in_review/resolved/closed
- `reports` — type enum: compliance/attendance/incident/trip_summary, format enum: pdf/xlsx
- `fee_schedules`, `invoices`, `payments` — payment abstraction layer ready

---

## 7. API Structure

```
/api/v1/auth/          — register, login, refresh, logout, me
/api/v1/schools/       — CRUD (super admin)
/api/v1/vehicles/      — CRUD
/api/v1/drivers/       — list, assign, schedule, trips
/api/v1/routes/        — CRUD + stops + reorder + students
/api/v1/transport-requests/ — submit, review, approve, suggest-stop
/api/v1/trips/         — CRUD + start + end + cancel + gps-log + active
/api/v1/trips/{id}/stops/{stop_id}/attendance — batch mark (MVP)
/api/v1/trips/{id}/drop   — batch drop-off marking
/api/v1/trips/{id}/absent/{student_id} — parent absent mark
/api/v1/alerts/        — list, acknowledge, resolve
/api/v1/notifications/ — list, read, preferences
/api/v1/broadcasts/    — send, list (V2)
/api/v1/parents/dashboard — aggregated multi-child view (V2)
/api/v1/reports/       — generate, status, download (V2)
/health                — DB + Redis + last GPS event
```

### Socket.IO Events
```
# Client → Server
join_trip, leave_trip, location_update, location_batch

# Server → Client
location_update, bus_approaching, trip_started, trip_ended,
tracking_paused, attendance_update, child_not_boarded,
child_not_dropped, child_absent_marked, route_deviation,
alert_new, broadcast, notification, trip_reassigned
```

---

## 8. Security Rules

- JWT access tokens: 15-min expiry, `user_id + school_id + role` in claims
- Refresh tokens: HttpOnly + Secure + SameSite=Strict cookies — **never localStorage**
- Refresh token rotation + family theft detection
- Account lockout: 5 failed attempts → 15-min Redis TTL lock
- CORS: `allow_origins=[settings.FRONTEND_URL]` — no wildcard
- Socket.IO: JWT in `?token=` query param on connect. Room authorization on `join_trip`
- Rate limiting: auth 5/min, API 100/min, location_update 1 per 3s per connection
- school_id scoping on every query — app layer (MVP) + PostgreSQL RLS (V2)
- Driver phone: shown to parents ONLY during active trip AND only if `school.settings.driver_phone_visible = true`

---

## 9. Hosting Strategy

| Tier | Setup | Cost | Use |
|---|---|---|---|
| **Dev/Demo** | Render (free) + Neon (free) + Upstash (free) + Cloudflare Pages | $0 | Development only — WS impractical on free tier |
| **MVP Prod** | Railway (app + PostgreSQL + Redis) + Cloudflare Pages | ~$12–18/mo | Always-on, 500 concurrent users |
| **Growth** | Hetzner VPS (Docker Compose) + Neon Pro | ~$5–30/mo | 2,000–5,000 concurrent |
| **Scale** | Hetzner x2 + load balancer + managed DB | ~$50–80/mo | 10,000+ users |

**PostGIS note:** Railway default PG does NOT include PostGIS. Use custom Dockerfile or Neon/Supabase (PostGIS enabled by default).

---

## 10. Monitoring (All Free, MVP)

| Tool | Purpose |
|---|---|
| Sentry | Error tracking — Python + React SDK |
| structlog | JSON structured logs with request_id, user_id, school_id, duration_ms |
| UptimeRobot | Pings /health every 5 min, email alert on downtime |
| `/health` endpoint | Returns: status, db_connected, redis_connected, last_gps_event_at |

**Logging config:**
- Dev: DEBUG, Prod: WARNING (LOG_LEVEL env var)
- Scrubbing: phones masked (last 4 digits), GPS rounded to 2 decimal places, emails domain-only
- Celery tasks log: task_name, task_id, school_id, duration_ms, status

---

## 11. Landing Page (YatraTrack Marketing Site)

### Tech
- React 19 + Vite 6 + Tailwind CSS 4
- Location: `landing/` directory in this repo
- Static — deploy to Cloudflare Pages

### Design
| Property | Value |
|---|---|
| Primary | Indigo `#4f46e5` |
| Background | White `#ffffff` + `#fafafa` |
| Accent | `#eef2ff` |
| WhatsApp | `#25d366` |
| Heading text | `#1e1b4b` |
| Body text | `#6b7280` |
| Border | `#e5e7eb` |
| Top stripe | 3px linear-gradient indigo |
| Hero glow | Radial indigo `rgba(99,102,241,0.07)` |

Indian identity: **copy only** — Hinglish headline + "Made for Indian Schools" badge. No warm/saffron colors anywhere.

### Sections
1. **Sticky Nav** — Logo · Features · Pricing · Contact links · `Contact Us` (outline) + `💬 WhatsApp` (green) buttons
2. **Hero** — 🇮🇳 badge · `बच्चों का सफर, Safe & Tracked.` · Hinglish subtitle · `💬 WhatsApp Us` (primary) + `✉️ Contact Us` (secondary) · 4 trust badges
3. **Dashboard Preview** — CSS map mockup with pulsing bus marker, route line, stop dots, LIVE badge + 3 stat cards
4. **Features** (`#features`) — 6-card grid: GPS Tracking · Safety Alerts · Attendance · Fleet Management · No App Needed · Multi-School
5. **How It Works** — 3 numbered steps: School Setup → Parents Join → Track Live
6. **Built for Everyone** — 3 role cards: Admin · Parents · Driver
7. **Pricing** (`#pricing`) — Hinglish copy + `💬 WhatsApp Us` + `✉️ Contact Us` + "No spam · No sales pressure"
8. **Footer** — Logo · Made with ❤️ in India · © 2026 YatraTrack

### CTAs
- **WhatsApp Us:** `https://wa.me/91XXXXXXXXXX?text=Hi, I'm interested in YatraTrack for my school`
- **Contact Us:** `mailto:hello@yatratrack.in`

*(Replace XXXXXXXXXX with real number and hello@yatratrack.in with real email before going live)*

### Removed / Not Included
- ~~Join Waitlist~~ — removed
- ~~City chips / waitlist form~~ — removed
- ~~Book a Demo~~ — removed
- ~~Free Trial~~ — removed
- ~~14-day trial badge~~ — removed

---

## 12. Open Questions (Unresolved)

| # | Question | Impact |
|---|---|---|
| OQ-1 | Who is the first pilot school? | Validates capacity planning and hosting tier |
| OQ-2 | Target geography — India only or global? | Payment gateway, SMS provider, compliance (GDPR vs DPDP) |
| OQ-3 | Parent self-registration or admin-only? | Self-reg needs school-code verification to prevent unauthorized signups |
| OQ-4 | Language / localization? | Hindi/regional = i18n from day 1, expensive to retrofit |
| OQ-5 | Existing data to migrate? | If school uses spreadsheets → data import tool needed in Phase 1 |
| OQ-6 | Driver device minimum spec? | Min Android/iOS version for Capacitor V2 app |
| OQ-7 | Branding / domain confirmed? | Needed before deployment (SSL, PWA manifest, email templates) |
| OQ-8 | MapTiler vs Stadia Maps for production tiles? | Stadia: 200k/mo free. MapTiler: 100k/mo free |
| OQ-9 | Nominatim self-hosted vs MapTiler geocoding? | Public Nominatim rate-limited (1 req/sec) |
| OQ-10 | Redis persistence — AOF or volatile? | If Redis restarts, GPS buffer + corridor cache lost |
| OQ-11 | Refresh token expiry — 7 days or 30 days? | UX vs security tradeoff for child-tracking system |
| OQ-12 | Trip end strictness — block or just warn? | Current: pending_safeguard_check. Alternative: warn only |
| OQ-13 | Attendance UX — sequential stops enforced or flexible? | Sequential = safer but adds friction for driver |
| OQ-14 | Parent absent-mark deadline — before trip starts or 30 min before? | Earlier cutoff gives driver time to see updated list |
| OQ-15 | Driver feedback visibility — aggregate only / anonymized / nothing? | Transparency vs conflict risk |
| OQ-16 | Compliance report fields — what does transport authority require? | Needs input from real school/transport authority |
| OQ-17 | Audit_logs DB retention — separate from app log retention? | App logs: 30 days. Audit logs: potentially years for compliance |
| OQ-18 | Individual driver phone opt-out? | Currently school-level toggle only |
| OQ-19 | Capacitor driver app — Android only for V2 or iOS too? | iOS needs Apple Developer account ($99/yr) |
| OQ-20 | WhatsApp business number for landing page? | Replace XXXXXXXXXX in wa.me link |
| OQ-21 | Contact email for landing page? | Replace hello@yatratrack.in |
| OQ-22 | Domain name registered? | yatratrack.app / yatratrack.in |

---

## 13. Development Phases Summary

### Phase 1 — Foundation (Weeks 1–3)
- Project scaffolding: Docker Compose, FastAPI modular monolith, SQLAlchemy async, Alembic
- Logging: structlog with scrubbing, Celery logging, logrotate config
- Auth: JWT + refresh tokens + RBAC + account lockout
- Multi-school + entity CRUD: schools, vehicles, drivers, routes, stops, students, transport requests

### Phase 2 — Core GPS + Frontend (Weeks 4–8)
- Trip management + Socket.IO GPS tracking + Redis buffer
- Safety system: attendance marking, child-not-boarded, safeguarding alerts, parent absent marking
- React frontend: parent tracking, driver dashboard, admin map
- Integration tests + demo flow

### V2 — Production Features (Weeks 9–16)
- Capacitor driver app + background GPS
- Route deviation detection + push notifications + SOS
- Substitute driver, multi-child dashboard, broadcasts
- Complaints, feedback, compliance reports
- Payment structure + analytics dashboard
- E2E tests (Playwright) + load testing (locust)

### Future (Post-Launch)
- Razorpay gateway integration
- Plugin architecture extraction
- Route optimization
- React Native mobile app

---

## 14. Project Structure (Backend)

```
app/
  main.py             # FastAPI + Socket.IO mount + explicit include_router()
  config.py           # Pydantic settings
  database.py         # SQLAlchemy async engine
  deps.py             # get_db, get_current_user, etc.
  middleware.py       # CORS, rate limiting, school_id scoping
  core/
    logging.py        # structlog processor chain + sensitive data scrubbing
  auth/               # JWT, RBAC, user management
  schools/            # School CRUD
  vehicles/           # Vehicle + Driver management
  routes/             # Route + Stop + Transport Request
  tracking/           # Trip, GPS, Socket.IO handlers, safety.py
  notifications/      # In-app notifications
  communication/      # Broadcasts (V2), complaints (V2)
  reports/            # Report generation (V2)
  payments/           # Payment abstraction (V2)
    gateways/
      base.py         # Abstract gateway interface
      razorpay.py     # (Future)
      stripe.py       # (Future)

landing/              # Marketing landing page (React + Vite + Tailwind)
tests/
  factories.py        # Pytest fixtures: school, user, vehicle, route, trip
docker/
  logrotate.conf      # Log rotation for VPS deployments
```
