# School Bus Management System - Revision 2 Additions

> ⚠️ **SUPERSEDED — kept for history only.** Folded into [`YATRATRACK-BUILD-SPEC.md`](./YATRATRACK-BUILD-SPEC.md) (v1.0, 2026-05-30). Build from that.

**Date:** 2026-05-27
**Author:** Planner Agent (RALPLAN Consensus - Iteration 2)
**Status:** DRAFT - Pending User Confirmation
**Scope:** 12 targeted additions across Logging, Safety, Operational, Parent Experience, and Admin modules

---

## 1. RALPLAN-DR Summary (Revision 2)

### Principles (5) -- Updated

1. **Simple, not complex** -- Each addition fits naturally into existing FastAPI + Celery + structlog + PostgreSQL patterns. No new dependencies unless essential. Extend existing models/tables with columns before creating new tables.
2. **System flows naturally** -- Safety features interconnect: parent marks absent -> driver skips stop -> no "not boarded" alert fires. Student boarded but not dropped -> safeguarding alert fires. No isolated features.
3. **Developer-friendly** -- Clear separation. New features live in existing modules (logging in `app/core/logging.py`, safety in `app/tracking/safety.py`, complaints in `app/communication/complaints.py`). Explicit registrations, no magic.
4. **Only add what is relevant** -- Skip anything that adds complexity without real-world value. Feedback/rating, complaints, and compliance reports are V2 because they are not needed for a working MVP demo.
5. **Fit into existing tech stack** -- All additions use FastAPI, Celery, structlog, Sentry, PostgreSQL, Socket.IO, Redis. Zero new infrastructure dependencies.

### Decision Drivers (Top 3)

| # | Driver | Weight | Rationale |
|---|--------|--------|-----------|
| 1 | **Child safety is non-negotiable** | Critical | "Not boarded" and "not dropped" alerts are the highest-value features for parents. These MUST be in MVP alongside attendance marking (promoting V5 attendance to MVP). |
| 2 | **Logging must be production-grade from day 1** | High | structlog is already in the stack. Adding log levels, scrubbing, Celery task logging, and retention is configuration work, not new architecture. Prevents debugging blindness in production. |
| 3 | **Operational features serve real daily pain** | Medium | Substitute driver, multi-child dashboard, feedback, complaints, and compliance reports serve real needs but are not blocking MVP demo. Keep in V2. |

### Viable Options -- Safety Feature Placement

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **Option A: Safety in MVP (chosen)** | Promote attendance marking (V5) + child-not-boarded alert + safeguarding alert + parent-absent-mark to MVP Phase 2 | Core value prop delivered at demo; parents see immediate safety benefit; interconnected flows tested early | Adds ~1 week to Phase 2 (Weeks 5-6 become Weeks 5-7); driver UI gets more complex |
| **Option B: Safety in V2** | Keep attendance and all safety features in V2 as originally planned | MVP stays at 6 weeks; simpler driver UI for demo | Demo has no safety differentiation; "just a map" is not compelling; safety flows not tested until Week 10+ |

**Decision: Option A -- Safety in MVP**
**Rationale:** A school bus tracking system without child safety alerts is a map, not a product. Attendance marking is the prerequisite for both safety alerts. The interconnected flow (absent mark -> skip stop -> no false alert; boarded but not dropped -> critical alert) is the core value proposition. Adding ~1 week to MVP (now 7 weeks) is worth it.
**Invalidation of Option B:** Deferring safety to V2 means the week-6 demo shows GPS tracking only. Schools evaluating the system will ask "what happens if my child doesn't get off the bus?" and the answer would be "that's coming later." Unacceptable for a child transport system.

### ADR (Revision 2 Addendum)

| Field | Value |
|-------|-------|
| **Decision** | Promote attendance + safety alerts to MVP. Add structured logging enhancements to Phase 1. Add substitute driver, multi-child, feedback, complaints, compliance reports to V2. |
| **Drivers** | Child safety non-negotiable in MVP, production logging from day 1, operational features fit V2 timeline |
| **Alternatives Considered** | Keep all safety in V2 (rejected: demo has no differentiator). Add all 12 features to MVP (rejected: scope creep, 6-week target becomes 10+). |
| **Why Chosen** | Safety features are the product's core value. Logging is configuration not architecture. V2 operational features are genuinely deferrable. |
| **Consequences** | MVP extends from 6 weeks to ~7 weeks. Driver UI adds attendance + absent-mark screens. Phase 2 Step 4 grows. V2 loses attendance (already done) but gains 5 new features. |
| **Follow-ups** | Validate safety alert UX with a real school admin before Week 5. Load-test attendance marking with 50 students per trip. |

---

## 2. Specific Plan Changes

### CHANGE 1: Logging Enhancements (Phase 1, Step 1)

**Where:** Section 8, Phase 1, Step 1 (Project Scaffolding & Core Infrastructure)
**What:** Extend the existing structlog setup bullet point.

**Add to Step 1 task list (after existing structlog bullet):**

```
- Logging configuration by environment:
  - Log levels: dev=DEBUG, staging=WARNING, prod=WARNING (configurable via LOG_LEVEL env var)
  - structlog processors chain: add_log_level -> add_timestamp -> add_request_context -> scrub_sensitive -> JSONRenderer
  - Sensitive data scrubbing processor: mask phone numbers (show last 4 digits: ***1234),
    mask GPS coordinates in logs (round to 2 decimal places: 28.61, 77.23 -> for debugging without exact location),
    mask email addresses (show domain only: ***@school.com)
  - Scrubbing applies to ALL log output including Celery task logs
  - Implementation: single structlog processor function in app/core/logging.py (~30 lines)

- Celery task logging:
  - Configure Celery to use structlog (celery.signals.setup_logging)
  - Every Celery task logs: task_name, task_id, school_id, duration_ms, status (success/failure)
  - GPS cleanup job logs: partitions_dropped, rows_affected, duration_ms
  - Notification dispatch logs: notification_type, recipient_count, failures
  - Add structlog context to all existing Celery tasks (GPS cleanup, insurance expiry check)

- Log retention / auto-cleanup:
  - If using file-based logs (VPS deployment): logrotate config with configurable retention (default: 30 days)
  - If using stdout (Railway/Docker): no file cleanup needed -- Railway/Docker handle log rotation
  - Add LOG_RETENTION_DAYS env var (default: 30) for file-based deployments
  - Add logrotate.conf to docker/ directory for VPS tier
  - For structured log storage (V2): forward to Loki with retention policy
```

**Update Step 1 Acceptance Criteria -- add:**
```
- Structured logs show masked phone numbers and rounded GPS coordinates.
- Celery task completion logs include task_name, duration_ms, status.
- LOG_LEVEL=WARNING suppresses DEBUG/INFO in prod.
```

**DB Schema changes:** None.
**API changes:** None.
**New files:** `app/core/logging.py` (structlog processor chain + scrubbing), `docker/logrotate.conf`

---

### CHANGE 2: Child Not-Boarded Alert (MVP Phase 2 -- NEW)

**Where:** Section 5 (Feature List MVP), Section 6 (DB Schema), Section 7 (API), Section 8 (Task Breakdown Phase 2)
**Phase:** MVP (promoted from implicit future)
**Prerequisite:** Attendance marking (also promoted to MVP -- see Change 4)

**Add to Feature List MVP table:**

```
| M11 | Attendance marking at stops (driver marks boarded/absent per student) | P0 |
| M12 | Child not-boarded alert: if assigned student not marked boarded at their stop -> auto-alert parent + admin via Socket.IO | P0 |
| M13 | Child safeguarding alert: if trip ends but student marked boarded and NOT marked dropped -> CRITICAL alert to admin | P0 |
| M14 | Parent marks child absent: parent taps "child won't ride today" before trip -> driver sees visual skip indicator, stop auto-skipped if no other students | P1 |
```

**DB Schema additions:**

Add to `attendance_records` table (promote from V2 to MVP):
```
attendance_records
------------------
id (PK, UUID)
trip_id (FK -> trips)
school_id (FK -> schools)                    -- NEW: direct scoping for multi-tenancy (no join needed)
student_id (FK -> students)
stop_id (FK -> route_stops)
status (enum: boarded, absent, absent_parent_marked)
              -- NOTE: 'dropped' removed — drop-off tracked via dropped_at column only.
              -- 'not_boarded' removed — not_boarded means no record exists (absent from list).
              -- Query for "on bus now": status='boarded' AND dropped_at IS NULL
marked_at (TIMESTAMPTZ)
marked_by (FK -> users)       -- NEW: driver who marked, or parent (for absent_parent_marked)
marked_location (PostGIS POINT)
drop_stop_id (FK -> route_stops, nullable)   -- NEW: where student was dropped off
dropped_at (TIMESTAMPTZ, nullable)           -- NEW: when student was dropped off (non-null = dropped)
created_at

UNIQUE(trip_id, student_id)   -- prevent duplicate records per student per trip
INDEX: (trip_id, stop_id)
INDEX: (school_id, trip_id)
```

Add columns to `trips` table:
```
trips (add columns)
-------------------
safeguarding_checked (BOOLEAN DEFAULT FALSE)  -- flag: end-of-trip safeguarding check completed
```

Add to `alerts` table type enum (promote alerts table from V2 to MVP, but only with safety-related types):
```
alerts (promote to MVP, limited types)
------
type enum: ADD 'child_not_boarded', 'child_not_dropped' to existing enum
           (keep sos, route_deviation, incident, etc. for V2)
severity: 'child_not_dropped' is always CRITICAL
          'child_not_boarded' is always HIGH
```

**API additions:**

```
# Attendance (promote to MVP)
# Stop-scoped: submitting this batch IS the "complete stop" action — triggers not-boarded detection
POST   /api/v1/trips/{trip_id}/stops/{stop_id}/attendance
  Request:  { attendance: [{ student_id: UUID, status: "boarded" | "absent" }] }
  Response: { processed: int, alerts_triggered: int }
  Logic:    On submit, compare submitted list against student_route_assignments for this stop_id.
            Any assigned student absent from list AND NOT absent_parent_marked → child_not_boarded alert.
            Idempotent: re-submitting same stop replaces previous records (UPSERT on trip_id+student_id).

GET    /api/v1/trips/{trip_id}/attendance           # Get full attendance for trip
GET    /api/v1/trips/{trip_id}/stops/{stop_id}/attendance  # Get attendance for one stop

# Drop-off marking (batch at end of trip or per-stop)
POST   /api/v1/trips/{trip_id}/drop
  Request:  { student_ids: [UUID], stop_id: UUID }  # batch drop-off for multiple students at once
  Response: { dropped: int }
  # Driver can call once at school with all boarded students → eliminates 50 individual taps

# Parent absent marking (MVP)
POST   /api/v1/trips/{trip_id}/absent/{student_id}  # Parent marks child absent for this trip
DELETE /api/v1/trips/{trip_id}/absent/{student_id}  # Parent cancels absent mark (if trip not started)
GET    /api/v1/trips/{trip_id}/absences             # Driver gets list of pre-marked absences

# Alerts (MVP - safety only)
GET    /api/v1/alerts                    # List alerts (admin, filterable)
PUT    /api/v1/alerts/{id}/acknowledge   # Admin acknowledges alert
PUT    /api/v1/alerts/{id}/resolve       # Admin resolves alert (auto-transitions trip if last unresolved)
```

**Socket.IO events (add to existing list):**

```
# Server -> Client (NEW)
"attendance_update"     {trip_id, student_id, student_name, status, stop_name}  # To parent when their child marked
"child_not_boarded"     {trip_id, student_id, student_name, stop_name}          # To parent + admin room
"child_not_dropped"     {trip_id, student_id, student_name, severity: "critical"}  # To admin room (CRITICAL)
"child_absent_marked"   {trip_id, student_id, student_name}                     # To driver (parent marked absent)
```

**Safety logic (in `app/tracking/safety.py`):**

```
Child Not-Boarded Detection:
- Trigger: POST /trips/{trip_id}/stops/{stop_id}/attendance batch submission
  (submitting the batch IS the explicit "complete stop" action)
- Server queries student_route_assignments WHERE stop_id = submitted stop_id
- For each assigned student NOT in submitted attendance list AND NOT absent_parent_marked:
    -> Create alert (type=child_not_boarded, severity=HIGH)
    -> Emit "child_not_boarded" to parent's Socket.IO room + admin room
    -> Create in-app notification for parent + admin
- If student IS marked absent_parent_marked: no alert, log as expected absence

Child Safeguarding (Not Dropped) Detection:
- Trigger: PUT /trips/{id}/end
- Query: SELECT student_id FROM attendance_records
         WHERE trip_id=X AND status='boarded' AND dropped_at IS NULL
- If any unaccounted students found:
    -> Create alert (type=child_not_dropped, severity=CRITICAL) per student
    -> Emit "child_not_dropped" to admin room (Socket.IO)
    -> Trip status → "pending_safeguard_check" (NOT "completed")
    -> Return HTTP 200 with body: {status: "pending_safeguard_check", unresolved_students: [...]}
- If no unaccounted students: trip status → "completed" immediately.

Resolution flow for pending_safeguard_check:
- Two resolution paths exist (admin and driver). Both use the same atomic guard to prevent
  race conditions if both paths fire simultaneously:

  Path A (admin): PUT /api/v1/alerts/{id}/resolve
    -> After resolving alert, check: any unresolved child_not_dropped alerts remain for this trip?
    -> If none: run atomic transition (see below)

  Path B (driver): POST /trips/{trip_id}/drop (marks missed student dropped)
    -> Auto-resolves the corresponding child_not_dropped alert for that student
    -> Check: any unresolved child_not_dropped alerts remain for this trip?
    -> If none: run atomic transition (see below)

  Atomic transition (both paths use this):
    UPDATE trips SET status = 'completed', safeguarding_checked = TRUE
    WHERE id = :trip_id AND status = 'pending_safeguard_check'
    -- Returns rows_affected. Emit "trip_completed" Socket.IO event ONLY if rows_affected > 0.
    -- Idempotent: second concurrent caller updates 0 rows, emits nothing. No double notifications.

Parent Absent Marking:
- Parent calls POST /trips/{trip_id}/absent/{student_id} before trip starts
- Creates attendance_record with status=absent_parent_marked, marked_by=parent.id
- Emit "child_absent_marked" to driver's Socket.IO room
- Driver UI shows visual indicator (greyed out student, "Parent: won't ride today")
- If no other students assigned to that stop: show "Skip this stop?" suggestion to driver
- Cancellation: allowed only if trip.status != 'in_progress'
```

**Add to trips status enum:**
```
status enum: ADD 'pending_safeguard_check' between 'in_progress' and 'completed'
```

---

### CHANGE 3: Update Task Breakdown for Safety (Phase 2)

**Where:** Section 8, Phase 2

**Modify Step 4 (Trip Management & Real-Time GPS Tracking) -- add sub-tasks:**

```
- Attendance marking endpoint (driver marks students at each stop)
  - Driver UI: at each stop, show assigned students with checkboxes (boarded / not present)
  - POST /trips/{trip_id}/stops/{stop_id}/attendance with batch student statuses
    Body: { attendance: [{ student_id: UUID, status: "boarded" | "absent" }] }
    Idempotent via UPSERT on (trip_id, student_id)
  - Real-time notification to parent via Socket.IO on attendance mark

- Safety alert system (app/tracking/safety.py):
  - Child not-boarded detection: triggered when driver completes a stop's attendance
  - Child not-dropped detection: triggered when driver ends trip
  - Parent absent marking: pre-trip endpoint + driver UI indicator
  - Alert creation + Socket.IO broadcast + in-app notification

- Driver drop-off marking:
  - POST /trips/{trip_id}/drop/{student_id} marks student as dropped
  - Simple button per student on driver's "boarded students" list
  - Required before trip can complete (safeguarding gate)
```

**Modify Step 5 (Frontend MVP) -- add:**

```
- Driver view: attendance screen at each stop (student list with board/absent toggles)
- Driver view: "boarded students" panel with drop-off buttons
- Driver view: absent-marked students shown greyed out with "Parent: won't ride" label
- Parent view: "Mark absent for today" button on upcoming trip card
- Parent view: notification banner when child boarded / not boarded
- Admin view: safety alerts panel on dashboard (list of unacknowledged alerts, CRITICAL highlighted)
```

**Update Step 4 Acceptance Criteria -- add:**
```
- Driver marks 3 students boarded at stop. 1 assigned student not marked -> parent receives "child not boarded" alert within 2s.
- Driver ends trip with 1 student still marked boarded (not dropped) -> CRITICAL alert appears on admin dashboard within 2s.
- Parent marks child absent -> driver sees greyed student at that stop. No "not boarded" alert fires for that student.
- Trip with unresolved safeguarding issue cannot move to "completed" status.
```

**Update MVP timeline:** Weeks 1-6 becomes Weeks 1-8 (attendance + safety + frontend + tests = ~2 weeks for a solo dev, not 1).

**Update Week 8 Demo Success Criteria (was Week 6):**
```
Original criteria remain, PLUS:
- Driver marks attendance at each stop. Parent whose child was not marked receives alert.
- Parent marks child absent before trip. Driver sees skip indicator. No false alert.
- Driver ends trip with student still "boarded" -> admin sees CRITICAL safeguarding alert.
```

---

### CHANGE 4: Substitute Driver Flow (V2)

**Where:** Section 5 (V2 Feature List), Section 7 (API), Section 8 (V2 Task Breakdown)
**Phase:** V2

**Add to V2 Feature List:**

```
| V14 | Substitute driver flow: admin reassigns trip to substitute driver when primary is absent | P1 |
```

**DB Schema additions:**

Add columns to `trips` table:
```
trips (add columns)
-------------------
original_driver_id (FK -> users, nullable)   -- original driver before substitution
reassigned_at (TIMESTAMPTZ, nullable)        -- when substitution happened
reassignment_reason (VARCHAR, nullable)      -- "driver_absent", "vehicle_issue", etc.
```

**API additions:**

```
PUT    /api/v1/trips/{trip_id}/reassign    # Admin reassigns trip to different driver
  Body: { driver_id: UUID, vehicle_id: UUID (optional), reason: string }
  Logic:
    - Validates new driver is available (no conflicting trip)
    - Stores original_driver_id if first reassignment
    - Updates trip.driver_id and optionally trip.vehicle_id
    - Emits Socket.IO "trip_reassigned" to new driver
    - Notifies affected parents (driver name change)
    - Creates audit_log entry
```

**Socket.IO events:**

```
"trip_reassigned"    {trip_id, new_driver_name, vehicle_plate}  # To new driver + subscribed parents
```

**Add to V2 Step 9 (Route Deviation, Notifications & Alerts):**
```
- Substitute driver flow:
  - Admin UI: "Reassign Driver" button on trip detail / schedule view
  - Driver selection modal: shows available drivers (no conflicting trips)
  - On reassign: new driver receives trip details on their dashboard
  - Parents notified of driver change (in-app notification)
  - Audit trail preserved (original_driver_id, reassignment_reason)
```

---

### CHANGE 5: Multiple Children, One Parent Dashboard (V2)

**Where:** Section 5 (V2 Feature List), Section 7 (API), Section 8 (V2 Task Breakdown)
**Phase:** V2

**Add to V2 Feature List:**

```
| V15 | Multi-child parent dashboard: single view showing all children, different buses, different ETAs | P1 |
```

**DB Schema changes:** None needed. The existing schema already supports multiple students per parent (`students.parent_id` FK). This is purely a frontend + API aggregation change.

**API additions:**

```
GET    /api/v1/parents/dashboard    # Aggregated parent dashboard
  Response: {
    children: [
      {
        student: { id, name, grade },
        route: { id, name },
        stop: { id, name, arrival_time },
        active_trip: {              # null if no active trip
          id, status, driver_name, vehicle_plate,
          current_location: { lat, lng, updated_at },
          eta_to_stop_seconds: int
        },
        today_attendance: { status, marked_at } | null,
        absent_marked: boolean
      },
      ...  # one entry per child
    ]
  }
```

**Socket.IO changes:** Parent already joins rooms per trip. With multiple children on different routes, client joins multiple trip rooms. No server change needed -- client-side logic subscribes to N trip rooms.

**Frontend changes (V2):**
```
- Parent dashboard redesign: card-per-child layout
- Each card shows: child name, bus/route, live map thumbnail, ETA, attendance status
- Tapping a card expands to full map view for that child's bus
- "Mark absent" button per child
- Notifications grouped by child
```

---

### CHANGE 6: Feedback and Rating (V2)

**Where:** Section 5 (V2 Feature List), Section 6 (DB Schema), Section 7 (API)
**Phase:** V2

**Add to V2 Feature List:**

```
| V16 | Parent feedback & rating: rate driver after trip ends, admin reviews flagged patterns | P2 |
```

**DB Schema -- new table:**

```
trip_feedback
-------------
id (PK, UUID)
trip_id (FK -> trips)                -- one feedback per parent per trip
parent_id (FK -> users)
driver_id (FK -> users)              -- denormalized for query efficiency
school_id (FK -> schools)
rating (SMALLINT, 1-5)
comment (TEXT, nullable, max 500 chars)
is_flagged (BOOLEAN DEFAULT FALSE)   -- auto-flag if rating <= 2
admin_reviewed (BOOLEAN DEFAULT FALSE)
admin_notes (TEXT, nullable)
created_at (TIMESTAMPTZ)

UNIQUE(trip_id, parent_id)           -- one feedback per parent per trip (not one total per trip)
INDEX: (driver_id, created_at DESC)
INDEX: (school_id, is_flagged, admin_reviewed)
```

**API:**

```
POST   /api/v1/trips/{trip_id}/feedback          # Parent submits rating (1-5) + optional comment
GET    /api/v1/drivers/{driver_id}/feedback       # Admin views driver's feedback history
GET    /api/v1/feedback?flagged=true              # Admin views flagged feedback
PUT    /api/v1/feedback/{id}/review               # Admin marks feedback as reviewed + adds notes
GET    /api/v1/analytics/driver-ratings           # Driver rating averages + trends (admin)
```

**Auto-flagging logic:**
```
- Rating <= 2: auto-set is_flagged=TRUE
- If driver has 3+ flagged ratings in 30 days: create alert (type=driver_behavior_pattern, severity=HIGH)
- Admin reviews flagged feedback, adds notes, resolves
```

---

### CHANGE 7: Complaints System (V2)

**Where:** Section 5 (V2 Feature List), Section 6 (DB Schema), Section 7 (API)
**Phase:** V2

**Add to V2 Feature List:**

```
| V17 | Formal complaints system: tracked status, resolution timeline, separate from chat | P2 |
```

**DB Schema -- new table:**

```
complaints
----------
id (PK, UUID)
school_id (FK -> schools)
submitted_by (FK -> users)            -- parent or driver
against_type (enum: driver, route, vehicle, general)
against_id (UUID, nullable)           -- FK to relevant entity
trip_id (FK -> trips, nullable)       -- related trip if applicable
subject (VARCHAR 200)
description (TEXT, max 2000 chars)
status (enum: open, in_review, resolved, closed)
priority (enum: low, medium, high, urgent)
assigned_to (FK -> users, nullable)   -- admin handling the complaint
resolution_notes (TEXT, nullable)
resolved_at (TIMESTAMPTZ, nullable)
created_at (TIMESTAMPTZ)
updated_at (TIMESTAMPTZ)

INDEX: (school_id, status, created_at DESC)
INDEX: (submitted_by, created_at DESC)
```

**API:**

```
POST   /api/v1/complaints                    # Parent/driver submits complaint
GET    /api/v1/complaints                    # List complaints (admin: all; parent: own)
GET    /api/v1/complaints/{id}               # Get complaint details
PUT    /api/v1/complaints/{id}/assign        # Admin assigns to themselves or another admin
PUT    /api/v1/complaints/{id}/resolve       # Admin resolves with notes
PUT    /api/v1/complaints/{id}/status        # Update status (in_review, closed)
```

**Note:** Complaints are NOT chat. No real-time messaging. Simple form submission + status tracking. Admin gets notification when new complaint filed. Parent gets notification when status changes.

---

### CHANGE 8: Compliance Report Generation (V2)

**Where:** Section 5 (V2 Feature List), Section 7 (API), Section 8 (V2 Task Breakdown)
**Phase:** V2

**Add to V2 Feature List:**

```
| V18 | Compliance report generation: PDF/Excel export of trips, incidents, attendance %, for transport authority | P2 |
```

**API:**

```
POST   /api/v1/reports/generate              # Admin triggers report generation (async via Celery)
  Body: {
    type: "compliance" | "attendance" | "incident" | "trip_summary",
    format: "pdf" | "xlsx",
    date_from: DATE,
    date_to: DATE,
    route_ids: [UUID] (optional, all routes if empty)
  }
  Response: { report_id: UUID, status: "generating" }

GET    /api/v1/reports/{id}                  # Check report status + download URL
GET    /api/v1/reports                       # List generated reports (paginated)
DELETE /api/v1/reports/{id}                  # Delete generated report
```

**Implementation:**
```
- Celery task: generate_compliance_report(report_id)
- PDF: use reportlab (pure Python, zero system deps — weasyprint rejected: requires Cairo/Pango system packages, violates "no new infrastructure deps" principle)
- Excel: use openpyxl
- Report contents:
  - Trip summary: total trips, completed, cancelled, on-time %
  - Attendance: per-route attendance %, absent patterns
  - Incidents: list of alerts/incidents with timestamps, resolution status
  - Driver performance: trips per driver, rating average (if feedback enabled)
- Generated file stored in S3-compatible storage (Cloudflare R2)
- Report link expires after 7 days (presigned URL)
- Auto-cleanup: Celery periodic task deletes reports older than 30 days
```

**DB Schema -- new table:**

```
reports
-------
id (PK, UUID)
school_id (FK -> schools)
generated_by (FK -> users)
type (enum: compliance, attendance, incident, trip_summary)
format (enum: pdf, xlsx)
date_from (DATE)
date_to (DATE)
status (enum: pending, generating, completed, failed)
file_url (VARCHAR, nullable)        -- S3/R2 presigned URL
file_size_bytes (INT, nullable)
error_message (TEXT, nullable)
created_at (TIMESTAMPTZ)
completed_at (TIMESTAMPTZ, nullable)
expires_at (TIMESTAMPTZ)            -- file auto-deleted after this

INDEX: (school_id, created_at DESC)
```

---

### CHANGE 9: Update Section 5 Feature Lists (consolidated)

**MVP Feature List -- add rows:**

```
| M11 | Student attendance marking at stops (driver marks boarded/absent per student, parent notified) | P0 |
| M12 | Child not-boarded alert (assigned student not marked at stop -> alert parent + admin) | P0 |
| M13 | Child safeguarding: not-dropped alert (trip ends, student boarded but not dropped -> CRITICAL alert to admin) | P0 |
| M14 | Parent marks child absent ("won't ride today" -> driver sees skip indicator, no false alert) | P1 |
```

**V2 Feature List -- add rows:**

```
| V14 | Substitute driver flow (admin reassigns trip to available substitute driver) | P1 |
| V15 | Multi-child parent dashboard (single view, all children, different buses, different ETAs) | P1 |
| V16 | Parent feedback & rating (rate driver after trip, flagged patterns for admin review) | P2 |
| V17 | Formal complaints system (form submission, tracked status, resolution notes, separate from chat) | P2 |
| V18 | Compliance report generation (PDF/Excel: trips, incidents, attendance %, for transport authority) | P2 |
```

**V2 Feature List -- REMOVE (promoted to MVP):**

```
REMOVE: V5 (Student attendance marking) -- now M11 in MVP
```

**Future Feature List -- REMOVE (promoted to V2):**

```
REMOVE: F5 (Parent feedback / rating system) -- now V16 in V2
REMOVE: F8 (Sibling management) -- now V15 in V2 (multi-child dashboard)
REMOVE: F9 (Substitute driver assignment) -- now V14 in V2
```

---

### CHANGE 10: Update Section 12 (Monitoring & Observability)

**Add to Section 12.1 (MVP Monitoring Stack):**

```
| **Logging config** | structlog + custom processors | 2 hours | Log levels per env (dev=DEBUG, prod=WARNING). Sensitive data scrubbing (phones, GPS, emails). Celery task logging with duration + status. |
| **Log retention** | logrotate (VPS) / platform-managed (Railway) | 30 min | Configurable via LOG_RETENTION_DAYS env var (default: 30 days). |
```

---

### CHANGE 11: Update Edge Cases & Mitigations Table

**Add rows:**

```
| **Child not boarded** | When driver marks attendance at a stop, system checks all assigned students. Unmarked students (not absent-marked by parent) trigger HIGH alert to parent + admin via Socket.IO within 2s. |
| **Child not dropped (safeguarding)** | When driver ends trip, system checks all boarded students have drop-off records. Any student still "boarded" triggers CRITICAL alert. Trip moves to "pending_safeguard_check" status until resolved. |
| **Parent marks absent after trip starts** | Rejected. Absent marking only allowed before trip status = in_progress. If parent misses the window, they must contact admin. |
| **Driver forgets attendance** | Trip cannot end without attendance marked at all stops with assigned students. Driver UI enforces this (stop-by-stop flow). If truly skipped, all assigned students at that stop treated as "not boarded" -> alerts fire. |
| **Substitute driver unfamiliar with route** | On reassignment, substitute receives full route details (ordered stops, student list, map). Same driver UI as primary driver. No special onboarding needed. |
| **Log storage overflow (VPS)** | logrotate with LOG_RETENTION_DAYS (default 30). Celery daily task for application-level log table cleanup if persisted to DB. |
```

---

### CHANGE 12: Update Guardrails

**Add to "Must Have":**

```
- Child safeguarding check on every trip end (no trip completes without all boarded students accounted for)
- Sensitive data scrubbed from all logs (phone numbers masked, GPS coordinates rounded)
- Celery tasks produce structured logs with task_id, duration, status
- Log levels configurable per environment via LOG_LEVEL env var
```

**Add to "Must NOT Have":**

```
- No exact phone numbers or GPS coordinates in log output (scrubbing processor enforced)
- No trip completion without safeguarding check (boarded students must all be dropped or accounted for)
- No "not boarded" alerts for parent-marked-absent students (interconnected flow prevents false positives)
```

---

## 3. Summary of All Changes

| # | Change | Phase | Impact |
|---|--------|-------|--------|
| 1 | Logging: levels, scrubbing, Celery logging, retention | MVP Phase 1 Step 1 | Config work, ~2 hours, 1 new file |
| 2 | Child not-boarded alert | MVP Phase 2 | New safety.py, extends attendance, alerts table promoted |
| 3 | Child safeguarding: not dropped | MVP Phase 2 | Part of safety.py, trip end hook |
| 4 | Parent marks child absent | MVP Phase 2 | New endpoint, driver UI indicator |
| 5 | Substitute driver flow | V2 | 3 columns on trips table, 1 endpoint, 1 Socket.IO event |
| 6 | Multi-child parent dashboard | V2 | 1 aggregation endpoint, frontend card layout |
| 7 | Feedback & rating | V2 | 1 new table, 4 endpoints, auto-flagging logic |
| 8 | Complaints system | V2 | 1 new table, 5 endpoints, status tracking |
| 9 | Compliance reports | V2 | 1 new table, 1 Celery task, PDF/Excel generation |
| 10 | Monitoring update | MVP Phase 1 | Documentation/config only |
| 11 | Edge cases update | All phases | Documentation only |
| 12 | Guardrails update | All phases | Documentation only |

### New DB Tables (3)
- `trip_feedback` (V2)
- `complaints` (V2)
- `reports` (V2)

### Promoted Tables (2, from V2 to MVP)
- `attendance_records` (was V2, now MVP)
- `alerts` (was V2, now MVP -- limited to safety types only)

### Modified Tables (1)
- `trips` -- add columns: `safeguarding_checked`, `original_driver_id`, `reassigned_at`, `reassignment_reason`

### New API Endpoints (18 total)
- MVP: 6 endpoints (attendance, drop-off, absent marking, alerts)
- V2: 12 endpoints (reassign, parent dashboard, feedback, complaints, reports)

### New Socket.IO Events (5)
- MVP: `child_not_boarded`, `child_not_dropped`, `child_absent_marked`, `attendance_update`
- V2: `trip_reassigned`

### New Files
- `app/core/logging.py` -- structlog processor chain + sensitive data scrubbing
- `app/tracking/safety.py` -- child safety alert logic (not-boarded, not-dropped, absent marking)
- `app/communication/complaints.py` -- complaints CRUD (V2)
- `app/reports/` -- report generation module (V2)
- `docker/logrotate.conf` -- log rotation config for VPS deployments

### Timeline Impact
- MVP: 6 weeks -> ~8 weeks (attendance + safety + frontend + tests = ~2 weeks for solo dev)
- V2: Weeks 9-16 (shifted by 2 weeks; net: 5 new features added, V5 attendance removed since promoted to MVP)

### Key Decisions Made (Critic/Architect fixes applied)
- "Complete stop" trigger: POST /trips/{trip_id}/stops/{stop_id}/attendance batch submission IS the trigger
- pending_safeguard_check resolution: auto-transitions to completed when last child_not_dropped alert resolved
- trip_feedback UNIQUE: UNIQUE(trip_id, parent_id) — one rating per parent per trip
- attendance_records status enum: boarded | absent | absent_parent_marked only (dropped removed, tracked via dropped_at)
- school_id added to attendance_records for direct multi-tenancy scoping
- UNIQUE(trip_id, student_id) added to attendance_records
- Batch drop-off endpoint: POST /trips/{trip_id}/drop with {student_ids: [UUID], stop_id: UUID}
- PDF library: reportlab (pure Python, zero system deps; weasyprint rejected)
