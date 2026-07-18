"""Seed inicial para o piloto Persa: cria a empresa, uma obra, um admin de qualidade
(login+senha) e um usuário de campo. Rode após aplicar a migration 0001_init.sql.

Uso:
    python -m scripts.seed --admin-email qualidade@persa.com --admin-password <senha>
"""

import argparse
import asyncio

from app.auth import hash_password
from app.db import async_session
from app.models import Company, Site, User


async def seed(admin_email: str, admin_password: str):
    async with async_session() as db:
        company = Company(name="Persa")
        db.add(company)
        await db.flush()

        site = Site(company_id=company.id, name="Obra Piloto", active=True)
        db.add(site)
        await db.flush()

        admin = User(
            company_id=company.id,
            name="Admin Qualidade",
            role="engenheiro de qualidade",
            is_admin=True,
            email=admin_email,
            password_hash=hash_password(admin_password),
        )
        field_user = User(
            company_id=company.id,
            name="Mestre de Obra",
            role="mestre de obra",
            phone_number="+5511999990000",
            site_id=site.id,
        )
        engineer = User(
            company_id=company.id,
            name="Eng. Responsável",
            role="engenheiro de obra",
            phone_number="+5511988887777",
            site_id=site.id,
        )
        db.add_all([admin, field_user, engineer])
        await db.commit()

        print("Seed concluído.")
        print(f"  company_id = {company.id}")
        print(f"  site_id    = {site.id}")
        print(f"  admin      = {admin_email}")
        print(f"  field_user_id (para testar o chat) = {field_user.id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-password", required=True)
    args = parser.parse_args()
    asyncio.run(seed(args.admin_email, args.admin_password))
