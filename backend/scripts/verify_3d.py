"""
Verification script for Chunk 3D: Students + Transport Requests + suggest-stop.

Run:  cd backend && uv run python -m scripts.verify_3d

Tests:
  1. Seed DB (fresh or reuse), capture join_code + admin creds.
  2. Register a parent via join_code → token.
  3. Parent POST /students → 201 child created.
  4. Admin creates a route with 2 stops at known coords.
  5. Parent GET /transport-requests/suggest-stop?lat=&lng= → suggestions sorted ascending.
  6. Parent POST /transport-requests {student_id, pickup_location} → 201 pending.
  7. Admin PUT /transport-requests/{id} {status:'assigned', ...} → 200, assignment row exists.
  8. Capacity guard: vehicle.capacity=1, fill route, then assign another → 409.
  9. Cross-tenant: parent of school A cannot see school B students/requests (404/empty).
"""

import asyncio
import secrets
import sys
import uuid

import httpx
from httpx import ASGITransport
from sqlalchemy import func, select

from app.auth.models import User
from app.core.security import hash_password
from app.database import SessionLocal
from app.main import app
from app.schools.models import School
from app.students.models import StudentRouteAssignment


def _random_join_code(length: int = 8) -> str:
    import string

    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def ok(label: str, value=None):
    print(f"  PASS  {label}" + (f": {value}" if value else ""))


def fail(label: str, resp=None):
    detail = ""
    if resp is not None:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
    print(f"  FAIL  {label}: status={getattr(resp, 'status_code', '?')} body={detail}")
    sys.exit(1)


async def main():
    # Flush rate-limit keys so repeated script runs don't hit auth 5/min limit
    from app.redis_client import get_redis
    r = get_redis()
    rl_keys = await r.keys("ratelimit:*")
    if rl_keys:
        await r.delete(*rl_keys)

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True
    ) as client:
        print("\n=== Chunk 3D Verification ===\n")

        # ------------------------------------------------------------------
        # Seed school A + admin
        # ------------------------------------------------------------------
        async with SessionLocal() as db:
            school_a = (await db.execute(select(School).limit(1))).scalar_one_or_none()
            if school_a is None:
                school_a = School(
                    name="Demo School A",
                    join_code=_random_join_code(),
                    settings={},
                    is_active=True,
                )
                db.add(school_a)
                await db.commit()
                await db.refresh(school_a)
            join_code_a = school_a.join_code
            school_a_id = school_a.id

            # Ensure admin user exists
            admin_email = "admin@yatratest.example"
            admin_pw = "Admin1234!"
            admin_exists = (
                await db.execute(select(User).where(func.lower(User.email) == admin_email))
            ).scalar_one_or_none()
            if admin_exists is None:
                admin = User(
                    school_id=school_a_id,
                    email=admin_email,
                    password_hash=hash_password(admin_pw),
                    full_name="Test Admin",
                    role="school_admin",
                    is_active=True,
                    email_verified=True,
                )
                db.add(admin)
                await db.commit()
            print(f"  School A: join_code={join_code_a}  admin={admin_email}")

            # School B for cross-tenant test
            school_b = (
                await db.execute(select(School).where(School.id != school_a_id).limit(1))
            ).scalar_one_or_none()
            if school_b is None:
                school_b = School(
                    name="Demo School B",
                    join_code=_random_join_code(),
                    settings={},
                    is_active=True,
                )
                db.add(school_b)
                await db.commit()
                await db.refresh(school_b)

            parent_b_email = "parentb@yatratest.example"
            parent_b_pw = "Parent1234!"
            parent_b_exists = (
                await db.execute(
                    select(User).where(func.lower(User.email) == parent_b_email)
                )
            ).scalar_one_or_none()
            if parent_b_exists is None:
                pb = User(
                    school_id=school_b.id,
                    email=parent_b_email,
                    password_hash=hash_password(parent_b_pw),
                    full_name="Parent B",
                    role="parent",
                    is_active=True,
                    email_verified=True,
                )
                db.add(pb)
                await db.commit()
            print(f"  School B: join_code={school_b.join_code}")

        # ------------------------------------------------------------------
        # Get admin token
        # ------------------------------------------------------------------
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": admin_email, "password": admin_pw},
        )
        if r.status_code != 200:
            fail("admin login", r)
        admin_token = r.json()["access_token"]
        admin_h = {"Authorization": f"Bearer {admin_token}"}
        ok("admin login")

        # ------------------------------------------------------------------
        # 2. Register a parent via join_code
        # ------------------------------------------------------------------
        parent_email = f"parent_{uuid.uuid4().hex[:6]}@yatratest.example"
        parent_pw = "Parent1234!"
        r = await client.post(
            "/api/v1/auth/register",
            json={
                "join_code": join_code_a,
                "email": parent_email,
                "password": parent_pw,
                "full_name": "Test Parent",
                "phone": "+911234567890",
            },
        )
        if r.status_code != 200:
            fail("parent register", r)
        parent_token = r.json()["access_token"]
        parent_h = {"Authorization": f"Bearer {parent_token}"}
        ok("parent register")

        # ------------------------------------------------------------------
        # 3. Parent POST /students → 201
        # ------------------------------------------------------------------
        r = await client.post(
            "/api/v1/students/",
            json={
                "full_name": "Test Child",
                "grade": "5",
                "section": "A",
                "pickup_address": "123 Main St",
                "pickup_location": {"lat": 28.6139, "lng": 77.2090},
            },
            headers=parent_h,
        )
        if r.status_code != 201:
            fail("parent create student", r)
        student_data = r.json()
        student_id = student_data["id"]
        ok("parent creates student", student_id)

        # ------------------------------------------------------------------
        # 4. Admin creates vehicle + route with 2 stops
        # ------------------------------------------------------------------
        # Create vehicle with capacity 2
        r = await client.post(
            "/api/v1/vehicles",
            json={"plate_number": f"DL{uuid.uuid4().hex[:4].upper()}", "capacity": 2},
            headers=admin_h,
        )
        if r.status_code != 201:
            fail("create vehicle", r)
        vehicle_id = r.json()["id"]
        ok("create vehicle capacity=2", vehicle_id)

        # Create route
        r = await client.post(
            "/api/v1/routes/",
            json={"name": "Test Route 3D", "schedule_type": "both", "vehicle_id": vehicle_id},
            headers=admin_h,
        )
        if r.status_code != 201:
            fail("create route", r)
        route_id = r.json()["id"]
        ok("create route", route_id)

        # Add stop 1 at (28.6129, 77.2295) — the coordinate we'll query suggest-stop from
        r = await client.post(
            f"/api/v1/routes/{route_id}/stops",
            json={
                "name": "Sector 12 Gate",
                "location": {"lat": 28.6129, "lng": 77.2295},
                "arrival_time": "08:00:00",
            },
            headers=admin_h,
        )
        if r.status_code != 201:
            fail("add stop 1", r)
        stop1_id = r.json()["id"]
        ok("add stop 1 (Sector 12 Gate)", stop1_id)

        # Add stop 2 further away
        r = await client.post(
            f"/api/v1/routes/{route_id}/stops",
            json={
                "name": "Market Road",
                "location": {"lat": 28.6200, "lng": 77.2400},
                "arrival_time": "08:15:00",
            },
            headers=admin_h,
        )
        if r.status_code != 201:
            fail("add stop 2", r)
        stop2_id = r.json()["id"]
        ok("add stop 2 (Market Road)", stop2_id)

        # ------------------------------------------------------------------
        # 5. suggest-stop near stop1
        # ------------------------------------------------------------------
        r = await client.get(
            "/api/v1/transport-requests/suggest-stop?lat=28.6129&lng=77.2295",
            headers=parent_h,
        )
        if r.status_code != 200:
            fail("suggest-stop", r)
        suggestions = r.json()["suggestions"]
        assert len(suggestions) <= 3, f"expected <=3 suggestions, got {len(suggestions)}"
        if len(suggestions) >= 2:
            assert (
                suggestions[0]["distance_m"] <= suggestions[1]["distance_m"]
            ), f"suggestions not ascending: {suggestions}"
        dists = [s["distance_m"] for s in suggestions]
        ok(f"suggest-stop returns {len(suggestions)} suggestions sorted ascending", dists)

        # ------------------------------------------------------------------
        # 6. Parent POST /transport-requests → 201 pending
        # ------------------------------------------------------------------
        r = await client.post(
            "/api/v1/transport-requests/",
            json={
                "student_id": student_id,
                "pickup_address": "123 Main St",
                "pickup_location": {"lat": 28.6139, "lng": 77.2090},
            },
            headers=parent_h,
        )
        if r.status_code != 201:
            fail("create transport request", r)
        treq = r.json()
        treq_id = treq["id"]
        assert treq["status"] == "pending", f"expected pending, got {treq['status']}"
        ok("parent creates transport request (pending)", treq_id)

        # ------------------------------------------------------------------
        # 7. Admin PUT → assigned, StudentRouteAssignment row created
        # ------------------------------------------------------------------
        r = await client.put(
            f"/api/v1/transport-requests/{treq_id}",
            json={
                "status": "assigned",
                "assigned_route_id": route_id,
                "assigned_stop_id": stop1_id,
                "admin_notes": "Welcome aboard",
            },
            headers=admin_h,
        )
        if r.status_code != 200:
            fail("admin assign transport request", r)
        assigned = r.json()
        assert assigned["status"] == "assigned", f"expected assigned, got {assigned['status']}"
        ok("admin assigns transport request")

        # Verify StudentRouteAssignment row exists in DB
        async with SessionLocal() as db:
            row = (
                await db.execute(
                    select(StudentRouteAssignment).where(
                        StudentRouteAssignment.student_id == uuid.UUID(student_id),
                        StudentRouteAssignment.route_id == uuid.UUID(route_id),
                        StudentRouteAssignment.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()
            assert row is not None, "StudentRouteAssignment row not found in DB!"
        ok("StudentRouteAssignment row exists in DB")

        # ------------------------------------------------------------------
        # 8. Capacity guard: set vehicle capacity to 1 (already 1 assigned)
        # ------------------------------------------------------------------
        async with SessionLocal() as db:
            from app.vehicles.models import Vehicle as VehicleModel
            veh = (
                await db.execute(
                    select(VehicleModel).where(VehicleModel.id == uuid.UUID(str(vehicle_id)))
                )
            ).scalar_one()
            veh.capacity = 1
            await db.commit()
        ok("set vehicle capacity to 1 (1 student already assigned)")

        # Register another parent and create another student
        parent2_email = f"parent2_{uuid.uuid4().hex[:6]}@yatratest.example"
        r = await client.post(
            "/api/v1/auth/register",
            json={
                "join_code": join_code_a,
                "email": parent2_email,
                "password": parent_pw,
                "full_name": "Test Parent 2",
                "phone": "+911234567891",
            },
        )
        if r.status_code != 200:
            fail("parent2 register", r)
        parent2_token = r.json()["access_token"]
        parent2_h = {"Authorization": f"Bearer {parent2_token}"}

        r = await client.post(
            "/api/v1/students/",
            json={"full_name": "Test Child 2", "grade": "6"},
            headers=parent2_h,
        )
        if r.status_code != 201:
            fail("parent2 create student", r)
        student2_id = r.json()["id"]

        # Try to assign directly to route (capacity should be full)
        r = await client.post(
            f"/api/v1/routes/{route_id}/students",
            json={"student_id": student2_id, "stop_id": stop2_id},
            headers=admin_h,
        )
        if r.status_code != 409:
            fail(f"capacity guard (expected 409, got {r.status_code})", r)
        ok("capacity guard returns 409 when route is full")

        # ------------------------------------------------------------------
        # 9. Cross-tenant: parent of school B cannot see school A data
        # ------------------------------------------------------------------
        # Get school B parent token
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": parent_b_email, "password": parent_b_pw},
        )
        if r.status_code != 200:
            fail("school B parent login", r)
        parent_b_token = r.json()["access_token"]
        parent_b_h = {"Authorization": f"Bearer {parent_b_token}"}

        # School B parent should see empty list for their own school (no students yet)
        r = await client.get("/api/v1/students/", headers=parent_b_h)
        if r.status_code != 200:
            fail("school B parent list students", r)
        b_students = r.json()
        assert b_students["total"] == 0, f"expected 0 for school B, got {b_students['total']}"
        ok("school B parent sees 0 students (cross-tenant isolation)")

        # School B parent cannot get school A's student by ID (404)
        r = await client.get(f"/api/v1/students/{student_id}", headers=parent_b_h)
        if r.status_code != 404:
            fail(f"cross-tenant student access (expected 404, got {r.status_code})", r)
        ok("school B parent gets 404 for school A student")

        # School B parent sees empty transport requests (their school has none)
        r = await client.get("/api/v1/transport-requests/", headers=parent_b_h)
        if r.status_code != 200:
            fail("school B transport request list", r)
        b_treqs = r.json()
        assert b_treqs["total"] == 0, f"expected 0 requests for school B, got {b_treqs['total']}"
        ok("school B parent sees 0 transport requests (cross-tenant isolation)")

        print("\n=== ALL VERIFICATION CHECKS PASSED ===\n")


if __name__ == "__main__":
    asyncio.run(main())
