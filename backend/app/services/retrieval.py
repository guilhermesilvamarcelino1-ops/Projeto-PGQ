import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Document, DocumentChunk
from app.services.embeddings import embed_query


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    content: str
    document_title: str
    page_ref: int | None
    section_ref: str | None


async def retrieve_chunks(
    db: AsyncSession, *, company_id: uuid.UUID, query: str, category: str | None = None
) -> list[RetrievedChunk]:
    query_embedding = embed_query(query)

    stmt = (
        select(DocumentChunk, Document.title)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(
            Document.company_id == company_id,
            Document.kind == "procedimento",
            Document.status == "active",
        )
    )
    if category:
        stmt = stmt.where(Document.category == category)

    stmt = stmt.order_by(DocumentChunk.embedding.cosine_distance(query_embedding)).limit(settings.retrieval_top_k)

    result = await db.execute(stmt)
    rows = result.all()
    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            content=chunk.content,
            document_title=title,
            page_ref=chunk.page_ref,
            section_ref=chunk.section_ref,
        )
        for chunk, title in rows
    ]
