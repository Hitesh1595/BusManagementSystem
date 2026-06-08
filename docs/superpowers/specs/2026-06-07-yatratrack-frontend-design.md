# YatraTrack Frontend (Step 6) — Design Spec

**Date:** 2026-06-07 · **Status:** Approved, building · **Source of truth:** `docs/YATRATRACK-BUILD-SPEC.md` §13, §21.6

## Goal

Build the complete Step-6 MVP frontend: a single browser-based SPA serving the three active roles (**parent**, **driver**, **school_admin**) wired to the live FastAPI backend, plus a separate static Hinglish marketing landing page. `super_admin` gets a minimal placeholder (V2).

## Decisions (locked)

- **Scope:** Full MVP SPA, all 3 active roles, all spec screens. Landing page included.
- **Stack:** React 19 + Vite 6 + Tailwind CSS 4 + shadcn/ui · Zustand (live state) · **TanStack Query over ky** (server state) · react-leaflet v5 + Leaflet 1.9 (maps) · socket.io-client (real-time) · react-i18next (i18n) · Vitest + RTL (tests).
- **Backend addition:** wire `notifications/router.py` (list, `{id}/read`, `read-all`, `preferences`) using existing services; register in `main.py`. Web-push subscribe/unsubscribe stay V2 stubs.
- **Verification:** against the live Docker backend (user runs `docker compose up` + seed) — login per role + end-to-end trip flow — plus `tsc` + `vite build` + lint + Vitest.

## Architecture

Single Vite SPA, role-based lazy-loaded routes. Same-origin in dev via Vite proxy of `/api` and `/socket.io` → `:8000` (sidesteps CORS; makes the httpOnly `SameSite=Strict` refresh cookie at path `/api/v1/auth` and the WS upgrade work transparently; `localhost` is a secure context so the `Secure` cookie sets in dev).

```
frontend/src/
  app/        router.tsx (role-guarded, lazy)  providers.tsx (QueryClient, i18n, Auth, Toaster)
  lib/api/    client.ts (ky + 401→refresh-once)  types.ts (mirrors backend schemas)  <module>.ts per domain
  lib/        socket.ts (typed socket.io singleton)  query.ts  i18n.ts  utils (IST, phone-mask, haversine)
  stores/     auth.ts (token+user)  liveTrip.ts (positions, ETA, connection status)
  components/ ui/ (shadcn)  layout/ (role shells)  maps/  common/ (NotificationBell, ConnectionBanner, Skeletons, ErrorBoundary)
  features/   auth/  parent/  driver/  admin/
  locales/en/ per-feature namespaces (no hard-coded strings)
landing/      static marketing site
```

## Auth lifecycle

On load: `POST /auth/refresh` (cookie) → access token → `GET /auth/me`. ky interceptor retries once on 401 via refresh, else → login. Role from `/auth/me` drives routing. Login/Register store access token in Zustand (memory); refresh cookie is httpOnly. 423 (lockout) and 429 (rate-limit) surfaced specifically.

## Real-time layer

socket.io-client connects same-origin with `auth:{token}`. `liveTrip` Zustand store consumes: `location_update`→moving marker + ETA, `bus_approaching`→toast, `tracking_paused`→stale banner (last-known + timestamp), `attendance_update`/`child_not_boarded`/`child_not_dropped`/`trip_ended`→live roster + alerts. Parent emits `join_trip`; driver emits throttled `location_update` from `watchPosition`. Socket loss → ConnectionBanner; REST still serves core data.

## Screens

- **Auth:** Login · Register (join-code) · Forgot/Reset
- **Parent:** Dashboard (child cards) · Live-Track (ETA, last-updated, tracking-paused, masked driver-call) · Request Transport (address→pin→nearest-stop) · Mark-Absent · Notifications
- **Driver:** Today's Route · Run Trip (Start → per-stop Boarded/Absent → Submit → drop-all/per-stop → End w/ safeguard gate) · Attendance · Drop-off · Keep-screen-on (Wake Lock)
- **Admin:** Setup Wizard · Vehicles CRUD · Routes+Stops map editor (click-add, drag-reorder, geocode) · Drivers · Transport Requests (map overlay, approve/assign w/ capacity guard) · Fleet Map · Alerts Panel (CRITICAL pinned + sound) · School Settings (toggles, join-code regen)

## Design language

Indigo primary `#4f46e5`, white/`#fafafa` surfaces, `#1e1b4b` headings. Mobile-first; driver touch targets ≥56px. Light theme. shadcn/ui (new-york) on Tailwind 4 CSS-variable theme. Skeleton loaders, optimistic UI with rollback, IST rendering, masked phone (`98765***21`, full only in `tel:` href when permitted).

## Build order

1. Foundation + shared contracts (authored centrally for coherence): scaffold, deps, Tailwind/shadcn, proxy, i18n, QueryClient, ky client + full TS types, socket lib, auth + liveTrip stores, layouts, role-guarded router.
2. Backend `notifications/router.py` + register.
3. Parallel feature build (disjoint dirs): auth, parent, driver, admin, shared maps/common, landing.
4. Integrate, then `tsc` + `vite build` + lint + Vitest + live smoke test.

## Risks / notes to verify at build time

- Exact Socket.IO mount path / namespace (`main.py` mounts `/socket.io`; confirm client `path`).
- Whether `GET /trips` self-scopes for `driver` role or needs client filter by `driver_id`.
- react-leaflet v5 ↔ React 19 peer compatibility; pin versions accordingly.
- shadcn/ui generator support for Tailwind 4 (use CSS-variable theme; hand-author components if generator lags).
- Node/npm availability + network for `npm install`.
```
