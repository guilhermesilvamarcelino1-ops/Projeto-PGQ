from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_admin
from app.db import get_db
from app.models import Conversation, Message, User
from app.schemas import QuestionLogOut

router = APIRouter(prefix="/admin/questions", tags=["admin"])


@router.get("", response_model=list[QuestionLogOut])
async def list_questions(
    only_fallback: bool = Query(False),
    limit: int = Query(50, le=200),
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Message, Conversation.id)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .join(User, Conversation.user_id == User.id)
        .where(User.company_id == admin.company_id)
        .order_by(Conversation.id, Message.created_at)
    )
    rows = result.all()

    # Pair each user question with the assistant reply that follows it in the same
    # conversation, so we can report had_fallback per question without a fragile SQL join.
    pairs: list[QuestionLogOut] = []
    pending_question: Message | None = None
    for message, _ in rows:
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
