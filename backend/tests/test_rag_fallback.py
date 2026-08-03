"""O fallback é o comportamento mais crítico do produto: o assistente nunca pode
responder por conhecimento geral, e precisa dizer isso explicitamente quando o material
recuperado não cobre a pergunta. Estes testes exercitam essa fronteira direto em
`answer_procedure_question` / `answer_document_request`, com o LLM e o banco mockados.
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.services import rag
from tests.conftest import make_chunk


class ToolUseBlock:
    type = "tool_use"

    def __init__(self, input_data: dict):
        self.input = input_data


class FakeResponse:
    def __init__(self, content):
        self.content = content


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    # Qualquer teste que esqueça de mockar o cliente deve falhar alto, não ir à rede.
    monkeypatch.setattr(rag, "_client", AsyncMock())


async def test_no_chunks_retrieved_triggers_fallback(monkeypatch):
    monkeypatch.setattr(rag, "retrieve_chunks", AsyncMock(return_value=[]))
    result = await rag.answer_procedure_question(
        db=object(),
        company_id=uuid.uuid4(),
        query="Qual o prazo de garantia da impermeabilização?",
        contact="João, 11999990000",
        user_first_name="Valdir",
    )
    assert result.had_fallback is True
    assert "João" in result.answer
    assert "Valdir" in result.answer
    rag._client.messages.create.assert_not_called()


async def test_model_reports_not_found_triggers_fallback(monkeypatch):
    chunks = [make_chunk("POP de Concretagem", "Item 4.2: o traço deve seguir o memorial estrutural.")]
    monkeypatch.setattr(rag, "retrieve_chunks", AsyncMock(return_value=chunks))
    rag._client.messages.create = AsyncMock(
        return_value=FakeResponse(
            [ToolUseBlock({"found": False, "answer": "não encontrado", "quote": "", "source_index": 0})]
        )
    )

    result = await rag.answer_procedure_question(
        db=object(),
        company_id=uuid.uuid4(),
        query="Qual a cor da tinta usada na fachada?",
        contact="Maria, 11988887777",
        user_first_name="Valdir",
    )

    assert result.had_fallback is True
    assert "Maria" in result.answer
    assert "não encontrei" in result.answer.lower()
    assert result.chunks_used == []


async def test_answer_includes_literal_quote_and_link(monkeypatch):
    chunk = make_chunk(
        "POP de Concretagem",
        "Item 4.3: a cura deve manter a superfície úmida por no mínimo 7 dias.",
        section_ref="4.3",
        page_ref=12,
    )
    monkeypatch.setattr(rag, "retrieve_chunks", AsyncMock(return_value=[chunk]))
    rag._client.messages.create = AsyncMock(
        return_value=FakeResponse(
            [
                ToolUseBlock(
                    {
                        "found": True,
                        "answer": "A superfície deve ser mantida úmida por no mínimo 7 dias.",
                        "quote": "a cura deve manter a superfície úmida por no mínimo 7 dias",
                        "source_index": 1,
                    }
                )
            ]
        )
    )

    result = await rag.answer_procedure_question(
        db=object(),
        company_id=uuid.uuid4(),
        query="Quanto tempo de cura da laje?",
        contact=None,
        user_first_name="Valdir",
    )

    assert result.had_fallback is False
    # trata pelo nome, cita a fonte com item, traz o trecho literal e o link da página
    assert result.answer.startswith("Valdir, ")
    assert "POP de Concretagem, item 4.3" in result.answer
    assert "“a cura deve manter a superfície úmida por no mínimo 7 dias”" in result.answer
    assert "#page=12" in result.answer
    source = result.sources[0]
    assert source.page_ref == 12
    assert source.quote and source.url
    assert result.chunks_used == [chunk.chunk_id]


async def test_document_request_without_match_triggers_fallback(monkeypatch):
    monkeypatch.setattr(rag, "find_administrative_document", AsyncMock(return_value=None))
    result = await rag.answer_document_request(
        db=object(),
        company_id=uuid.uuid4(),
        site_id=None,
        search_text="alvará empreendimento Alpha",
        contact="Carlos, 11977776666",
        user_first_name="Valdir",
    )
    assert result.had_fallback is True
    assert "Carlos" in result.answer


async def test_answer_question_routes_document_intent_without_calling_rag_prompt(monkeypatch):
    rag._client.messages.create = AsyncMock(
        return_value=FakeResponse([ToolUseBlock({"intent": "documento", "search_text": "alvará Alpha"})])
    )
    lookup_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(rag, "find_administrative_document", lookup_mock)
    retrieve_mock = AsyncMock()
    monkeypatch.setattr(rag, "retrieve_chunks", retrieve_mock)

    await rag.answer_question(
        db=object(), company_id=uuid.uuid4(), site_id=None, query="me manda o alvará do Alpha", contact=None
    )

    lookup_mock.assert_awaited_once()
    retrieve_mock.assert_not_called()


async def test_link_points_to_origin_when_document_lives_in_client_system(monkeypatch):
    """Documento vindo de conector (SharePoint/Drive): o link leva ao sistema do
    cliente, não a uma cópia nossa."""
    chunk = make_chunk("POP de Escavação", "Item 3.1: talude máximo de 1:1.", section_ref="3.1", page_ref=4)
    chunk.external_url = "https://persa.sharepoint.com/sites/qualidade/POP-Escavacao.pdf"
    monkeypatch.setattr(rag, "retrieve_chunks", AsyncMock(return_value=[chunk]))
    rag._client.messages.create = AsyncMock(
        return_value=FakeResponse(
            [
                ToolUseBlock(
                    {
                        "found": True,
                        "answer": "O talude máximo é 1:1.",
                        "quote": "talude máximo de 1:1",
                        "source_index": 1,
                    }
                )
            ]
        )
    )

    result = await rag.answer_procedure_question(
        db=object(), company_id=uuid.uuid4(), query="Qual talude posso deixar?", contact=None
    )

    assert result.sources[0].url == "https://persa.sharepoint.com/sites/qualidade/POP-Escavacao.pdf"
    assert "sharepoint.com" in result.answer
    assert "/documents/" not in result.answer  # não serve cópia nossa


def test_format_answer_without_name_keeps_sentence_capitalized():
    source = rag.Source(document_title="POP de Alvenaria", section_ref="2.1", quote="trecho literal")
    text = rag.format_answer("A junta deve ter 10 mm.", None, source)
    assert text.startswith("A junta deve ter 10 mm.")
    assert "📄 POP de Alvenaria, item 2.1" in text
