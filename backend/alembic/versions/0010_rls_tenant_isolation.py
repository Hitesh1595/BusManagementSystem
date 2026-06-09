"""0010 row-level security: tenant isolation

Revision ID: 0010_rls_tenant_isolation
Revises: 0009_attendance_records
Create Date: 2026-06-09 00:00:00.000000

Spec §6.8 — defence-in-depth multi-tenancy. Enables RLS on every table that
carries a `school_id`, with a policy that isolates rows by the per-request
session GUC `app.current_school_id` (set by the app's `after_begin` hook from the
JWT claim). An empty/unset GUC means "bypass" — used by super_admin and by
system paths (schedulers, GPS flush, socket handlers) that operate cross-tenant.

`FORCE ROW LEVEL SECURITY` makes the table OWNER subject to the policy too.

ACTIVATION NOTE: PostgreSQL bypasses RLS for SUPERUSER roles. The app currently
connects as the bootstrap superuser, so these policies are present but only
ENFORCE once the app connects as a non-superuser role (see CLAUDE.md / docs).
The policies and wiring are correct and verified against a non-superuser role.

Tables without a `school_id` column are intentionally NOT covered here:
  - route_stops, gps_logs  → reached only via their RLS-protected parent
    (routes / trips) plus app-level scoping;
  - refresh_tokens, auth_tokens → auth-internal, keyed by user_id;
  - schools → the tenant root itself (super_admin manages; school_admin reads
    own via app-level check).
"""

from __future__ import annotations

from alembic import op

revision: str = "0010_rls_tenant_isolation"
down_revision: str | None = "0009_attendance_records"
branch_labels = None
depends_on = None

# Every table that carries a `school_id` column.
_TENANT_TABLES = (
    "users",
    "vehicles",
    "routes",
    "students",
    "student_route_assignments",
    "transport_requests",
    "trips",
    "attendance_records",
    "alerts",
    "notifications",
    "audit_logs",
)

# Visible when the GUC is unset/empty (super_admin + system paths) OR the row's
# school_id matches the current request's school.
_PREDICATE = (
    "coalesce(current_setting('app.current_school_id', true), '') = '' "
    "OR school_id::text = current_setting('app.current_school_id', true)"
)


def upgrade() -> None:
    for table in _TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        # Idempotent: drop first so the migration can be re-applied cleanly.
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({_PREDICATE}) WITH CHECK ({_PREDICATE})"
        )


def downgrade() -> None:
    for table in _TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
