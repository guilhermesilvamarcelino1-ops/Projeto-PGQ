"""Carrega a taxonomia documental de uma empresa (o 'RQ 15' dela) a partir de um JSON.

Cada cliente traz a própria taxonomia no onboarding — é por isso que ela é dado, e não
prompt. Rodar de novo com o mesmo arquivo atualiza os tipos existentes (casados por
código, ou por nome quando não há código) e acrescenta os novos, sem duplicar.

Uso:
    ADMIN_DATABASE_URL=postgresql+asyncpg://postgres:<senha>@db.<ref>.supabase.co:5432/postgres \\
    python -m scripts.load_taxonomy --company "Persa" --file data/taxonomia_persa_rq15.json
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Company, DocumentType

CAMPOS = (
    "code", "name", "family", "medium", "storage_path", "physical_location",
    "external_system", "recovery_key", "retention_rule", "retention_months",
    "disposal", "has_revisions", "contains_personal_data",
)


def _validar(tipo: dict, indice: int) -> None:
    """Falha cedo e com mensagem clara: taxonomia carregada errada contamina
    classificação, nomenclatura e alertas de vencimento."""
    for campo in ("name", "family", "medium", "retention_rule", "disposal"):
        if not tipo.get(campo):
            raise SystemExit(f"Tipo #{indice} ('{tipo.get('name', '?')}'): campo obrigatório '{campo}' ausente")
    if tipo["retention_rule"] == "meses" and not tipo.get("retention_months"):
        raise SystemExit(f"Tipo #{indice} ('{tipo['name']}'): retention_rule='meses' exige retention_months")
    if tipo["medium"] == "sistema" and not tipo.get("external_system"):
        raise SystemExit(f"Tipo #{indice} ('{tipo['name']}'): medium='sistema' exige external_system")


async def load(company_name: str, file_path: Path):
    admin_url = os.environ.get("ADMIN_DATABASE_URL")
    if not admin_url:
        raise SystemExit("Defina ADMIN_DATABASE_URL (conexão postgres privilegiada).")

    dados = json.loads(file_path.read_text(encoding="utf-8"))
    tipos = dados["tipos"]
    for i, tipo in enumerate(tipos, start=1):
        _validar(tipo, i)

    engine = create_async_engine(admin_url, connect_args={"statement_cache_size": 0})
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as db:
        company = (await db.execute(select(Company).where(Company.name == company_name))).scalar_one_or_none()
        if company is None:
            raise SystemExit(f"Empresa '{company_name}' não encontrada. Rode o seed primeiro.")

        existentes = (
            await db.execute(select(DocumentType).where(DocumentType.company_id == company.id))
        ).scalars().all()
        por_codigo = {d.code: d for d in existentes if d.code}
        por_nome = {d.name: d for d in existentes if not d.code}

        criados = atualizados = 0
        for tipo in tipos:
            valores = {campo: tipo.get(campo) for campo in CAMPOS}
            valores["has_revisions"] = bool(tipo.get("has_revisions", False))
            valores["contains_personal_data"] = bool(tipo.get("contains_personal_data", False))

            atual = por_codigo.get(tipo.get("code")) if tipo.get("code") else por_nome.get(tipo["name"])
            if atual is None:
                db.add(DocumentType(company_id=company.id, **valores))
                criados += 1
            else:
                for campo, valor in valores.items():
                    setattr(atual, campo, valor)
                atualizados += 1

        await db.commit()

    await engine.dispose()

    com_dado_pessoal = sum(1 for t in tipos if t.get("contains_personal_data"))
    print(f"Taxonomia de '{company_name}' carregada: {criados} criados, {atualizados} atualizados.")
    print(f"  {com_dado_pessoal} tipos marcados com dado pessoal (acesso restrito por LGPD).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", required=True)
    parser.add_argument("--file", required=True, type=Path)
    args = parser.parse_args()
    asyncio.run(load(args.company, args.file))
