import uuid
from collections.abc import Sequence
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

# statement_cache_size=0 mantém a conexão segura com os poolers do Supabase
# (transaction mode / PgBouncer), que não suportam prepared statements persistentes.
engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"statement_cache_size": 0},
)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """Sessão sem contexto de empresa. Usada só na resolução de identidade
    (login/telefone), que precisa acontecer antes de existir company_id."""
    async with async_session() as session:
        yield session


@asynccontextmanager
async def tenant_session(company_id: uuid.UUID, families: Sequence[str] = ()):
    """Sessão com empresa E famílias permitidas fixadas por transação (set_config
    local). Toda query aqui dentro é filtrada pelo RLS: sem contexto de empresa, ou
    para uma família fora da lista, o banco não devolve nenhuma linha.

    `families` vazio é fail-closed de propósito — quem não recebeu acesso não vê
    documento nenhum, em vez de ver tudo."""
    async with async_session() as session:
        async with session.begin():
            await session.execute(
                text(
                    "select set_config('app.current_company_id', :cid, true),"
                    "       set_config('app.current_families', :fam, true)"
                ),
                {"cid": str(company_id), "fam": ",".join(families)},
            )
            yield session
