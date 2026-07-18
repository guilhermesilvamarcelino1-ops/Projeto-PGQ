import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def find_responsible_contact(
    db: AsyncSession, *, company_id: uuid.UUID, site_id: uuid.UUID | None
) -> str | None:
    """Finds the engineer responsible for a site to point the user to when the assistant can't answer."""
    stmt = select(User).where(User.company_id == company_id, User.role.ilike("%engenheiro%"))
    if site_id is not None:
        stmt = stmt.where(User.site_id == site_id)
    result = await db.execute(stmt.limit(1))
    engineer = result.scalar_one_or_none()
    if engineer is None:
        return None
    if engineer.phone_number:
        return f"{engineer.name}, {engineer.phone_number}"
    return engineer.name
