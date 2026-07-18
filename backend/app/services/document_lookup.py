import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document


async def find_administrative_document(
    db: AsyncSession, *, company_id: uuid.UUID, site_id: uuid.UUID | None, search_text: str
) -> Document | None:
    """Best-effort lookup of a whole-file administrative document (alvará, ART, habite-se, ...)
    by site + free-text match against title/category. Returns the most recent active match."""
    stmt = select(Document).where(
        Document.company_id == company_id,
        Document.kind == "administrativo",
        Document.status == "active",
    )
    if site_id is not None:
        stmt = stmt.where(Document.site_id == site_id)

    like_pattern = f"%{search_text}%"
    stmt = stmt.where(or_(Document.title.ilike(like_pattern), Document.category.ilike(like_pattern)))
    stmt = stmt.order_by(Document.uploaded_at.desc())

    result = await db.execute(stmt)
    return result.scalars().first()
