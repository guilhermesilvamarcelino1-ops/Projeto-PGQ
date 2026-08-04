"""Identificação do usuário de campo pelo número de telefone.

Com um número central de WhatsApp para todos os clientes, é o número de QUEM ENVIA
que diz quem é a pessoa e a que empresa ela pertence — daí o telefone precisar ser
único no sistema inteiro (índice em migrations/0005) e ser comparado sempre na mesma
forma normalizada.
"""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User

# Resposta a um número que não está cadastrado em nenhuma empresa. O assistente não
# pode responder nada de conteúdo: não sabe de qual empresa é a pessoa, nem se ela é
# funcionária. Usada pelo webhook do WhatsApp.
UNKNOWN_NUMBER_MESSAGE = (
    "Olá! Não reconheço este número.\n\n"
    "Para usar o Procede, seu telefone precisa estar cadastrado pela sua empresa. "
    "Fale com o responsável pela qualidade e peça o cadastro."
)


def normalize_phone(raw: str | None) -> str | None:
    """Deixa todo telefone na mesma forma (+55DDNÚMERO), venha de onde vier.

    É necessário porque cada origem manda um formato diferente: o WhatsApp entrega
    "5511999990000", o cadastro pode vir como "(11) 99999-0000" ou "+55 11 99999-0000".
    Sem isso, o mesmo telefone não bate com ele mesmo e o funcionário não é reconhecido.
    """
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    # Número brasileiro digitado sem o código do país (10 dígitos = fixo com DDD,
    # 11 = celular com DDD): assume Brasil.
    if len(digits) in (10, 11):
        digits = f"55{digits}"
    return f"+{digits}"


async def resolve_user_by_phone(db: AsyncSession, phone: str) -> User | None:
    """Descobre quem é a pessoa (e, por consequência, a empresa dela) pelo telefone.
    Devolve None quando o número não está cadastrado — o chamador responde com
    UNKNOWN_NUMBER_MESSAGE e não acessa nenhum dado."""
    normalized = normalize_phone(phone)
    if normalized is None:
        return None
    result = await db.execute(select(User).where(User.phone_number == normalized))
    return result.scalar_one_or_none()
