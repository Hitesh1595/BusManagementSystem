"""
In-process verification for Chunk 3A schools endpoints.
Uses httpx ASGITransport so no live server is needed.

Run:
    cd backend && uv run python -m scripts.verify_schools
"""

import asyncio

import httpx

from app.auth.models import User
from app.core.security import encode_access_token, hash_password
from app.database import SessionLocal
from app.main import app
from app.schools.models import School


async def get_or_create_school(db, name: str, join_code: str) -> School:
    from sqlalchemy import select

    row = (
        await db.execute(select(School).where(School.name == name))
    ).scalar_one_or_none()
    if row:
        return row
    school = School(
        name=name,
        join_code=join_code,
        settings={"driver_phone_visible": False, "trip_autogen_enabled": True},
        is_active=True,
    )
    db.add(school)
    await db.commit()
    await db.refresh(school)
    return school


async def get_or_create_user(
    db, email: str, password: str, school_id, role: str
) -> User:
    from sqlalchemy import func, select

    row = (
        await db.execute(select(User).where(func.lower(User.email) == email.lower()))
    ).scalar_one_or_none()
    if row:
        return row
    user = User(
        school_id=school_id,
        email=email.lower(),
        password_hash=hash_password(password),
        full_name="Verify User",
        role=role,
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def main():
    async with SessionLocal() as db:
        # School A and its admin
        school_a = await get_or_create_school(db, "Verify School A", "VRFY000001")
        admin_a = await get_or_create_user(
            db, "verify_admin_a@test.school", "Test1234!", school_a.id, "school_admin"
        )

        # School B and its admin (for cross-tenant test)
        school_b = await get_or_create_school(db, "Verify School B", "VRFY000002")
        await get_or_create_user(
            db, "verify_admin_b@test.school", "Test1234!", school_b.id, "school_admin"
        )

    # Build tokens directly (no login roundtrip needed)
    token_a = encode_access_token(
        sub=str(admin_a.id), school_id=str(school_a.id), role="school_admin"
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        headers_a = {"Authorization": f"Bearer {token_a}"}

        print("\n=== 1. GET own school (admin A) ===")
        r = await client.get(f"/api/v1/schools/{school_a.id}", headers=headers_a)
        print(f"Status: {r.status_code}")
        body = r.json()
        print(f"name={body.get('name')}, settings={body.get('settings')}")

        print("\n=== 2. PUT /{id}/settings — merge driver_phone_visible=true ===")
        existing_keys_before = set(body.get("settings", {}).keys())
        print(f"Pre-existing settings keys: {existing_keys_before}")
        r = await client.put(
            f"/api/v1/schools/{school_a.id}/settings",
            headers=headers_a,
            json={"driver_phone_visible": True},
        )
        print(f"Status: {r.status_code}")
        merged = r.json()
        settings_after = merged.get("settings", {})
        print(f"Settings after merge: {settings_after}")
        assert settings_after.get("driver_phone_visible") is True, \
            "driver_phone_visible not set!"
        for k in existing_keys_before:
            assert k in settings_after, f"Pre-existing key '{k}' was lost after merge!"
        print(
            f"OK — driver_phone_visible=True AND all "
            f"{len(existing_keys_before)} pre-existing keys preserved"
        )

        print("\n=== 3. POST /{id}/regenerate-join-code ===")
        r_before = await client.get(
            f"/api/v1/schools/{school_a.id}", headers=headers_a
        )
        old_code = r_before.json()["join_code"]
        r = await client.post(
            f"/api/v1/schools/{school_a.id}/regenerate-join-code",
            headers=headers_a,
        )
        print(f"Status: {r.status_code}")
        new_code = r.json().get("join_code")
        print(f"Old code: {old_code}  New code: {new_code}")
        assert new_code != old_code, "join_code did NOT change!"
        print("OK — join code rotated")

        print("\n=== 4. Cross-tenant 404 (admin A reads school B) ===")
        r = await client.get(f"/api/v1/schools/{school_b.id}", headers=headers_a)
        print(f"Status: {r.status_code}")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"
        print(f"OK — got 404 as expected: {r.json()}")

    print("\n=== All verifications PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
