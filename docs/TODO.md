# YatraTrack — TODO / Backlog

Tracked work that's agreed but not yet built. (Source of truth for scope is
`YATRATRACK-BUILD-SPEC.md`; this file is the running backlog.)

Grouped by role / feature area. Priorities: **P0** = bug or launch-blocker ·
**P1** = MVP gap · **P2** = polish · **V2** = deferred by design. File refs are
verified against the code as of 2026-06-09.

---

## super_admin (multi-school console) — V2 built 2026-06-09

- [x] **V2** School **create** endpoint — `POST /api/v1/schools/` (super_admin;
  auto join code). `backend/app/schools/{router,services,schemas}.py`
  _(verified live: create + list + name filter)_
- [x] **V2** School **list** endpoint — `GET /api/v1/schools/?q=&limit=&offset=`
  (super_admin, cross-school).
- [x] **V2** Cross-school console UI — `SuperDashboard` now lists schools with a
  create dialog + join-code reveal + school counts.
  `frontend/src/features/super/SuperDashboard.tsx` _(tsc + vite build pass)_
- [x] **V2** PostgreSQL Row-Level Security — migration `0010` enables RLS + `FORCE`
  + a `tenant_isolation` policy on all 11 `school_id` tables; the app sets a
  per-request `app.current_school_id` GUC via a `ContextVar` + SQLAlchemy
  `after_begin` hook (transaction-local → survives mid-request commits, no pool
  leak); super_admin/system paths use empty GUC = bypass.
  `backend/alembic/versions/0010_rls_tenant_isolation.py`, `app/database.py`,
  `app/deps.py` _(verified live as a non-superuser role: cross-tenant SELECT
  filtered, cross-tenant INSERT blocked by WITH CHECK, empty GUC sees all)_
  - [ ] **Activation (infra):** Postgres bypasses RLS for **superusers**, and the
    app currently connects as the bootstrap superuser, so RLS is present but not
    yet *enforcing*. To activate: connect the app runtime as a **non-superuser**
    role (with `SELECT/INSERT/UPDATE/DELETE` grants), keeping migrations/seed on
    the owner role. Needs split runtime-vs-migration credentials
    (`docker-compose.yml` + `.env` + the Docker `CMD` runs `alembic upgrade` as
    the connecting role) — an infra decision, not a code change.

---

## Admin-initiated password reset

**Status:** planned · **Added:** 2026-06-08

Let admins set a user's password directly (today only self-service
forgot/reset exists; drivers get a one-time temp password at creation).

**Decided scope:**
- **super_admin** → reset **any** user, in any school.
- **school_admin** → reset only users in **their own school**, and only
  `driver` / `parent` roles (must NOT be able to reset other admins or
  super_admins — privilege safety).

**Method (decided):** admin **types a specific new password** (with a confirm
field). Server sets `password_hash`, then **revokes the target's refresh
tokens** so the user is forced to re-login. (Admin knows the password until the
user changes it — consider a future "force change on next login" flag.)

**Backend:** _(done 2026-06-09 — new `app/users` module; authz verified with a
10-case live test: own-school driver/parent reset OK, own-school admin → 403,
cross-school → 404, super_admin → any, refresh tokens revoked, list scoping)_
- [x] **P1** `POST /api/v1/users/{id}/reset-password` body `{ new_password }` (min 8).
  - authz: super_admin any; school_admin → own-school `driver`/`parent` only.
    Cross-school target returns **404** (no tenant disclosure); own-school
    non-manageable role returns **403**.
  - reuses `hash_password` + `revoke_all_families_for_user` (auth/services.py).
- [x] **P1** `GET /api/v1/users` (list/search, `?role=&q=&school=`):
  - super_admin → all users (optional `school` filter);
  - school_admin → own-school `driver`/`parent` only (hard-scoped).

**Frontend:**
- [x] **P1** school_admin: **People** screen (`/admin/users`, nav entry) listing
  drivers + parents with search + role filter and a "Reset password" action →
  dialog (new password + confirm, min-8/match validation).
  `frontend/src/features/admin/people/PeoplePage.tsx` _(done 2026-06-09; tsc +
  vite build pass)_
- [x] **V2** super_admin: cross-school user search + reset UI — new **People**
  screen in the `/super` console (`/super/users`, nav entry) with search + school
  filter + role filter and a reset-password dialog; uses `GET /users?school=` and
  reset-any. `frontend/src/features/super/SuperPeoplePage.tsx` _(done 2026-06-09;
  tsc + vite build pass; backend authz proven in the 10-case test)_

---

## Driver

- [x] **P1** Implement `GET /drivers/{id}/schedule` — now queries the trips table
  for the driver's upcoming/in-flight trips (paginated `TripPage`, soonest first).
  `backend/app/vehicles/router.py`, `services.list_driver_schedule` _(done 2026-06-09)_
- [x] **P1** Implement `GET /drivers/{id}/trips` — full trip history, most recent
  first (paginated `TripPage`). `services.list_driver_trips` _(done 2026-06-09)_

_(Verified already built: per-stop board/absent attendance toggles, boarded-students
drop-off panel, end-of-trip safeguard gate.)_

---

## Parent

- [x] **P1** Notification-preferences UI — new parent **Settings** screen
  (`/parent/settings`, nav entry added) with toggles for trip updates /
  bus-approaching / boarding-drop-off, seeded from `user.notification_prefs` and
  persisted via `notificationsApi.updatePreferences`; safety alerts shown as
  always-on. `frontend/src/features/parent/SettingsPage.tsx` _(done 2026-06-09;
  tsc + vite build pass)_
  - [ ] **Follow-up (needs product call):** the backend `notify()` helper does not
    yet read these prefs, so muting only takes effect once delivery-side
    enforcement is added — deferred because it touches the child-safety
    notification path (which alert types are non-negotiable is a product decision).
    `backend/app/notifications/services.py:27`

_(Verified already built: "Mark absent today" toggle, live tracking.)_

---

## school_admin

- [x] **P2** Add a `bus_approaching_radius_m` control to Settings — added a numeric
  metres field (50–1000) to the admin Preferences card; `SchoolSettings` type
  extended. `frontend/src/features/admin/SettingsPage.tsx` _(done 2026-06-09)_
- [x] **P2** Make `eta.py` read per-school `bus_approaching_radius_m` — the radius is
  now cached in Redis (`trip:radius:{id}`) at trip start (clamped 50–2000 m,
  default 200) so the GPS hot path stays DB-free; `eta.py` reads it.
  `backend/app/tracking/{eta,services}.py` _(done 2026-06-09; verified live: 250 m
  point is "approaching" at 300 m radius, not at 200 m)_

_(Verified already built: safety-alerts panel with acknowledge/resolve + critical
highlighting.)_

---

## Bugs & code cleanup

- [x] **P0** Vehicle-delete guard is a silent no-op — fixed: `_has_active_trip()`
  now imports `app.tracking.models.Trip` and queries for blocking statuses
  (`scheduled`/`in_progress`/`pending_safeguard_check`); delete returns 409 when a
  vehicle has an active/scheduled trip. `backend/app/vehicles/services.py`
  _(done 2026-06-09; verified against a live PostGIS DB)_
- [x] **P2** Deleted the orphaned `list_route_students` stub (dead code, zero
  callers). `backend/app/routes/services.py` _(done 2026-06-09)_
- [x] **P2** Fixed the stale `DriverBrief.phone` comment — now points at the
  conditional disclosure in `get_trip_detail()`. `backend/app/tracking/schemas.py`
  _(done 2026-06-09)_
