"""Permissão por família — a barreira que impede o assistente de virar canal de
vazamento de dado pessoal.

31 dos 86 tipos da taxonomia da Persa carregam dado pessoal (RH, funcionário,
cliente). Se a busca do chat alcançasse essas famílias, o mestre de obra perguntando
qualquer coisa poderia receber trecho de ficha de funcionário ou ASO — LGPD.
"""

import uuid
from dataclasses import dataclass

import pytest

from app.services.access import (
    DEFAULT_FIELD_FAMILIES,
    FAMILIES,
    FAMILY_LABELS,
    resolve_families,
    resolve_upload_families,
)


@dataclass
class FakePrincipal:
    user_id: uuid.UUID
    company_id: uuid.UUID
    is_admin: bool


class FakeResult:
    def __init__(self, valores):
        self._valores = valores

    def scalars(self):
        return self

    def all(self):
        return self._valores


class FakeDB:
    """Devolve as concessões que o teste definir, sem tocar no banco."""

    def __init__(self, concessoes):
        self.concessoes = concessoes
        self.consultou = False

    async def execute(self, _stmt):
        self.consultou = True
        return FakeResult(self.concessoes)


def test_familia_com_dado_pessoal_nao_entra_no_padrao():
    """O padrão de um usuário de campo recém-cadastrado não pode incluir RH nem
    cliente: liberar por engano é vazamento, negar por engano é só um pedido."""
    assert "pessoas_seguranca" not in DEFAULT_FIELD_FAMILIES
    assert "comercial_cliente" not in DEFAULT_FIELD_FAMILIES
    assert set(DEFAULT_FIELD_FAMILIES) == {"qualidade_gestao", "projetos_obra"}


async def test_usuario_sem_concessao_nao_ve_nada():
    """Ausência de concessão significa sem acesso — nunca acesso total."""
    db = FakeDB([])
    familias = await resolve_families(db, user_id=uuid.uuid4(), is_admin=False)
    assert familias == ()


async def test_usuario_de_campo_ve_apenas_o_concedido():
    db = FakeDB(["qualidade_gestao", "projetos_obra"])
    familias = await resolve_families(db, user_id=uuid.uuid4(), is_admin=False)
    assert set(familias) == {"qualidade_gestao", "projetos_obra"}
    assert "pessoas_seguranca" not in familias


async def test_admin_alcanca_todas_sem_consultar_concessoes():
    db = FakeDB([])
    familias = await resolve_families(db, user_id=uuid.uuid4(), is_admin=True)
    assert set(familias) == set(FAMILIES)
    assert db.consultou is False


async def test_ler_e_arquivar_sao_permissoes_separadas():
    """Quem consulta o procedimento não necessariamente pode alimentar o acervo."""
    somente_leitura = FakeDB([])  # nenhuma concessão com can_upload
    familias = await resolve_upload_families(somente_leitura, user_id=uuid.uuid4(), is_admin=False)
    assert familias == ()


def test_toda_familia_tem_rotulo_legivel():
    """As famílias aparecem na tela de permissões do painel; sem rótulo, o admin
    veria 'pessoas_seguranca' e teria que adivinhar."""
    assert set(FAMILY_LABELS) == set(FAMILIES)
    assert all(FAMILY_LABELS[f] for f in FAMILIES)
