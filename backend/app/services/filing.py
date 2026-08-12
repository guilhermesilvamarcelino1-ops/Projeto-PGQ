"""Arquivamento: leva o documento confirmado ao lugar certo.

O destino é o drive do próprio cliente, com a estrutura de pastas do RQ 15 dele. Se
ainda não houver drive conectado, o arquivo é guardado localmente e o documento fica
marcado como `upload` — assim é possível validar classificação, nomenclatura e caminho
antes de a conexão com a Microsoft existir, sem inventar um destino falso.
"""

import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import DriveConnection
from app.services import onedrive


@dataclass
class Arquivado:
    onde: str  # 'onedrive' ou 'local'
    caminho: str
    file_path: str | None  # cópia local, quando houver
    external_id: str | None
    external_url: str | None


def _staging_dir(company_id: uuid.UUID) -> Path:
    caminho = Path(settings.storage_dir) / str(company_id) / "_aguardando"
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def stage_file(company_id: uuid.UUID, filename: str, conteudo: bytes) -> str:
    """Guarda o arquivo enquanto ele aguarda confirmação — ainda fora do acervo."""
    destino = _staging_dir(company_id) / f"{uuid.uuid4()}_{filename}"
    destino.write_bytes(conteudo)
    return str(destino)


async def _conexao_ativa(db: AsyncSession, company_id: uuid.UUID) -> DriveConnection | None:
    return (
        await db.execute(
            select(DriveConnection).where(
                DriveConnection.company_id == company_id, DriveConnection.active.is_(True)
            )
        )
    ).scalar_one_or_none()


async def arquivar(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    caminho_pasta: str,
    nome_arquivo: str,
    conteudo: bytes,
    content_type: str,
) -> Arquivado:
    """Grava o documento no destino final e devolve onde ele ficou."""
    conexao = await _conexao_ativa(db, company_id)

    if conexao is None:
        # Modo local: sem drive conectado, o acervo fica aqui. Serve para validar o
        # fluxo antes da conexão existir; o documento continua achável pelo chat.
        pasta = Path(settings.storage_dir) / str(company_id) / caminho_pasta
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / nome_arquivo
        destino.write_bytes(conteudo)
        return Arquivado(
            onde="local",
            caminho=caminho_pasta,
            file_path=str(destino),
            external_id=None,
            external_url=None,
        )

    from app.routers.drive import get_valid_access_token  # import tardio: evita ciclo

    access_token, _ = await get_valid_access_token(db, company_id)
    raiz = (conexao.root_path or "").strip("/")
    caminho_completo = f"{raiz}/{caminho_pasta}".strip("/") if raiz else caminho_pasta

    folder_id = await onedrive.ensure_folder(access_token, caminho_completo)
    salvo = await onedrive.upload_file(
        access_token,
        folder_id=folder_id,
        filename=nome_arquivo,
        content=conteudo,
        content_type=content_type or "application/octet-stream",
    )
    return Arquivado(
        onde="onedrive",
        caminho=caminho_completo,
        file_path=None,  # o arquivo vive no drive do cliente; não guardamos cópia
        external_id=salvo.item_id,
        external_url=salvo.web_url,
    )
