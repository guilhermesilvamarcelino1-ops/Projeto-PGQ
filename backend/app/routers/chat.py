import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import Conversation, Message, User
from app.schemas import ChatResponse, SourceRef
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
    user_id: uuid.UUID = Form(...),
    conversation_id: uuid.UUID | None = Form(None),
    channel: Literal["web", "whatsapp"] = Form("web"),
    media_type: Literal["text", "audio", "image"] = Form("text"),
    text: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if media_type in ("audio", "image") and file is None:
        raise HTTPException(status_code=400, detail=f"Envie um arquivo para media_type={media_type}")
    if media_type == "text" and not text:
        raise HTTPException(status_code=400, detail="Envie o texto da pergunta")

    if conversation_id is not None:
        conv_result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        conversation = conv_result.scalar_one_or_none()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversa não encontrada")
    else:
        conversation = Conversation(user_id=user.id, site_id=user.site_id, channel=channel)
        db.add(conversation)
        await db.flush()

    media_url: str | None = None
    transcript: str | None = None
    query_text = text or ""

    if media_type == "audio":
        audio_bytes = await file.read()
        media_url = _store_media(user.company_id, file.filename, audio_bytes)
        transcript = await transcribe_audio(audio_bytes, file.filename)
        query_text = transcript
    elif media_type == "image":
        image_bytes = await file.read()
        media_url = _store_media(user.company_id, file.filename, image_bytes)
        # MVP: a foto só fica anexada como contexto/registro — sem análise visual nesta fase.
        query_text = text or "(foto anexada, sem pergunta em texto)"

    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=query_text,
        media_type=media_type,
        media_url=media_url,
        transcript=transcript,
    )
    db.add(user_message)
    await db.flush()

    contact = await find_responsible_contact(db, company_id=user.company_id, site_id=user.site_id)
    result = await answer_question(
        db, company_id=user.company_id, site_id=user.site_id, query=query_text, contact=contact
    )

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result.answer,
        chunks_used=result.chunks_used or None,
        had_fallback=result.had_fallback,
    )
    db.add(assistant_message)
    await db.commit()

    return ChatResponse(
        conversation_id=conversation.id,
        answer=result.answer,
        had_fallback=result.had_fallback,
        sources=[SourceRef(**s) for s in result.sources],
        document_file_path=result.document_file_path,
    )
