import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_admin
from app.db import get_db
from app.models import Document, User
from app.schemas import DocumentOut, DocumentUploadResponse
from app.services.ingestion import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    title: str = Form(...),
    category: str = Form(...),
    kind: str = Form(...),
    site_id: uuid.UUID | None = Form(None),
    plain_text: str | None = Form(None),
    file: UploadFile | None = File(None),
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    if kind not in ("procedimento", "administrativo"):
        raise HTTPException(status_code=400, detail="kind deve ser 'procedimento' ou 'administrativo'")
    if file is None and not plain_text:
        raise HTTPException(status_code=400, detail="Envie um arquivo ou texto colado")

    file_bytes = await file.read() if file is not None else None
    filename = file.filename if file is not None else f"{title}.txt"
    content_type = file.content_type if file is not None else "text/plain"

    document, chunks_created = await ingest_document(
        db,
        company_id=admin.company_id,
        title=title,
        category=category,
        kind=kind,
        site_id=site_id,
        uploaded_by=admin.id,
        filename=filename,
        content_type=content_type,
        file_bytes=file_bytes,
        plain_text=plain_text,
    )
    return DocumentUploadResponse(document=DocumentOut.model_validate(document), chunks_created=chunks_created)


@router.get("", response_model=list[DocumentOut])
async def list_documents(admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Document).where(Document.company_id == admin.company_id).order_by(Document.uploaded_at.desc())
    )
    return result.scalars().all()


@router.post("/{document_id}/archive", response_model=DocumentOut)
async def archive_document(
    document_id: uuid.UUID, admin: User = Depends(get_current_admin), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.company_id == admin.company_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    document.status = "archived"
    await db.commit()
    await db.refresh(document)
    return document
