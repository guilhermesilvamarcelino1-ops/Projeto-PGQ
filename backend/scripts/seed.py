"""Onboarding/seed de uma empresa. Cria company, obra, admin (email+senha) e um
usuário de campo (telefone+PIN).

Onboarding é uma operação PRIVILEGIADA do operador da plataforma — cria uma empresa
nova, que por definição ainda não tem contexto de RLS. Por isso este script conecta
com uma URL privilegiada (papel `postgres`, que ignora RLS), passada em
ADMIN_DATABASE_URL, e NÃO com a conexão app_tenant usada pelo backend.

Uso:
    ADMIN_DATABASE_URL=postgresql+asyncpg://postgres:<senha>@db.<ref>.supabase.co:5432/postgres \\
    python -m scripts.seed --company "Persa" \\
        --admin-email qualidade@persa.com --admin-password '<senha>' \\
        --field-name "Mestre de Obra" --field-phone "+5511999990000" --field-pin 1234
"""

import argparse
import asyncio
import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth import hash_secret
from app.models import Company, Site, User


async def seed(args):
    admin_url = os.environ.get("ADMIN_DATABASE_URL")
    if not admin_url:
        raise SystemExit("Defina ADMIN_DATABASE_URL (conexão postgres privilegiada) para o onboarding.")

    engine = create_async_engine(admin_url, connect_args={"statement_cache_size": 0})
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        company = Company(name=args.company)
        db.add(company)
        await db.flush()

        site = Site(company_id=company.id, name=args.site, active=True)
        db.add(site)
        await db.flush()

        admin = User(
            company_id=company.id,
            name="Admin Qualidade",
            role="engenheiro de qualidade",
            is_admin=True,
            email=args.admin_email,
            password_hash=hash_secret(args.admin_password),
        )
        field_user = User(
            company_id=company.id,
            name=args.field_name,
            role="mestre de obra",
            phone_number=args.field_phone,
            pin_hash=hash_secret(args.field_pin),
            site_id=site.id,
        )
        engineer = User(
            company_id=company.id,
            name="Eng. Responsável",
            role="engenheiro de obra",
            phone_number=args.engineer_phone,
            site_id=site.id,
        )
        db.add_all([admin, field_user, engineer])
        await db.commit()

        print("Seed concluído.")
        print(f"  company_id    = {company.id}")
        print(f"  site_id       = {site.id}")
        print(f"  admin login   = {args.admin_email}")
        print(f"  field login   = telefone {args.field_phone} + PIN informado")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", default="Persa")
    parser.add_argument("--site", default="Obra Piloto")
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-password", required=True)
    parser.add_argument("--field-name", default="Mestre de Obra")
    parser.add_argument("--field-phone", default="+5511999990000")
    parser.add_argument("--field-pin", required=True)
    parser.add_argument("--engineer-phone", default="+5511988887777")
    asyncio.run(seed(parser.parse_args()))
