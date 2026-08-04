"""A taxonomia é o ativo central: dela saem a classificação, o nome do arquivo, a pasta
de destino e os alertas de vencimento. Um erro de transcrição aqui se propaga em silêncio
para tudo isso — daí validar o arquivo como se fosse código.
"""

import json
from pathlib import Path

import pytest

TAXONOMIA = Path(__file__).resolve().parents[1] / "data" / "taxonomia_persa_rq15.json"

FAMILIAS = {"qualidade_gestao", "projetos_obra", "suprimentos", "comercial_cliente", "pessoas_seguranca"}
MEIOS = {"eletronico", "fisico", "ambos", "sistema"}
RETENCOES = {"permanente", "ate_proxima_atualizacao", "fim_de_obra", "meses", "ate_validade", "tempo_contratacao"}
DESCARTES = {"arquivo_permanente", "substituir", "destruir", "acervo_tecnico"}


@pytest.fixture(scope="module")
def tipos():
    return json.loads(TAXONOMIA.read_text(encoding="utf-8"))["tipos"]


def test_taxonomia_tem_volume_esperado(tipos):
    # O RQ 15 da Persa mapeia dezenas de tipos; um arquivo truncado passaria despercebido.
    assert len(tipos) >= 80


def test_todos_os_campos_estao_nos_valores_permitidos(tipos):
    for tipo in tipos:
        assert tipo["family"] in FAMILIAS, tipo["name"]
        assert tipo["medium"] in MEIOS, tipo["name"]
        assert tipo["retention_rule"] in RETENCOES, tipo["name"]
        assert tipo["disposal"] in DESCARTES, tipo["name"]


def test_retencao_em_meses_sempre_tem_prazo(tipos):
    """Sem o prazo, o alerta de vencimento não tem como ser calculado."""
    for tipo in tipos:
        if tipo["retention_rule"] == "meses":
            assert tipo.get("retention_months"), tipo["name"]


def test_documento_eletronico_tem_pasta_e_fisico_tem_local(tipos):
    """Sem destino, o arquivamento automático não sabe onde guardar (nem o que instruir
    sobre a via em papel)."""
    for tipo in tipos:
        if tipo["medium"] in ("eletronico", "ambos"):
            assert tipo.get("storage_path"), f"{tipo['name']}: falta storage_path"
        if tipo["medium"] in ("fisico", "ambos"):
            assert tipo.get("physical_location"), f"{tipo['name']}: falta physical_location"
        if tipo["medium"] == "sistema":
            assert tipo.get("external_system"), f"{tipo['name']}: falta external_system"


def test_documentos_de_pessoas_marcam_dado_pessoal(tipos):
    """LGPD: documento de RH/funcionário não pode aparecer no chat do time de campo.
    A marcação é o que sustenta essa restrição."""
    pessoais = [t for t in tipos if t["family"] == "pessoas_seguranca"]
    assert len(pessoais) >= 20
    nao_marcados = [t["name"] for t in pessoais if not t.get("contains_personal_data")]
    # Só a inspeção de extintores não trata de pessoa identificável.
    assert nao_marcados == ["Inspeção mensal dos extintores"], nao_marcados


def test_documentos_trabalhistas_retem_30_anos(tipos):
    """Prazo trabalhista é o mais longo da tabela; se vier errado, o sistema sugeriria
    descarte de documento que precisa ser guardado por 30 anos."""
    trabalhistas = [t for t in tipos if "trabalhistas" in t["name"] or "departamento pessoal" in t["name"]]
    assert len(trabalhistas) == 2
    for tipo in trabalhistas:
        assert tipo["retention_months"] == 360, tipo["name"]


def test_codigos_nao_se_repetem(tipos):
    codigos = [t["code"] for t in tipos if t.get("code")]
    assert len(codigos) == len(set(codigos)), "código RQ duplicado na taxonomia"


def test_descarte_por_destruicao_e_excecao_explicita(tipos):
    """'Destruir' só vale quando está escrito na tabela — errar guardando não gera
    prejuízo, errar descartando sim."""
    destruir = {t["name"] for t in tipos if t["disposal"] == "destruir"}
    assert destruir == {
        "Ordem de Serviço por atividade",
        "Projeto Layout do Canteiro",
        "Cronograma de acompanhamento de obra",
        "Inspeção mensal dos extintores",
    }
