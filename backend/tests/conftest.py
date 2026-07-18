import os
import uuid

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/procede_test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("VOYAGE_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest

from app.services.retrieval import RetrievedChunk


def make_chunk(document_title: str, content: str, section_ref: str | None = None, page_ref: int | None = None):
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        content=content,
        document_title=document_title,
        page_ref=page_ref,
        section_ref=section_ref,
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"
