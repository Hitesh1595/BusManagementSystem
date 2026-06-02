from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


async def paginate(
    query,
    db: AsyncSession,
    limit: int = _DEFAULT_LIMIT,
    offset: int = 0,
) -> dict:
    """Run a count query then the sliced select. Returns a dict suitable for Page."""
    limit = min(limit, _MAX_LIMIT)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    rows = (await db.execute(query.offset(offset).limit(limit))).scalars().all()
    return {"items": rows, "total": total, "limit": limit, "offset": offset}
