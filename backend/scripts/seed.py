"""
Bootstrap seed — idempotent.

Creates:
  1. First school with a random join_code.
  2. school_admin user for that school (email/pw from env or CLI args).
  3. super_admin user (email/pw from env or CLI args).

Run:
    cd backend && uv run python -m scripts.seed
    cd backend && uv run python -m scripts.seed \\
        --admin-email admin@demo.school \\
        --admin-password secret1234 \\
        --super-email super@yatratrack.in \\
        --super-password secret5678

Idempotency: checks lower(email) before creating; skips if already present.
School: creates if no school exists; skips otherwise (prints existing join_code).
"""

import argparse
import asyncio
import os
import secrets
import string

from sqlalchemy import func, select

from app.auth.models import User
from app.core.security import hash_password
from app.database import SessionLocal
from app.schools.models import School


def _random_join_code(length: int = 8) -> str:
    """Generate a random alphanumeric join code (uppercase)."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def seed(
    school_name: str,
    admin_email: str,
    admin_password: str,
    super_email: str,
    super_password: str,
) -> None:
    async with SessionLocal() as db:
        # ------------------------------------------------------------------
        # 1. School
        # ------------------------------------------------------------------
        existing_school = (await db.execute(select(School).limit(1))).scalar_one_or_none()
        if existing_school is None:
            join_code = _random_join_code()
            school = School(
                name=school_name,
                join_code=join_code,
                settings={
                    "driver_phone_visible": False,
                    "trip_autogen_enabled": True,
                    "bus_approaching_radius_m": 200,
                },
                is_active=True,
            )
            db.add(school)
            await db.commit()
            await db.refresh(school)
            print(f"[seed] Created school: {school.name!r}  join_code={school.join_code}")
        else:
            school = existing_school
            print(
                f"[seed] School already exists: {school.name!r}  join_code={school.join_code}"
            )

        # ------------------------------------------------------------------
        # 2. School admin
        # ------------------------------------------------------------------
        admin_exists = (
            await db.execute(
                select(User).where(func.lower(User.email) == admin_email.lower())
            )
        ).scalar_one_or_none()

        if admin_exists is None:
            admin = User(
                school_id=school.id,
                email=admin_email.lower(),
                password_hash=hash_password(admin_password),
                full_name="School Administrator",
                role="school_admin",
                is_active=True,
                email_verified=True,
            )
            db.add(admin)
            await db.commit()
            print(f"[seed] Created school_admin: {admin_email}")
        else:
            print(f"[seed] school_admin already exists: {admin_email}")

        # ------------------------------------------------------------------
        # 3. Super admin
        # ------------------------------------------------------------------
        super_exists = (
            await db.execute(
                select(User).where(func.lower(User.email) == super_email.lower())
            )
        ).scalar_one_or_none()

        if super_exists is None:
            superadmin = User(
                school_id=None,
                email=super_email.lower(),
                password_hash=hash_password(super_password),
                full_name="Super Administrator",
                role="super_admin",
                is_active=True,
                email_verified=True,
            )
            db.add(superadmin)
            await db.commit()
            print(f"[seed] Created super_admin: {super_email}")
        else:
            print(f"[seed] super_admin already exists: {super_email}")

        print(f"\n[seed] Done.  join_code={school.join_code}  admin={admin_email}")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bootstrap YatraTrack seed data")
    p.add_argument(
        "--school-name",
        default=os.getenv("SEED_SCHOOL_NAME", "Demo School"),
    )
    p.add_argument(
        "--admin-email",
        default=os.getenv("SEED_ADMIN_EMAIL", "admin@demo.school"),
    )
    p.add_argument(
        "--admin-password",
        default=os.getenv("SEED_ADMIN_PASSWORD", "Admin1234!"),
    )
    p.add_argument(
        "--super-email",
        default=os.getenv("SEED_SUPER_EMAIL", "super@yatratrack.in"),
    )
    p.add_argument(
        "--super-password",
        default=os.getenv("SEED_SUPER_PASSWORD", "Super1234!"),
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(
        seed(
            school_name=args.school_name,
            admin_email=args.admin_email,
            admin_password=args.admin_password,
            super_email=args.super_email,
            super_password=args.super_password,
        )
    )
