import uuid
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
async def tenant_session(company_id: uuid.UUID):
    """Sessão com o contexto da empresa fixado por transação via set_config
    (is_local=true). Toda query aqui dentro é filtrada pelo RLS por company_id;
    sem esse contexto o banco não devolve nenhuma linha das tabelas de conteúdo."""
    async with async_session() as session:
        async with session.begin():
            await session.execute(
                text("select set_config('app.current_company_id', :cid, true)"),
                {"cid": str(company_id)},
            )
            yield session
