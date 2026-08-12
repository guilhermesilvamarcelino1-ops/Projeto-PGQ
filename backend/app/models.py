import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

EMBEDDING_DIM = 1024  # voyage-3


def uuid_pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    role: Mapped[str | None] = mapped_column(String, nullable=True)
    site_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    pin_hash: Mapped[str | None] = mapped_column(String, nullable=True)  # login do time de campo (web)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("kind in ('procedimento','administrativo')", name="documents_kind_check"),
        CheckConstraint("status in ('active','archived')", name="documents_status_check"),
        CheckConstraint(
            "source_type in ('upload','sharepoint','google_drive')", name="documents_source_type_check"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    site_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=True)
    # Documento vindo de conector pode não ter cópia local: o arquivo continua na origem.
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String, default="active")

    # Família do documento na taxonomia: é por ela que o acesso é concedido.
    document_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_types.id"), nullable=True
    )
    family: Mapped[str] = mapped_column(String, nullable=False)

    # Origem do documento. 'upload' = enviado pelo painel; os demais vêm de conector,
    # onde o arquivo permanece no sistema do cliente e só o índice é nosso.
    source_type: Mapped[str] = mapped_column(String, default="upload", nullable=False)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    external_url: Mapped[str | None] = mapped_column(String, nullable=True)
    external_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    # Repetida do documento para a busca vetorial filtrar por permissão sem join.
    family: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    page_ref: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_ref: Mapped[str | None] = mapped_column(String, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="chunks")


class DocumentType(Base):
    """Taxonomia documental da empresa (o RQ 15 dela). Fica no banco, e não no prompt,
    para que cada empresa tenha a sua, para que o modelo escolha entre linhas que
    existem em vez de recordar uma tabela, e para que 'não está mapeado' seja fato
    verificável. A retenção é regra computável — base dos alertas de vencimento."""

    __tablename__ = "document_types"
    __table_args__ = (
        CheckConstraint(
            "family in ('qualidade_gestao','projetos_obra','suprimentos','comercial_cliente','pessoas_seguranca')",
            name="document_types_family_check",
        ),
        CheckConstraint(
            "medium in ('eletronico','fisico','ambos','sistema')", name="document_types_medium_check"
        ),
        CheckConstraint(
            "retention_rule in ('permanente','ate_proxima_atualizacao','fim_de_obra','meses',"
            "'ate_validade','tempo_contratacao')",
            name="document_types_retention_rule_check",
        ),
        CheckConstraint(
            "disposal in ('arquivo_permanente','substituir','destruir','acervo_tecnico')",
            name="document_types_disposal_check",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)

    code: Mapped[str | None] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    family: Mapped[str] = mapped_column(String, nullable=False)

    medium: Mapped[str] = mapped_column(String, nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String, nullable=True)
    physical_location: Mapped[str | None] = mapped_column(String, nullable=True)
    external_system: Mapped[str | None] = mapped_column(String, nullable=True)

    recovery_key: Mapped[str | None] = mapped_column(String, nullable=True)

    retention_rule: Mapped[str] = mapped_column(String, nullable=False)
    retention_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    disposal: Mapped[str] = mapped_column(String, nullable=False)

    has_revisions: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    contains_personal_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserFamilyAccess(Base):
    """Quem pode ver cada família de documento. Ausência de linha significa SEM acesso —
    nunca o contrário. É o que impede o chat do time de campo de alcançar documento de
    RH ou de cliente (LGPD)."""

    __tablename__ = "user_family_access"
    __table_args__ = (
        CheckConstraint(
            "family in ('qualidade_gestao','projetos_obra','suprimentos','comercial_cliente','pessoas_seguranca')",
            name="user_family_access_family_check",
        ),
        UniqueConstraint("user_id", "family", name="user_family_access_user_family_uniq"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    family: Mapped[str] = mapped_column(String, nullable=False)
    can_upload: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DriveConnection(Base):
    """Autorização da empresa para o sistema gravar no drive dela. O acervo continua
    sendo do cliente — guardamos só a permissão de escrever lá."""

    __tablename__ = "drive_connections"
    __table_args__ = (
        CheckConstraint(
            "provider in ('onedrive','sharepoint','google_drive')", name="drive_connections_provider_check"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)

    account_email: Mapped[str | None] = mapped_column(String, nullable=True)
    drive_id: Mapped[str | None] = mapped_column(String, nullable=True)
    root_path: Mapped[str] = mapped_column(String, default="Procede", nullable=False)

    # Credencial de longa duração: nunca sai em resposta de API.
    refresh_token: Mapped[str] = mapped_column(String, nullable=False)
    access_token: Mapped[str | None] = mapped_column(String, nullable=True)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    connected_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PendingFiling(Base):
    """Documento classificado aguardando a confirmação de um toque. Entre o envio e a
    confirmação, o arquivo fica fora do acervo do cliente."""

    __tablename__ = "pending_filings"
    __table_args__ = (
        CheckConstraint(
            "status in ('aguardando','confirmado','recusado','expirado')", name="pending_filings_status_check"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    family: Mapped[str] = mapped_column(String, nullable=False)
    document_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_types.id"), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    proposal: Mapped[dict] = mapped_column(JSONB, nullable=False)

    staged_path: Mapped[str] = mapped_column(String, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, default="aguardando", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (CheckConstraint("channel in ('web','whatsapp')", name="conversations_channel_check"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    site_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role in ('user','assistant')", name="messages_role_check"),
        CheckConstraint("media_type in ('text','audio','image')", name="messages_media_type_check"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(String, default="text")
    media_url: Mapped[str | None] = mapped_column(String, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunks_used: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    document_returned_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    had_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
