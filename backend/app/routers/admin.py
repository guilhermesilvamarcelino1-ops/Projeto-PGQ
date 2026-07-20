from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.auth import Principal, get_current_admin
from app.db import tenant_session
from app.models import Conversation, Message
from app.schemas import QuestionLogOut

router = APIRouter(prefix="/admin/questions", tags=["admin"])


@router.get("", response_model=list[QuestionLogOut])
async def list_questions(
    only_fallback: bool = Query(False),
    limit: int = Query(50, le=200),
    admin: Principal = Depends(get_current_admin),
):
    async with tenant_session(admin.company_id) as db:
        result = await db.execute(
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .order_by(Conversation.id, Message.created_at)
        )
        messages = result.scalars().all()

    # Emparelha cada pergunta do usuário com a resposta do assistente que veio na
    # sequência, para reportar had_fallback por pergunta sem depender de join frágil.
    pairs: list[QuestionLogOut] = []
    pending_question: Message | None = None
    for message in messages:
        if message.role == "user":
            pending_question = message
        elif message.role == "assistant" and pending_question is not None:
            pairs.append(
                QuestionLogOut(
                    id=pending_question.id,
                    content=pending_question.content,
                    had_fallback=message.had_fallback,
                    created_at=pending_question.created_at,
                )
            )
            pending_question = None

    if only_fallback:
        pairs = [p for p in pairs if p.had_fallback]
    pairs.sort(key=lambda p: p.created_at, reverse=True)
    return pairs[:limit]
