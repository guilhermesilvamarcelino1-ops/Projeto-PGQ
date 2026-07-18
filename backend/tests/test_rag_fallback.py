"""The RAG fallback is the most safety-critical behavior in the product: the assistant
must never answer from general knowledge, and must say so explicitly when the retrieved
material doesn't cover the question. These tests exercise that boundary directly against
`answer_procedure_question` / `answer_document_request`, mocking the LLM and DB lookups.
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
    # Any test that forgets to mock the client should fail loudly instead of hitting the network.
    monkeypatch.setattr(rag, "_client", AsyncMock())


async def test_no_chunks_retrieved_triggers_fallback(monkeypatch):
    monkeypatch.setattr(rag, "retrieve_chunks", AsyncMock(return_value=[]))
    result = await rag.answer_procedure_question(
        db=object(), company_id=uuid.uuid4(), query="Qual o prazo de garantia da impermeabilização?", contact="João, 11999990000"
    )
    assert result.had_fallback is True
    assert "João" in result.answer
    rag._client.messages.create.assert_not_called()


async def test_model_reports_not_found_triggers_fallback(monkeypatch):
    chunks = [make_chunk("POP de Concretagem", "Item 4.2: o traço deve seguir o memorial estrutural.")]
    monkeypatch.setattr(rag, "retrieve_chunks", AsyncMock(return_value=chunks))
    rag._client.messages.create = AsyncMock(
        return_value=FakeResponse([ToolUseBlock({"found": False, "answer": "não encontrado", "citations": []})])
    )

    result = await rag.answer_procedure_question(
        db=object(), company_id=uuid.uuid4(), query="Qual a cor da tinta usada na fachada?", contact="Maria, 11988887777"
    )

    assert result.had_fallback is True
    assert "Maria" in result.answer
    assert result.chunks_used == []


async def test_model_finds_answer_returns_citations_and_no_fallback(monkeypatch):
    chunk = make_chunk("POP de Concretagem", "Item 4.2: o traço deve seguir o memorial estrutural.", section_ref="4.2")
    monkeypatch.setattr(rag, "retrieve_chunks", AsyncMock(return_value=[chunk]))
    rag._client.messages.create = AsyncMock(
        return_value=FakeResponse(
            [
                ToolUseBlock(
                    {
                        "found": True,
                        "answer": "Segundo o POP de Concretagem, item 4.2, o traço deve seguir o memorial estrutural.",
                        "citations": [{"document_title": "POP de Concretagem", "section_ref": "4.2"}],
                    }
                )
            ]
        )
    )

    result = await rag.answer_procedure_question(
        db=object(), company_id=uuid.uuid4(), query="Qual traço de concreto usar na fundação?", contact=None
    )

    assert result.had_fallback is False
    assert result.chunks_used == [chunk.chunk_id]
    assert result.sources[0]["document_title"] == "POP de Concretagem"


async def test_document_request_without_match_triggers_fallback(monkeypatch):
    monkeypatch.setattr(rag, "find_administrative_document", AsyncMock(return_value=None))
    result = await rag.answer_document_request(
        db=object(),
        company_id=uuid.uuid4(),
        site_id=None,
        search_text="alvará empreendimento Alpha",
        contact="Carlos, 11977776666",
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
