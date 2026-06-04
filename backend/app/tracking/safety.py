"""
Attendance safety logic — spec §10.1.

process_stop_attendance(db, sio, trip, stop_id, entries):
  1. UPSERT each submitted entry into attendance_records on conflict
     (trip_id, student_id) — update status + stop_id.
  2. Not-boarded detection: students assigned to this route+stop but
     NOT in the submitted entries and NOT already absent_parent_marked
     → create Alert(child_not_boarded), emit socket events, notify parent
     and school admins.
  3. For each boarded entry emit attendance_update to the child's parent.
  4. Commit once. Return {"processed": len(entries), "alerts_triggered": N}.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.models import Alert
from app.auth.models import User
from app.notifications.services import notify
from app.routes.models import RouteStop
from app.students.models import Student, StudentRouteAssignment
from app.tracking.models import AttendanceRecord, Trip

log = structlog.get_logger(__name__)


async def process_stop_attendance(
    db: AsyncSession,
    sio: Any,
    trip: Trip,
    stop_id: uuid.UUID,
    entries: list[dict],  # [{student_id: UUID, status: str}, ...]
) -> dict:
    """
    Upsert submitted attendance, detect not-boarded students, fire alerts.

    Parameters
    ----------
    entries : list of dicts with keys ``student_id`` (UUID) and ``status`` (str).
    """
    # ------------------------------------------------------------------
    # 1. Load the stop name (single query — used for socket payloads)
    # ------------------------------------------------------------------
    stop_row = (
        await db.execute(select(RouteStop).where(RouteStop.id == stop_id))
    ).scalar_one_or_none()
    stop_name: str = stop_row.name if stop_row else str(stop_id)

    # ------------------------------------------------------------------
    # 2. Batch-load student names + parent_ids for submitted entries
    #    (single IN query — no N+1)
    # ------------------------------------------------------------------
    submitted_student_ids = {e["student_id"] for e in entries}
    students_in_entries: dict[uuid.UUID, Student] = {}
    if submitted_student_ids:
        rows = (
            await db.execute(
                select(Student).where(Student.id.in_(submitted_student_ids))
            )
        ).scalars().all()
        students_in_entries = {s.id: s for s in rows}

    # ------------------------------------------------------------------
    # 3. UPSERT attendance entries
    # ------------------------------------------------------------------
    for entry in entries:
        stmt = (
            pg_insert(AttendanceRecord)
            .values(
                school_id=trip.school_id,
                trip_id=trip.id,
                student_id=entry["student_id"],
                stop_id=stop_id,
                status=entry["status"],
                marked_by=trip.driver_id,
            )
            .on_conflict_do_update(
                index_elements=["trip_id", "student_id"],
                set_={
                    "status": entry["status"],
                    "stop_id": stop_id,
                    "marked_by": trip.driver_id,
                },
            )
        )
        await db.execute(stmt)

    # ------------------------------------------------------------------
    # 4. Not-boarded detection
    # ------------------------------------------------------------------
    # 4a. Students assigned to this route + stop (active)
    assigned_rows = (
        await db.execute(
            select(StudentRouteAssignment).where(
                and_(
                    StudentRouteAssignment.route_id == trip.route_id,
                    StudentRouteAssignment.stop_id == stop_id,
                    StudentRouteAssignment.is_active.is_(True),
                )
            )
        )
    ).scalars().all()
    assigned_student_ids = {r.student_id for r in assigned_rows}

    # 4b. Load existing attendance for this trip (for parent-marked-absent check)
    existing_att_rows = (
        await db.execute(
            select(AttendanceRecord).where(
                and_(
                    AttendanceRecord.trip_id == trip.id,
                    AttendanceRecord.student_id.in_(assigned_student_ids),
                )
            )
        )
    ).scalars().all()
    existing_status: dict[uuid.UUID, str] = {r.student_id: r.status for r in existing_att_rows}

    # 4c. Missing = assigned but not in submitted entries
    missing_student_ids = assigned_student_ids - submitted_student_ids

    # 4d. Batch-load missing students in one query
    missing_students: dict[uuid.UUID, Student] = {}
    if missing_student_ids:
        rows = (
            await db.execute(
                select(Student).where(Student.id.in_(missing_student_ids))
            )
        ).scalars().all()
        missing_students = {s.id: s for s in rows}

    alerts_triggered = 0

    for sid in missing_student_ids:
        current_status = existing_status.get(sid)
        if current_status == "absent_parent_marked":
            # Expected absence — skip silently
            log.debug(
                "attendance.expected_absence",
                trip_id=str(trip.id),
                student_id=str(sid),
                stop_id=str(stop_id),
            )
            continue

        student = missing_students.get(sid)
        student_name = student.full_name if student else str(sid)

        # Create alert
        alert = Alert(
            type="child_not_boarded",
            severity="high",
            school_id=trip.school_id,
            trip_id=trip.id,
            title=f"Child not boarded: {student_name} at {stop_name}",
            metadata_={
                "student_id": str(sid),
                "stop_id": str(stop_id),
                "stop_name": stop_name,
                "trip_id": str(trip.id),
            },
        )
        db.add(alert)

        # Socket emit — trip room + school room (best-effort)
        socket_payload = {
            "trip_id": str(trip.id),
            "student_id": str(sid),
            "student_name": student_name,
            "stop_name": stop_name,
        }
        try:
            await sio.emit(
                "child_not_boarded",
                socket_payload,
                room=f"trip:{trip.id}",
            )
            await sio.emit(
                "child_not_boarded",
                socket_payload,
                room=f"school:{trip.school_id}",
            )
        except Exception as exc:
            log.warning(
                "attendance.socket_emit_failed",
                event="child_not_boarded",
                student_id=str(sid),
                exc=str(exc),
            )

        alerts_triggered += 1

        # Notify parent
        if student and student.parent_id:
            try:
                await notify(
                    db,
                    user_id=student.parent_id,
                    school_id=trip.school_id,
                    type="child_not_boarded",
                    title=f"Your child {student_name} was not boarded at {stop_name}",
                    body="Please contact the school for more information.",
                    data={
                        "trip_id": str(trip.id),
                        "student_id": str(sid),
                        "stop_id": str(stop_id),
                    },
                )
            except Exception as exc:
                log.warning(
                    "attendance.notify_parent_failed",
                    student_id=str(sid),
                    exc=str(exc),
                )

        # Notify school admins
        try:
            admin_rows = (
                await db.execute(
                    select(User).where(
                        and_(
                            User.school_id == trip.school_id,
                            User.role == "school_admin",
                            User.is_active.is_(True),
                        )
                    )
                )
            ).scalars().all()
            for admin in admin_rows:
                await notify(
                    db,
                    user_id=admin.id,
                    school_id=trip.school_id,
                    type="child_not_boarded",
                    title=f"Alert: {student_name} not boarded at {stop_name}",
                    body=f"Trip {trip.id} — student did not board at expected stop.",
                    data={
                        "trip_id": str(trip.id),
                        "student_id": str(sid),
                        "stop_id": str(stop_id),
                    },
                )
        except Exception as exc:
            log.warning(
                "attendance.notify_admins_failed",
                student_id=str(sid),
                exc=str(exc),
            )

    # ------------------------------------------------------------------
    # 5. Emit attendance_update for each boarded student → parent room
    # ------------------------------------------------------------------
    for entry in entries:
        if entry["status"] != "boarded":
            continue
        sid = entry["student_id"]
        student = students_in_entries.get(sid)
        if student is None:
            continue
        update_payload = {
            "trip_id": str(trip.id),
            "student_id": str(sid),
            "student_name": student.full_name,
            "status": "boarded",
            "stop_name": stop_name,
        }
        try:
            # Emit to parent's personal room
            parent_room = f"user:{student.parent_id}"
            await sio.emit("attendance_update", update_payload, room=parent_room)
            # Also emit to trip room so admin dashboards see it
            await sio.emit("attendance_update", update_payload, room=f"trip:{trip.id}")
        except Exception as exc:
            log.warning(
                "attendance.emit_update_failed",
                student_id=str(sid),
                exc=str(exc),
            )

    # ------------------------------------------------------------------
    # 6. Single commit for all alerts + upserted attendance rows
    # ------------------------------------------------------------------
    await db.commit()

    log.info(
        "attendance.processed",
        trip_id=str(trip.id),
        stop_id=str(stop_id),
        processed=len(entries),
        alerts_triggered=alerts_triggered,
    )

    return {
        "processed": len(entries),
        "alerts_triggered": alerts_triggered,
    }
