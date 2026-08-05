"""Conexão da empresa com o drive dela.

O admin clica em "conectar", autoriza na tela da Microsoft e pronto — nunca pedimos
a senha da conta. O que fica guardado é a autorização revogável, não a credencial
pessoal de ninguém.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, create_document_link_token, get_current_admin, read_document_link_token
from app.db import tenant_session
from app.models import DriveConnection
from app.services import onedrive
from app.services.access import authorized_session

router = APIRouter(prefix="/drive", tags=["drive"])

# O retorno da Microsoft fica fora do prefixo porque o endereço é cadastrado no
# portal da Microsoft e precisa bater exatamente com o que foi registrado lá.
callback_router = APIRouter(tags=["drive"])


@router.get("/connect")
async def connect(admin: Principal = Depends(get_current_admin)):
    """Devolve a URL da tela de autorização da Microsoft.

    O `state` é um token assinado nosso: garante que o retorno pertence a esta empresa
    e não pode ser forjado por quem apenas descobriu o endereço de callback.
    """
    state = create_document_link_token(admin.company_id, admin.company_id, "drive_connect")
    return {"authorize_url": onedrive.build_authorize_url(state)}


@callback_router.get("/auth/microsoft/callback", response_class=HTMLResponse)
async def callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
    error_description: str | None = Query(None),
):
    """Retorno da Microsoft depois que a pessoa autoriza."""
    if error_description:
        raise HTTPException(status_code=400, detail=f"Autorização recusada: {error_description}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Retorno incompleto da Microsoft")

    _doc, company_id, escopo = read_document_link_token(state)
    if escopo != "drive_connect":
        raise HTTPException(status_code=400, detail="Retorno não corresponde a uma conexão de drive")

    tokens = await onedrive.exchange_code(code)
    conta = await onedrive.get_account_info(tokens.access_token)

    async with tenant_session(company_id) as db:
        existente = (
            await db.execute(
                select(DriveConnection).where(
                    DriveConnection.company_id == company_id,
                    DriveConnection.provider == "onedrive",
                    DriveConnection.active.is_(True),
                )
            )
        ).scalar_one_or_none()

        if existente is None:
            db.add(
                DriveConnection(
                    company_id=company_id,
                    provider="onedrive",
                    account_email=conta["email"],
                    refresh_token=tokens.refresh_token,
                    access_token=tokens.access_token,
                    access_token_expires_at=tokens.expires_at,
                )
            )
        else:
            # Reconectar substitui a autorização anterior em vez de acumular conexões.
            existente.refresh_token = tokens.refresh_token
            existente.access_token = tokens.access_token
            existente.access_token_expires_at = tokens.expires_at
            existente.account_email = conta["email"]
            existente.last_error = None

    return HTMLResponse(
        "<h2>Drive conectado</h2>"
        f"<p>Conta: <b>{conta['email']}</b></p>"
        "<p>Pode fechar esta janela e voltar ao painel.</p>"
    )


@router.get("/status")
async def status(admin: Principal = Depends(get_current_admin)):
    """Estado da conexão para o painel. O refresh token nunca é devolvido."""
    async with authorized_session(admin) as (db, _families):
        conexao = (
            await db.execute(
                select(DriveConnection).where(
                    DriveConnection.company_id == admin.company_id, DriveConnection.active.is_(True)
                )
            )
        ).scalar_one_or_none()

    if conexao is None:
        return {"conectado": False}
    return {
        "conectado": True,
        "provedor": conexao.provider,
        "conta": conexao.account_email,
        "pasta_raiz": conexao.root_path,
        "conectado_em": conexao.connected_at,
        "ultimo_erro": conexao.last_error,
    }


async def get_valid_access_token(db: AsyncSession, company_id: uuid.UUID) -> tuple[str, DriveConnection]:
    """Token válido para falar com o drive, renovando quando vencido.

    A renovação acontece aqui, e não em cada chamada, para que o arquivamento não
    falhe por token expirado no meio do expediente.
    """
    conexao = (
        await db.execute(
            select(DriveConnection).where(
                DriveConnection.company_id == company_id, DriveConnection.active.is_(True)
            )
        )
    ).scalar_one_or_none()
    if conexao is None:
        raise HTTPException(status_code=409, detail="Nenhum drive conectado para esta empresa")

    agora = datetime.now(timezone.utc)
    vencido = conexao.access_token_expires_at is None or conexao.access_token_expires_at <= agora
    if not vencido and conexao.access_token:
        return conexao.access_token, conexao

    tokens = await onedrive.refresh_access_token(conexao.refresh_token)
    conexao.access_token = tokens.access_token
    conexao.refresh_token = tokens.refresh_token
    conexao.access_token_expires_at = tokens.expires_at
    return tokens.access_token, conexao


@router.get("/authorize-redirect")
async def authorize_redirect(state: str = Query(...)):
    """Atalho para abrir a tela da Microsoft direto do navegador."""
    return RedirectResponse(onedrive.build_authorize_url(state))
