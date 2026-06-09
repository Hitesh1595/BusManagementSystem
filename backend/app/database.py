import contextvars
from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import DateTime, event, func, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    echo=False,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# ---------------------------------------------------------------------------
# Row-Level Security tenant scope (spec §6.8)
#
# `current_school_id` is a per-request/task scope (ContextVar). The app sets it
# from the JWT claim in `deps.get_current_claims`; super_admin and all system
# paths (schedulers, GPS flush, socket handlers) leave it at "" = bypass.
#
# The `after_begin` hook re-applies it as a transaction-local GUC at the start
# of EVERY transaction — so it survives the services' mid-request commits, and
# being transaction-local it auto-clears on commit/rollback, so a pooled
# connection never leaks one request's tenant scope into the next.
# ---------------------------------------------------------------------------

current_school_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_school_id", default=""
)


@event.listens_for(Session, "after_begin")
def _apply_rls_scope(session: Session, transaction, connection) -> None:  # noqa: ANN001
    connection.execute(
        text("SELECT set_config('app.current_school_id', :scope, true)"),
        {"scope": current_school_id.get()},
    )


class Base(DeclarativeBase):
    pass


class CreatedAtMixin:
    """Adds a `created_at` column (set on insert). For append-only / immutable rows."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )


class TimestampMixin(CreatedAtMixin):
    """Adds `created_at` + `updated_at` columns. For mutable entities.

    `updated_at` auto-bumps to now() on every UPDATE via SQLAlchemy's `onupdate`
    (client-side; applies to ORM and Core `update()` — no DDL change, no migration).
    """

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", onupdate=func.now(), nullable=False
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
