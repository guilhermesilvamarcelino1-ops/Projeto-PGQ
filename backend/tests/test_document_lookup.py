"""Integration test for administrative document lookup. Requires a Postgres instance
(with pgvector) reachable via DATABASE_URL; skipped automatically when unavailable so
the unit suite stays runnable without infra.
"""

import uuid

import pytest
from sqlalchemy import text

from app.db import async_session, engine
from app.models import Company, Document, Site
from app.services.document_lookup import find_administrative_document


async def _db_available() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
        return True
    except Exception:
        return False


@pytest.fixture
async def seeded():
    if not await _db_available():
        pytest.skip("Postgres não disponível (DATABASE_URL)")
    async with async_session() as db:
        company = Company(name="Persa Teste")
        db.add(company)
        await db.flush()
        site = Site(company_id=company.id, name="Empreendimento Alpha")
        db.add(site)
        await db.flush()
        doc = Document(
            company_id=company.id,
            title="Alvará de Construção - Alpha",
            category="alvara",
            kind="administrativo",
            site_id=site.id,
            file_path="/tmp/alvara_alpha.pdf",
        )
        db.add(doc)
        await db.commit()
        yield company, site, doc
        await db.delete(doc)
        await db.delete(site)
        await db.delete(company)
        await db.commit()


async def test_finds_admin_document_by_site_and_text(seeded):
    company, site, doc = seeded
    async with async_session() as db:
        found = await find_administrative_document(
            db, company_id=company.id, site_id=site.id, search_text="alvará"
        )
    assert found is not None
    assert found.id == doc.id


async def test_no_match_returns_none(seeded):
    company, site, _ = seeded
    async with async_session() as db:
        found = await find_administrative_document(
            db, company_id=company.id, site_id=site.id, search_text="habite-se"
        )
    assert found is None
