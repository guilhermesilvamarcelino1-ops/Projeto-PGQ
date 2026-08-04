import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select

from app.auth import Principal, get_principal
from app.config import settings
from app.models import Conversation, Message, User
from app.schemas import ChatResponse, SourceRef
from app.services.access import authorized_session
from app.services.contacts import find_responsible_contact
from app.services.rag import answer_question
from app.services.transcription import transcribe_audio

router = APIRouter(prefix="/chat", tags=["chat"])


def _store_media(company_id: uuid.UUID, filename: str, data: bytes) -> str:
    media_dir = Path(settings.storage_dir) / str(company_id) / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    dest = media_dir / f"{uuid.uuid4()}_{filename}"
    dest.write_bytes(data)
    return str(dest)


@router.post("/message", response_model=ChatResponse)
async def send_message(
    conversation_id: uuid.UUID | None = Form(None),
    media_type: Literal["text", "audio", "image"] = Form("text"),
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    principal: Principal = Depends(get_principal),
):
    # A empresa e o usuário vêm do token assinado — nunca de um campo do cliente.
    company_id = principal.company_id

    if media_type in ("audio", "image") and file is None:
        raise HTTPException(status_code=400, detail=f"Envie um arquivo para media_type={media_type}")
    if media_type == "text" and not text:
        raise HTTPException(status_code=400, detail="Envie o texto da pergunta")

    media_url: str | None = None
    transcript: str | None = None
    query_text = text or ""

    if media_type == "audio":
        audio_bytes = await file.read()
        media_url = _store_media(company_id, file.filename, audio_bytes)
        transcript = await transcribe_audio(audio_bytes, file.filename)
        query_text = transcript
    elif media_type == "image":
        image_bytes = await file.read()
        media_url = _store_media(company_id, file.filename, image_bytes)
        # MVP: a foto só fica anexada como registro — sem análise visual nesta fase.
        query_text = text or "(foto anexada, sem pergunta em texto)"

    # Todo o trabalho de dados roda com empresa E famílias permitidas fixadas: a busca
    # nunca alcança documento de família que esta pessoa não pode ver (RH, cliente).
    async with authorized_session(principal) as (db, _families):
        user = (await db.execute(select(User).where(User.id == principal.user_id))).scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        if conversation_id is not None:
            conversation = (
                await db.execute(select(Conversation).where(Conversation.id == conversation_id))
            ).scalar_one_or_none()
            if conversation is None:
                raise HTTPException(status_code=404, detail="Conversa não encontrada")
        else:
            conversation = Conversation(
                company_id=company_id, user_id=user.id, site_id=user.site_id, channel="web"
            )
            db.add(conversation)
            await db.flush()

        db.add(
            Message(
                conversation_id=conversation.id,
                company_id=company_id,
                role="user",
                content=query_text,
                media_type=media_type,
                media_url=media_url,
                transcript=transcript,
            )
        )
        await db.flush()

        contact = await find_responsible_contact(db, company_id=company_id, site_id=user.site_id)
        first_name = user.name.split()[0] if user.name else None
        result = await answer_question(
            db,
            company_id=company_id,
            site_id=user.site_id,
            query=query_text,
            contact=contact,
            user_first_name=first_name,
        )

        db.add(
            Message(
                conversation_id=conversation.id,
                company_id=company_id,
                role="assistant",
                content=result.answer,
                chunks_used=result.chunks_used or None,
                had_fallback=result.had_fallback,
            )
        )
        conv_id = conversation.id

    return ChatResponse(
        conversation_id=conv_id,
        answer=result.answer,
        had_fallback=result.had_fallback,
        sources=[
            SourceRef(
                document_title=s.document_title,
                document_id=s.document_id,
                section_ref=s.section_ref,
                page_ref=s.page_ref,
                quote=s.quote,
                url=s.url,
            )
            for s in result.sources
        ],
        document_file_path=result.document_file_path,
    )
