import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    category: str
    kind: Literal["procedimento", "administrativo"]
    site_id: uuid.UUID | None
    version: int
    status: Literal["active", "archived"]
    uploaded_at: datetime
    source_type: Literal["upload", "sharepoint", "google_drive"] = "upload"
    external_url: str | None = None
    last_synced_at: datetime | None = None


class DocumentUploadResponse(BaseModel):
    document: DocumentOut
    chunks_created: int


class SourceRef(BaseModel):
    document_title: str
    document_id: uuid.UUID | None = None
    section_ref: str | None = None
    page_ref: int | None = None
    quote: str | None = None
    url: str | None = None


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    answer: str
    had_fallback: bool
    sources: list[SourceRef] = []
    document_file_path: str | None = None


class QuestionLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content: str
    had_fallback: bool
    created_at: datetime


class LoginRequest(BaseModel):
    email: str
    password: str


class FieldLoginRequest(BaseModel):
    phone_number: str
    pin: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
