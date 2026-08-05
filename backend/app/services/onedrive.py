"""Conector OneDrive/SharePoint via Microsoft Graph.

O arquivo é gravado no drive do próprio cliente, com a estrutura de pastas do RQ 15
dele — é lá que a documentação já é revisada, e é o que evita obrigar a empresa a
manter o acervo em dois lugares.

O caminho é criado por inteiro quando não existe: um documento de tipo novo, ou de
obra nova, não pode falhar por falta de pasta nem cair num lugar improvisado.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx

from app.config import settings

GRAPH = "https://graph.microsoft.com/v1.0"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
AUTHORIZE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"

# offline_access é o que devolve o refresh token — sem ele o acesso morre em uma hora
# e o arquivamento pararia de funcionar sozinho no dia seguinte.
SCOPES = "offline_access User.Read Files.ReadWrite.All"

# Acima disso, o Graph exige upload em sessão/pedaços em vez de uma chamada só.
SIMPLE_UPLOAD_LIMIT = 4 * 1024 * 1024


class DriveError(RuntimeError):
    """Falha ao falar com o drive do cliente. A mensagem é mostrada ao admin."""


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str
    expires_at: datetime


@dataclass
class ArquivoSalvo:
    item_id: str
    nome: str
    caminho: str
    web_url: str
    tamanho: int


def build_authorize_url(state: str) -> str:
    """URL para a pessoa autorizar o acesso. Quem clica é ela — nunca pedimos senha."""
    if not settings.microsoft_client_id:
        raise DriveError("MICROSOFT_CLIENT_ID não configurado")
    params = {
        "client_id": settings.microsoft_client_id,
        "response_type": "code",
        "redirect_uri": settings.microsoft_redirect_uri,
        "response_mode": "query",
        "scope": SCOPES,
        "state": state,
    }
    query = "&".join(f"{k}={quote(str(v), safe='')}" for k, v in params.items())
    return f"{AUTHORIZE_URL}?{query}"


async def _post_token(data: dict) -> TokenSet:
    if not settings.microsoft_client_id or not settings.microsoft_client_secret:
        raise DriveError("Credenciais da Microsoft não configuradas")
    payload = {
        "client_id": settings.microsoft_client_id,
        "client_secret": settings.microsoft_client_secret,
        "redirect_uri": settings.microsoft_redirect_uri,
        **data,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(TOKEN_URL, data=payload)
    if response.status_code >= 400:
        raise DriveError(f"Microsoft recusou a autorização: {response.text[:300]}")

    body = response.json()
    refresh = body.get("refresh_token")
    if not refresh:
        raise DriveError("A Microsoft não devolveu refresh token — verifique o escopo offline_access")
    return TokenSet(
        access_token=body["access_token"],
        refresh_token=refresh,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(body.get("expires_in", 3600))),
    )


async def exchange_code(code: str) -> TokenSet:
    """Troca o código devolvido pela tela de autorização por um par de tokens."""
    return await _post_token({"grant_type": "authorization_code", "code": code})


async def refresh_access_token(refresh_token: str) -> TokenSet:
    """Renova o acesso. Rodado automaticamente antes de cada operação vencida."""
    return await _post_token({"grant_type": "refresh_token", "refresh_token": refresh_token})


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


async def get_account_info(access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{GRAPH}/me", headers=_headers(access_token))
    if response.status_code >= 400:
        raise DriveError(f"Não consegui identificar a conta: {response.text[:200]}")
    dados = response.json()
    return {
        "email": dados.get("mail") or dados.get("userPrincipalName"),
        "nome": dados.get("displayName"),
    }


def _encode_path(caminho: str) -> str:
    """Caminho de pasta na sintaxe do Graph, preservando espaços e acentos."""
    partes = [quote(p, safe="") for p in caminho.strip("/").split("/") if p]
    return "/".join(partes)


async def ensure_folder(access_token: str, caminho: str) -> str:
    """Garante a árvore de pastas inteira, criando o que faltar, e devolve o id da última.

    Criar pasta a pasta (em vez de exigir que já exista) é o que permite arquivar um
    documento de obra nova ou de tipo ainda não usado sem intervenção manual.
    """
    partes = [p for p in caminho.strip("/").split("/") if p]
    if not partes:
        return "root"

    parent = "root"
    async with httpx.AsyncClient(timeout=60) as client:
        for nome in partes:
            criar = await client.post(
                f"{GRAPH}/me/drive/items/{parent}/children",
                headers={**_headers(access_token), "Content-Type": "application/json"},
                json={
                    "name": nome,
                    "folder": {},
                    # Já existe? Devolve a pasta existente em vez de criar duplicata.
                    "@microsoft.graph.conflictBehavior": "fail",
                },
            )
            if criar.status_code < 300:
                parent = criar.json()["id"]
                continue

            # nameAlreadyExists é o caminho normal a partir da segunda vez.
            buscar = await client.get(
                f"{GRAPH}/me/drive/items/{parent}:/{_encode_path(nome)}",
                headers=_headers(access_token),
            )
            if buscar.status_code >= 400:
                raise DriveError(f"Não consegui criar/abrir a pasta '{nome}': {criar.text[:200]}")
            parent = buscar.json()["id"]

    return parent


async def upload_file(
    access_token: str, *, folder_id: str, filename: str, content: bytes, content_type: str
) -> ArquivoSalvo:
    """Grava o arquivo na pasta indicada. Nome repetido ganha sufixo em vez de
    sobrescrever — nenhum documento arquivado é perdido por engano."""
    if len(content) > SIMPLE_UPLOAD_LIMIT:
        raise DriveError(
            "Arquivo acima de 4 MB ainda não suportado neste conector (exige upload em sessão)"
        )

    url = (
        f"{GRAPH}/me/drive/items/{folder_id}:/{_encode_path(filename)}:/content"
        "?@microsoft.graph.conflictBehavior=rename"
    )
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.put(
            url, headers={**_headers(access_token), "Content-Type": content_type}, content=content
        )
    if response.status_code >= 400:
        raise DriveError(f"Falha ao gravar o arquivo no drive: {response.text[:300]}")

    item = response.json()
    return ArquivoSalvo(
        item_id=item["id"],
        nome=item["name"],
        caminho=(item.get("parentReference", {}).get("path", "") + "/" + item["name"]),
        web_url=item.get("webUrl", ""),
        tamanho=int(item.get("size", len(content))),
    )


async def download_file(access_token: str, item_id: str) -> bytes:
    """Busca o arquivo no drive do cliente para servi-lo ao time de campo pelo nosso
    link assinado — quem está na obra não costuma ter licença Microsoft 365."""
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        response = await client.get(f"{GRAPH}/me/drive/items/{item_id}/content", headers=_headers(access_token))
    if response.status_code >= 400:
        raise DriveError(f"Não consegui baixar o arquivo do drive: {response.text[:200]}")
    return response.content
