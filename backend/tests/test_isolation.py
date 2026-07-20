"""Prova, contra um Postgres real, que o RLS isola os dados por empresa.

Requer duas conexões, passadas por variáveis de ambiente, e é pulado quando ausentes:
  - ADMIN_DATABASE_URL: conexão privilegiada (postgres) para o onboarding das empresas.
  - DATABASE_URL: conexão do backend (papel app_tenant, sujeito a RLS).

Cenário: cria empresa A e empresa B, cada uma com um documento administrativo.
Conectado como app_tenant no contexto de A, o backend só pode enxergar o documento
de A — o de B é invisível mesmo sem nenhum filtro na query.
"""

import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import tenant_session
from app.models import Company, Document
from app.services.document_lookup import find_administrative_document

ADMIN_URL = os.environ.get("ADMIN_DATABASE_URL")
APP_URL = os.environ.get("DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not ADMIN_URL or "app_tenant" not in APP_URL,
    reason="Requer ADMIN_DATABASE_URL (postgres) e DATABASE_URL apontando para app_tenant",
)


@pytest.fixture
async def two_companies():
    engine = create_async_engine(ADMIN_URL, connect_args={"statement_cache_size": 0})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        a = Company(name=f"A-{uuid.uuid4().hex[:6]}")
        b = Company(name=f"B-{uuid.uuid4().hex[:6]}")
        db.add_all([a, b])
        await db.flush()
        doc_a = Document(company_id=a.id, title="Alvará A", category="alvara", kind="administrativo", file_path="/tmp/a")
        doc_b = Document(company_id=b.id, title="Alvará B", category="alvara", kind="administrativo", file_path="/tmp/b")
        db.add_all([doc_a, doc_b])
        await db.commit()
        ids = (a.id, b.id, doc_a.id, doc_b.id)
        yield ids
        for did in (doc_a.id, doc_b.id):
            await db.execute(text("delete from documents where id = :i"), {"i": did})
        for cid in (a.id, b.id):
            await db.execute(text("delete from companies where id = :i"), {"i": cid})
        await db.commit()
    await engine.dispose()


async def test_tenant_sees_only_its_own_documents(two_companies):
    a_id, b_id, doc_a_id, doc_b_id = two_companies

    # Contexto da empresa A: só enxerga o documento de A.
    async with tenant_session(a_id) as db:
        found = await find_administrative_document(db, company_id=a_id, site_id=None, search_text="alvará")
        assert found is not None and found.id == doc_a_id
        # Tentar puxar o documento de B explicitamente não retorna nada.
        leaked = await db.execute(text("select count(*) from documents where id = :i"), {"i": str(doc_b_id)})
        assert leaked.scalar() == 0


async def test_no_context_returns_nothing(two_companies):
    a_id, *_ = two_companies
    async with tenant_session(a_id) as db:
        pass  # apenas garante que o fixture cria dados

    # Sem contexto de empresa, nenhuma linha é visível (fail-closed).
    from app.db import async_session

    async with async_session() as db:
        rows = await db.execute(text("select count(*) from documents"))
        assert rows.scalar() == 0
