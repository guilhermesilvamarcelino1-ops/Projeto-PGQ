"""Quais famílias de documento cada pessoa alcança.

Resolvido ANTES de abrir a sessão com contexto — é essa lista que o RLS vai usar
para recusar tudo o mais. Ausência de concessão significa sem acesso: quem nunca
foi liberado não vê documento nenhum, em vez de ver tudo.
"""

import uuid
from contextlib import asynccontextmanager

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import tenant_session
from app.models import UserFamilyAccess

FAMILIES = (
    "qualidade_gestao",
    "projetos_obra",
    "suprimentos",
    "comercial_cliente",
    "pessoas_seguranca",
)

FAMILY_LABELS = {
    "qualidade_gestao": "Qualidade e gestão",
    "projetos_obra": "Projetos e obra",
    "suprimentos": "Suprimentos e fornecedores",
    "comercial_cliente": "Comercial e cliente",
    "pessoas_seguranca": "Pessoas, treinamento e segurança do trabalho",
}

# Acesso concedido a um usuário de campo recém-cadastrado. Deliberadamente não
# inclui 'pessoas_seguranca' nem 'comercial_cliente': são as famílias com dado
# pessoal, e ninguém deve alcançá-las por padrão.
DEFAULT_FIELD_FAMILIES = ("qualidade_gestao", "projetos_obra")


async def resolve_families(db: AsyncSession, *, user_id: uuid.UUID, is_admin: bool) -> tuple[str, ...]:
    """Famílias que este usuário pode consultar.

    Admin da empresa enxerga todas — é quem administra a documentação. Os demais,
    apenas o que lhes foi concedido explicitamente.
    """
    if is_admin:
        return FAMILIES

    result = await db.execute(select(UserFamilyAccess.family).where(UserFamilyAccess.user_id == user_id))
    return tuple(result.scalars().all())


@asynccontextmanager
async def authorized_session(principal):
    """Abre a sessão já restrita ao que este usuário pode ver.

    A concessão é lida com o contexto da empresa (a tabela de concessões não é
    filtrada por família, senão não haveria como descobri-las) e, na mesma
    transação, o contexto de famílias é fixado. Da linha seguinte em diante, o
    banco recusa qualquer documento fora dessas famílias.
    """
    async with tenant_session(principal.company_id) as db:
        families = await resolve_families(db, user_id=principal.user_id, is_admin=principal.is_admin)
        await db.execute(
            text("select set_config('app.current_families', :fam, true)"), {"fam": ",".join(families)}
        )
        yield db, families


async def resolve_upload_families(db: AsyncSession, *, user_id: uuid.UUID, is_admin: bool) -> tuple[str, ...]:
    """Famílias nas quais este usuário pode ARQUIVAR documento novo. Ler e enviar
    são permissões separadas: o mestre de obra consulta o procedimento, mas nem
    todo mundo que consulta pode alimentar o acervo."""
    if is_admin:
        return FAMILIES

    result = await db.execute(
        select(UserFamilyAccess.family).where(
            UserFamilyAccess.user_id == user_id, UserFamilyAccess.can_upload.is_(True)
        )
    )
    return tuple(result.scalars().all())
