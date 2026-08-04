import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

bearer_scheme = HTTPBearer()

# bcrypt limita a senha a 72 bytes; truncamos explicitamente para evitar ValueError
# em versões novas da lib (comportamento equivalente ao histórico do bcrypt).
_BCRYPT_MAX_BYTES = 72


def _encode(secret: str) -> bytes:
    return secret.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_secret(secret: str) -> str:
    return bcrypt.hashpw(_encode(secret), bcrypt.gensalt()).decode("utf-8")


def verify_secret(secret: str, secret_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_encode(secret), secret_hash.encode("utf-8"))
    except ValueError:
        return False


# Compatibilidade com o nome anterior das funções.
hash_password = hash_secret
verify_password = verify_secret


@dataclass
class Principal:
    """Identidade autenticada, extraída do token assinado. O company_id vem SEMPRE
    do token (nunca de um campo enviado pelo cliente), e é ele que fixa o contexto
    de RLS de toda a requisição."""

    user_id: uuid.UUID
    company_id: uuid.UUID
    is_admin: bool


def create_access_token(user_id: uuid.UUID, company_id: uuid.UUID, is_admin: bool) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {
        "sub": str(user_id),
        "company_id": str(company_id),
        "is_admin": is_admin,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode(credentials: HTTPAuthorizationCredentials) -> Principal:
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas")
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return Principal(
            user_id=uuid.UUID(payload["sub"]),
            company_id=uuid.UUID(payload["company_id"]),
            is_admin=bool(payload.get("is_admin", False)),
        )
    except (JWTError, KeyError, ValueError):
        raise unauthorized


async def get_principal(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> Principal:
    return _decode(credentials)


def create_document_link_token(document_id: uuid.UUID, company_id: uuid.UUID, family: str) -> str:
    """Token curto embutido no link do documento. O WhatsApp não envia cabeçalho de
    autenticação, então o próprio link carrega a autorização — assinada, com validade,
    e restrita a um documento de uma empresa.

    A família viaja no token porque o link é gerado no momento em que a pessoa tinha
    acesso àquele documento; ao abrir, é ela que o RLS usa para liberar só essa linha."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.document_link_expires_minutes)
    payload = {
        "doc": str(document_id),
        "company_id": str(company_id),
        "family": family,
        "scope": "document_link",
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def read_document_link_token(token: str) -> tuple[uuid.UUID, uuid.UUID, str]:
    """Devolve (document_id, company_id, family) do link, ou 401 se inválido/expirado."""
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Link inválido ou expirado")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("scope") != "document_link":
            raise unauthorized
        return uuid.UUID(payload["doc"]), uuid.UUID(payload["company_id"]), payload["family"]
    except (JWTError, KeyError, ValueError):
        raise unauthorized


async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> Principal:
    principal = _decode(credentials)
    if not principal.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito ao admin")
    return principal
