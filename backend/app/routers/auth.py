from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, verify_secret
from app.db import get_db
from app.models import User
from app.schemas import FieldLoginRequest, LoginRequest, TokenResponse
from app.services.identity import resolve_user_by_phone

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login do admin (qualidade/planejamento) por email + senha."""
    result = await db.execute(select(User).where(User.email == payload.email, User.is_admin.is_(True)))
    user = result.scalar_one_or_none()
    if user is None or not user.password_hash or not verify_secret(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou senha inválidos")
    return TokenResponse(access_token=create_access_token(user.id, user.company_id, is_admin=True))


@router.post("/field-login", response_model=TokenResponse)
async def field_login(payload: FieldLoginRequest, db: AsyncSession = Depends(get_db)):
    """Login do time de campo por telefone + PIN. No WhatsApp esta etapa é dispensada:
    o número verificado pela Meta já identifica o usuário e a empresa no servidor."""
    user = await resolve_user_by_phone(db, payload.phone_number)
    if user is None or not user.pin_hash or not verify_secret(payload.pin, user.pin_hash):
        raise HTTPException(status_code=401, detail="Telefone ou PIN inválidos")
    return TokenResponse(access_token=create_access_token(user.id, user.company_id, is_admin=user.is_admin))
