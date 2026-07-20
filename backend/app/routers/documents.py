import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select

from app.auth import Principal, get_current_admin
from app.db import tenant_session
from app.models import Document
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
    admin: Principal = Depends(get_current_admin),
):
    if kind not in ("procedimento", "administrativo"):
        raise HTTPException(status_code=400, detail="kind deve ser 'procedimento' ou 'administrativo'")
    if file is None and not plain_text:
        raise HTTPException(status_code=400, detail="Envie um arquivo ou texto colado")

    file_bytes = await file.read() if file is not None else None
    filename = file.filename if file is not None else f"{title}.txt"
    content_type = file.content_type if file is not None else "text/plain"

    async with tenant_session(admin.company_id) as db:
        document, chunks_created = await ingest_document(
            db,
            company_id=admin.company_id,
            title=title,
            category=category,
            kind=kind,
            site_id=site_id,
            uploaded_by=admin.user_id,
            filename=filename,
            content_type=content_type,
            file_bytes=file_bytes,
            plain_text=plain_text,
        )
        response = DocumentUploadResponse(
            document=DocumentOut.model_validate(document), chunks_created=chunks_created
        )
    return response


@router.get("", response_model=list[DocumentOut])
async def list_documents(admin: Principal = Depends(get_current_admin)):
    async with tenant_session(admin.company_id) as db:
        result = await db.execute(select(Document).order_by(Document.uploaded_at.desc()))
        return result.scalars().all()


@router.post("/{document_id}/archive", response_model=DocumentOut)
async def archive_document(document_id: uuid.UUID, admin: Principal = Depends(get_current_admin)):
    async with tenant_session(admin.company_id) as db:
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if document is None:
            raise HTTPException(status_code=404, detail="Documento não encontrado")
        document.status = "archived"
    return document
