# YatraTrack — TODO / Backlog

Tracked work that's agreed but not yet built. (Source of truth for scope is
`YATRATRACK-BUILD-SPEC.md`; this file is the running backlog.)

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

**Backend:**
- `POST /api/v1/users/{id}/reset-password` body `{ new_password }` (min 8).
  - authz: super_admin any; school_admin → `target.school_id == claims.school_id`
    and `target.role in (driver, parent)`, else 403.
  - reuse `hash_password` + the refresh-token-revoke helper in `auth/services.py`.
- `GET /api/v1/users` (list/search) so the UI can pick a target:
  - super_admin → all users (cross-school, with school filter/search);
  - school_admin → own-school `driver`/`parent` users only.
  - Note: no user-list endpoint exists today; parents have no admin management
    screen yet (they self-register).

**Frontend:**
- school_admin: a "People / Users" screen (drivers + parents) with a
  "Reset password" row action → dialog (new password + confirm).
  (Drivers already have a screen; parents need this new list.)
- super_admin: cross-school user search + reset — build as part of the V2
  super-admin console at `/super` (currently a placeholder).

**Depends on / relates to:** the V2 super-admin console (school create/list are
501 stubs today); a generic users module/endpoint.
