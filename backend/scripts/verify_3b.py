"""
In-process verification for Chunk 3B — Vehicles + Drivers.
Uses httpx ASGITransport (no uvicorn needed).
"""

import asyncio
import time

from httpx import ASGITransport, AsyncClient

from app.main import app

# Unique suffix per run so re-runs don't collide with leftover DB state.
_RUN = str(int(time.time()))[-5:]

BASE = "http://test"

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}" + (f"  ← {detail}" if detail else ""))
    if not condition:
        print(f"         detail: {detail}")


async def login(client: AsyncClient, email: str, password: str) -> str:
    r = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


async def seed_school_b(client: AsyncClient, super_token: str) -> tuple[str, str]:
    """Create a second school + admin for cross-tenant testing."""
    import secrets
    import string

    from sqlalchemy import func, select

    from app.auth.models import User
    from app.core.security import hash_password
    from app.database import SessionLocal
    from app.schools.models import School

    email_b = "admin_b@schoolb.example.com"
    pw_b = "SecretB1234!"

    async with SessionLocal() as db:
        # school B
        result = await db.execute(select(School).where(School.name == "School B"))
        existing = result.scalar_one_or_none()
        if existing is None:
            alphabet = string.ascii_uppercase + string.digits
            code = "".join(secrets.choice(alphabet) for _ in range(8))
            school_b = School(name="School B", join_code=code, is_active=True)
            db.add(school_b)
            await db.commit()
            await db.refresh(school_b)
        else:
            school_b = existing

        # admin B
        existing_admin = (
            await db.execute(select(User).where(func.lower(User.email) == email_b))
        ).scalar_one_or_none()
        if existing_admin is None:
            admin_b = User(
                school_id=school_b.id,
                email=email_b,
                password_hash=hash_password(pw_b),
                full_name="Admin B",
                role="school_admin",
                is_active=True,
                email_verified=True,
            )
            db.add(admin_b)
            await db.commit()

    return email_b, pw_b


async def main() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        # ── Login as school_admin A ──────────────────────────────────────────
        print("\n=== Auth ===")
        token_a = await login(client, "admin@demo.school", "Admin1234!")
        print("  [PASS] school_admin login ok")

        headers_a = {"Authorization": f"Bearer {token_a}"}

        # ── POST vehicle — 201 ───────────────────────────────────────────────
        PLATE = f"DL{_RUN}AA"   # unique per run
        print(f"\n=== Vehicle CRUD (plate={PLATE}) ===")
        r = await client.post(
            "/api/v1/vehicles/",
            headers=headers_a,
            json={"plate_number": PLATE, "capacity": 40},
        )
        check("POST vehicle → 201", r.status_code == 201, r.text)
        vehicle_id = r.json().get("id", "")

        # ── Duplicate plate → 409 ────────────────────────────────────────────
        r2 = await client.post(
            "/api/v1/vehicles/",
            headers=headers_a,
            json={"plate_number": PLATE, "capacity": 20},
        )
        check("duplicate plate → 409", r2.status_code == 409, r2.text)

        # ── capacity=0 → 422 ─────────────────────────────────────────────────
        r3 = await client.post(
            "/api/v1/vehicles/",
            headers=headers_a,
            json={"plate_number": f"DL{_RUN}XX", "capacity": 0},
        )
        check("capacity=0 → 422", r3.status_code == 422, r3.text)

        # ── GET list shows vehicle ───────────────────────────────────────────
        r4 = await client.get("/api/v1/vehicles/", headers=headers_a)
        check("GET list → 200", r4.status_code == 200, r4.text)
        items = r4.json().get("items", [])
        check("vehicle in list", any(v["id"] == vehicle_id for v in items))

        # ── GET /{id} ok ─────────────────────────────────────────────────────
        r5 = await client.get(f"/api/v1/vehicles/{vehicle_id}", headers=headers_a)
        check("GET /{id} → 200", r5.status_code == 200, r5.text)

        # ── PUT updates ──────────────────────────────────────────────────────
        r6 = await client.put(
            f"/api/v1/vehicles/{vehicle_id}",
            headers=headers_a,
            json={"capacity": 50, "make": "Tata"},
        )
        check("PUT update → 200", r6.status_code == 200, r6.text)
        check("capacity updated", r6.json().get("capacity") == 50)
        check("make updated", r6.json().get("make") == "Tata")

        # ── DELETE → 204, then GET → 404 ─────────────────────────────────────
        r7 = await client.delete(f"/api/v1/vehicles/{vehicle_id}", headers=headers_a)
        check("DELETE → 204", r7.status_code == 204, r7.text)

        r8 = await client.get(f"/api/v1/vehicles/{vehicle_id}", headers=headers_a)
        check("GET after delete → 404", r8.status_code == 404, r8.text)

        # ── Create a fresh vehicle for driver-assign test ────────────────────
        # Use a different plate since soft-deleted vehicle still holds the DB row.
        r_re = await client.post(
            "/api/v1/vehicles/",
            headers=headers_a,
            json={"plate_number": f"MH{_RUN}BB", "capacity": 35},
        )
        check("Re-create vehicle → 201", r_re.status_code == 201, r_re.text)
        vehicle_id_2 = r_re.json().get("id", "")

        # ── Cross-tenant: admin B cannot see school A vehicle ────────────────
        print("\n=== Cross-tenant isolation ===")
        email_b, pw_b = await seed_school_b(client, token_a)
        token_b = await login(client, email_b, pw_b)
        headers_b = {"Authorization": f"Bearer {token_b}"}

        r_ct = await client.get(f"/api/v1/vehicles/{vehicle_id_2}", headers=headers_b)
        check("cross-tenant GET vehicle → 404", r_ct.status_code == 404, r_ct.text)

        # ── Drivers ──────────────────────────────────────────────────────────
        print("\n=== Driver CRUD ===")
        r_d = await client.post(
            "/api/v1/drivers/",
            headers=headers_a,
            json={
                "email": f"driver{_RUN}@demo.school",
                "full_name": "Ram Kumar",
                "phone": "+919876543210",
            },
        )
        check("POST driver → 201", r_d.status_code == 201, r_d.text)
        driver_resp = r_d.json()
        driver_id = driver_resp.get("driver", {}).get("id", "")
        temp_pw = driver_resp.get("temp_password", "")
        check("temp_password in response", bool(temp_pw), f"temp_pw={temp_pw!r}")
        check("driver role=driver", driver_resp.get("driver", {}).get("role") == "driver")

        # ── GET drivers list ─────────────────────────────────────────────────
        r_dl = await client.get("/api/v1/drivers/", headers=headers_a)
        check("GET drivers list → 200", r_dl.status_code == 200, r_dl.text)
        driver_items = r_dl.json().get("items", [])
        check("driver in list", any(d["id"] == driver_id for d in driver_items))

        # ── GET /{id} ────────────────────────────────────────────────────────
        r_dg = await client.get(f"/api/v1/drivers/{driver_id}", headers=headers_a)
        check("GET driver/{id} → 200", r_dg.status_code == 200, r_dg.text)

        # ── POST /{id}/assign ────────────────────────────────────────────────
        r_assign = await client.post(
            f"/api/v1/drivers/{driver_id}/assign",
            headers=headers_a,
            json={"vehicle_id": vehicle_id_2},
        )
        check("POST driver assign → 200", r_assign.status_code == 200, r_assign.text)
        check("assign returns status", r_assign.json().get("status") == "assigned")

        # ── GET /{id}/schedule and /trips → stubs ───────────────────────────
        r_sched = await client.get(f"/api/v1/drivers/{driver_id}/schedule", headers=headers_a)
        check("GET schedule → 200 (stub)", r_sched.status_code == 200)

        r_trips = await client.get(f"/api/v1/drivers/{driver_id}/trips", headers=headers_a)
        check("GET trips → 200 (stub)", r_trips.status_code == 200)

        print("\n=== Summary ===")
        print("  Verification complete. Check PASS/FAIL above.")


if __name__ == "__main__":
    asyncio.run(main())
