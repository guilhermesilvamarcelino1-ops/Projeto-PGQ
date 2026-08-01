import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.auth import Principal, get_current_admin, read_document_link_token
from app.db import tenant_session
from app.models import Document
from app.schemas import DocumentOut, DocumentUploadResponse
from app.services.ingestion import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])

# Procedimentos são exigidos em PDF: é o formato que preserva a paginação, o que
# permite abrir o documento direto na página citada (e, adiante, destacar o trecho).
PDF_CONTENT_TYPES = {"application/pdf"}


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

    if kind == "procedimento" and file is not None and file.content_type not in PDF_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Procedimentos devem ser enviados em PDF. Se o arquivo estiver em Word, "
                "salve como PDF e envie novamente."
            ),
        )

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


@router.get("/{document_id}/file")
async def get_document_file(document_id: uuid.UUID, t: str = Query(..., description="Token do link")):
    """Serve o arquivo do procedimento pelo link enviado ao usuário. A autorização vem
    do token assinado na URL (o WhatsApp não envia cabeçalho), restrito a este documento."""
    token_doc_id, company_id = read_document_link_token(t)
    if token_doc_id != document_id:
        raise HTTPException(status_code=403, detail="Link não corresponde ao documento")

    async with tenant_session(company_id) as db:
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if document is None:
            raise HTTPException(status_code=404, detail="Documento não encontrado")
        file_path, title = document.file_path, document.title

    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no armazenamento")
    # inline: o navegador/WhatsApp abre o PDF na página do #page=N em vez de baixar.
    return FileResponse(
        path,
        media_type="application/pdf" if path.suffix.lower() == ".pdf" else "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )


@router.post("/{document_id}/archive", response_model=DocumentOut)
async def archive_document(document_id: uuid.UUID, admin: Principal = Depends(get_current_admin)):
    async with tenant_session(admin.company_id) as db:
        result = await db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if document is None:
            raise HTTPException(status_code=404, detail="Documento não encontrado")
        document.status = "archived"
    return document
