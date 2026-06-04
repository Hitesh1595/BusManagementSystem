"""
In-process verification for Chunk 3C — Routes + Stops.
Uses httpx ASGITransport (no uvicorn needed).

Tests:
  1. POST route → 201 (version=1)
  2. POST 3 stops → 201 each; GET /{id} shows 3 ordered stops + non-null route_path
  3. PUT /{id}/stops/reorder reversing order → 200; GET shows new stop_order 0..2
  4. PUT /{id} with current version → 200 (version increments)
  5. PUT /{id} with stale version → 409
  6. Cross-tenant: admin B GET route of school A → 404
"""

import asyncio
import secrets
import string
import time

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.auth.models import User
from app.core.security import hash_password
from app.database import SessionLocal
from app.main import app
from app.schools.models import School

_RUN = str(int(time.time()))[-5:]
BASE = "http://test"


def check(label: str, condition: bool, detail: str = "") -> None:
    status_str = "PASS" if condition else "FAIL"
    msg = f"  [{status_str}] {label}"
    if detail:
        msg += f"  ← {detail}"
    print(msg)
    if not condition:
        print(f"         detail: {detail}")


async def login(client: AsyncClient, email: str, password: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


async def seed_school_b() -> tuple[str, str]:
    """Create school B + admin B for cross-tenant test."""
    email_b = f"admin_b_{_RUN}@schoolb.example.com"
    pw_b = "SecretB1234!"

    async with SessionLocal() as db:
        # school B
        school_name = f"School B {_RUN}"
        result = await db.execute(select(School).where(School.name == school_name))
        existing = result.scalar_one_or_none()
        if existing is None:
            alphabet = string.ascii_uppercase + string.digits
            code = "".join(secrets.choice(alphabet) for _ in range(8))
            school_b = School(name=school_name, join_code=code, is_active=True)
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
        # ── Auth ──────────────────────────────────────────────────────────────
        print("\n=== Auth ===")
        token_a = await login(client, "admin@demo.school", "Admin1234!")
        print("  [PASS] school_admin login ok")
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # ── POST route → 201 ─────────────────────────────────────────────────
        print("\n=== Route CRUD ===")
        r = await client.post(
            "/api/v1/routes/",
            headers=headers_a,
            json={"name": f"Route A {_RUN}", "schedule_type": "both"},
        )
        check("POST route → 201", r.status_code == 201, r.text)
        route = r.json()
        route_id = route.get("id", "")
        check("version=1", route.get("version") == 1, str(route.get("version")))
        check("stops=[]", route.get("stops") == [], str(route.get("stops")))
        check("has_route_path=False (no stops)", route.get("has_route_path") is False)

        # ── POST 3 stops ──────────────────────────────────────────────────────
        print("\n=== Stops ===")
        stops_input = [
            {"name": "Stop Alpha", "location": {"lat": 28.6139, "lng": 77.2090}},
            {"name": "Stop Beta", "location": {"lat": 28.6200, "lng": 77.2100}},
            {"name": "Stop Gamma", "location": {"lat": 28.6300, "lng": 77.2200}},
        ]
        stop_ids = []
        for i, stop_data in enumerate(stops_input):
            r_s = await client.post(
                f"/api/v1/routes/{route_id}/stops",
                headers=headers_a,
                json=stop_data,
            )
            check(f"POST stop {i+1} → 201", r_s.status_code == 201, r_s.text)
            stop_ids.append(r_s.json().get("id"))

        # ── GET /{id} shows 3 stops + route_path ─────────────────────────────
        r_get = await client.get(f"/api/v1/routes/{route_id}", headers=headers_a)
        check("GET route → 200", r_get.status_code == 200, r_get.text)
        route_data = r_get.json()
        stops_out = route_data.get("stops", [])
        check("3 stops returned", len(stops_out) == 3, f"got {len(stops_out)}")
        check(
            "stops ordered 0,1,2",
            [s["stop_order"] for s in stops_out] == [0, 1, 2],
            str([s["stop_order"] for s in stops_out]),
        )
        check("has_route_path=True (≥2 stops)", route_data.get("has_route_path") is True)
        check(
            "stop location has lat/lng",
            "lat" in stops_out[0]["location"] and "lng" in stops_out[0]["location"],
        )

        # ── PUT /{id}/stops/reorder (reverse order) ───────────────────────────
        print("\n=== Reorder ===")
        reversed_ids = list(reversed(stop_ids))
        r_reorder = await client.put(
            f"/api/v1/routes/{route_id}/stops/reorder",
            headers=headers_a,
            json={"ordered_stop_ids": reversed_ids},
        )
        check("PUT reorder → 200", r_reorder.status_code == 200, r_reorder.text)
        reordered = r_reorder.json()
        check(
            "3 stops in response",
            len(reordered) == 3,
            f"got {len(reordered)}",
        )
        new_orders = [s["stop_order"] for s in reordered]
        check("new orders = [0,1,2]", new_orders == [0, 1, 2], str(new_orders))
        # First stop should now be Gamma (was last)
        check(
            "first stop after reorder = Gamma",
            reordered[0]["name"] == "Stop Gamma",
            reordered[0]["name"],
        )

        # Verify GET after reorder shows rebuilt route_path
        r_after = await client.get(f"/api/v1/routes/{route_id}", headers=headers_a)
        check("GET after reorder → 200", r_after.status_code == 200)
        check("has_route_path still True", r_after.json().get("has_route_path") is True)

        # ── Optimistic lock ───────────────────────────────────────────────────
        print("\n=== Optimistic Lock ===")
        # Fetch current version
        r_curr = await client.get(f"/api/v1/routes/{route_id}", headers=headers_a)
        current_version = r_curr.json()["version"]

        # PUT with CURRENT version → 200, version increments
        r_upd = await client.put(
            f"/api/v1/routes/{route_id}",
            headers=headers_a,
            json={"name": f"Route A Updated {_RUN}", "version": current_version},
        )
        check("PUT current version → 200", r_upd.status_code == 200, r_upd.text)
        new_version = r_upd.json().get("version")
        check(
            f"version incremented ({current_version} → {new_version})",
            new_version == current_version + 1,
            f"{new_version}",
        )

        # PUT with OLD (stale) version → 409
        r_stale = await client.put(
            f"/api/v1/routes/{route_id}",
            headers=headers_a,
            json={"name": "Stale Update", "version": current_version},  # already used
        )
        check("PUT stale version → 409", r_stale.status_code == 409, r_stale.text)

        # ── Cross-tenant isolation ────────────────────────────────────────────
        print("\n=== Cross-tenant isolation ===")
        email_b, pw_b = await seed_school_b()
        token_b = await login(client, email_b, pw_b)
        headers_b = {"Authorization": f"Bearer {token_b}"}

        r_ct = await client.get(f"/api/v1/routes/{route_id}", headers=headers_b)
        check("admin B GET route of school A → 404", r_ct.status_code == 404, r_ct.text)

        # ── GET students (stub) ───────────────────────────────────────────────
        print("\n=== Students stub ===")
        r_students = await client.get(f"/api/v1/routes/{route_id}/students", headers=headers_a)
        check("GET students → 200 (stub)", r_students.status_code == 200, r_students.text)
        check(
            "students returns empty list",
            r_students.json().get("items") == [],
        )

        print("\n=== Summary ===")
        print("  Verification complete. Check PASS/FAIL above.")


if __name__ == "__main__":
    asyncio.run(main())
