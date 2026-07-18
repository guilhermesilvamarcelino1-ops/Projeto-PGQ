import uuid
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Document, DocumentChunk
from app.services.chunking import extract_chunks
from app.services.embeddings import embed_documents


async def _next_version(db: AsyncSession, company_id: uuid.UUID, title: str) -> int:
    result = await db.execute(
        select(Document)
        .where(Document.company_id == company_id, Document.title == title, Document.status == "active")
    )
    existing = result.scalars().all()
    if not existing:
        return 1
    await db.execute(
        update(Document)
        .where(Document.id.in_([d.id for d in existing]))
        .values(status="archived")
    )
    return max(d.version for d in existing) + 1


def _store_file(company_id: uuid.UUID, filename: str, file_bytes: bytes) -> str:
    company_dir = Path(settings.storage_dir) / str(company_id)
    company_dir.mkdir(parents=True, exist_ok=True)
    unique_name = f"{uuid.uuid4()}_{filename}"
    dest = company_dir / unique_name
    dest.write_bytes(file_bytes)
    return str(dest)


async def ingest_document(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    title: str,
    category: str,
    kind: str,
    site_id: uuid.UUID | None,
    uploaded_by: uuid.UUID | None,
    filename: str,
    content_type: str,
    file_bytes: bytes | None = None,
    plain_text: str | None = None,
) -> tuple[Document, int]:
    version = await _next_version(db, company_id, title)
    stored_path = _store_file(company_id, filename, file_bytes if file_bytes is not None else plain_text.encode())

    document = Document(
        company_id=company_id,
        title=title,
        category=category,
        kind=kind,
        site_id=site_id,
        file_path=stored_path,
        version=version,
        uploaded_by=uploaded_by,
        status="active",
    )
    db.add(document)
    await db.flush()

    chunks_created = 0
    if kind == "procedimento":
        raw_chunks = extract_chunks(file_bytes, plain_text, content_type)
        embeddings = embed_documents([c.content for c in raw_chunks])
        for raw_chunk, embedding in zip(raw_chunks, embeddings):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    content=raw_chunk.content,
                    embedding=embedding,
                    page_ref=raw_chunk.page_ref,
                    section_ref=raw_chunk.section_ref,
                )
            )
        chunks_created = len(raw_chunks)

    await db.commit()
    await db.refresh(document)
    return document, chunks_created
