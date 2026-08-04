"""Classificação de documento.

O erro caro aqui não é deixar de classificar — é classificar errado em silêncio: um
laudo arquivado como ata é um documento que ninguém encontra no dia da auditoria.
Por isso os testes cobrem principalmente as recusas: tipo fora da taxonomia, índice
inválido e baixa confiança.
"""

import uuid
from dataclasses import dataclass
from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.services import classification
from app.services.classification import PropostaArquivamento, classify_document, format_proposal
from app.services.naming import CamposDocumento


@dataclass
class FakeTipo:
    name: str
    code: str | None = None
    family: str = "projetos_obra"
    recovery_key: str | None = "Data"
    storage_path: str | None = None
    physical_location: str | None = None
    medium: str = "fisico"
    has_revisions: bool = False
    contains_personal_data: bool = False


RASTREABILIDADE = FakeTipo(
    name="Rastreabilidade do concreto",
    code="RQ 30",
    recovery_key="Data",
    physical_location="Obra, sala administrativo / pasta obra",
    medium="fisico",
)
NR35 = FakeTipo(
    name="Segurança do Trabalho: certificados NR-35 (trabalho em altura)",
    code=None,
    family="pessoas_seguranca",
    recovery_key="Nome da obra",
    physical_location="Escritório / pasta de treinamentos",
    medium="fisico",
    contains_personal_data=True,
)


class ToolUseBlock:
    type = "tool_use"

    def __init__(self, input_data: dict):
        self.input = input_data


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeScalars:
    def __init__(self, valores):
        self._valores = valores

    def scalars(self):
        return self

    def all(self):
        return self._valores

    def scalar(self):
        return self._valores


class FakeDB:
    def __init__(self, tipos):
        self.tipos = tipos

    async def execute(self, _stmt):
        return FakeScalars(self.tipos)


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    monkeypatch.setattr(classification, "_client", AsyncMock())


def _responde(dados: dict):
    classification._client.messages.create = AsyncMock(
        return_value=FakeResponse([ToolUseBlock(dados)])
    )


async def test_documento_identificado_gera_nome_e_pasta():
    _responde(
        {
            "indice_tipo": 1,
            "confianca": "alta",
            "data_documento": "2026-03-12",
            "obra": "Vila Nova",
            "complementos": ["NF 4471"],
            "justificativa": "Formulário de rastreabilidade preenchido.",
        }
    )
    proposta = await classify_document(
        FakeDB([RASTREABILIDADE]),
        company_id=uuid.uuid4(),
        families=("projetos_obra",),
        file_bytes=b"%PDF-fake",
        content_type="application/pdf",
        user_hint="rastreabilidade da concretagem de hoje",
    )

    assert proposta.mapeado is True
    assert proposta.nome_arquivo == "2026-03-12_RQ30_RASTREABILIDADE-CONCRETO_NF-4471_VILA-NOVA"
    assert proposta.exige_via_fisica is True
    assert proposta.local_fisico == "Obra, sala administrativo / pasta obra"


async def test_tipo_fora_da_taxonomia_nao_arquiva_nem_inventa_pasta():
    """Documento não mapeado não recebe código nem destino chutado."""
    _responde({"indice_tipo": 0, "confianca": "media", "justificativa": "Não corresponde a nenhum tipo."})
    proposta = await classify_document(
        FakeDB([RASTREABILIDADE]),
        company_id=uuid.uuid4(),
        families=("projetos_obra",),
        file_bytes=b"x",
        content_type="application/pdf",
    )

    assert proposta.mapeado is False
    assert proposta.nome_arquivo is None
    assert proposta.caminho is None
    texto = format_proposal(proposta, "Valdir")
    assert "não encontrei este documento" in texto
    assert "RQ 15" in texto


async def test_indice_invalido_e_tratado_como_nao_mapeado():
    """Blindagem: índice fora da lista não pode virar acesso a outro tipo."""
    _responde({"indice_tipo": 99, "confianca": "alta", "justificativa": "..."})
    proposta = await classify_document(
        FakeDB([RASTREABILIDADE]),
        company_id=uuid.uuid4(),
        families=("projetos_obra",),
        file_bytes=b"x",
        content_type="application/pdf",
    )
    assert proposta.mapeado is False


async def test_validade_lida_do_documento_alimenta_o_aviso_de_vencimento():
    _responde(
        {
            "indice_tipo": 1,
            "confianca": "alta",
            "data_documento": "2026-01-10",
            "data_validade": "2028-01-10",
            "obra": "Vila Nova",
            "pessoa": "Carlos Andrade",
            "justificativa": "Certificado com validade de 2 anos.",
        }
    )
    proposta = await classify_document(
        FakeDB([NR35]),
        company_id=uuid.uuid4(),
        families=("pessoas_seguranca",),
        file_bytes=b"x",
        content_type="image/jpeg",
    )

    assert proposta.data_validade == date(2028, 1, 10)
    assert proposta.contem_dado_pessoal is True
    texto = format_proposal(proposta)
    assert "Vence em 10/01/2028" in texto
    assert "dado pessoal" in texto


async def test_taxonomia_oferecida_respeita_as_familias_do_usuario():
    """Quem não tem acesso a RH não pode nem ver os tipos de RH entre as opções."""
    db = FakeDB([])
    with pytest.raises(ValueError, match="Nenhum tipo"):
        await classify_document(
            db,
            company_id=uuid.uuid4(),
            families=(),
            file_bytes=b"x",
            content_type="application/pdf",
        )


def test_baixa_confianca_avisa_antes_de_confirmar():
    proposta = PropostaArquivamento(
        tipo=RASTREABILIDADE,
        mapeado=True,
        confianca="baixa",
        justificativa="Documento cortado na foto.",
        nome_arquivo="2026-03-12_RQ30_RASTREABILIDADE-CONCRETO",
        caminho=None,
        campos=CamposDocumento(data=date(2026, 3, 12)),
        data_validade=None,
        exige_via_fisica=False,
        local_fisico=None,
        contem_dado_pessoal=False,
    )
    texto = format_proposal(proposta, "Valdir")
    assert texto.startswith("Valdir, identifiquei")
    assert "Não tenho certeza" in texto
    assert "Confirma o arquivamento?" in texto
