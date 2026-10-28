"""Relational schema. Portable across SQLite (laptop default) and PostgreSQL (server deployments)."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    display_name: Mapped[str] = mapped_column(String(120), default="")
    role: Mapped[str] = mapped_column(String(20), default="user")  # user | admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # sha256 of the cookie value
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Case(Base):
    """A user's private workspace grouping conversations, documents and drafts."""
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    narrative: Mapped[str] = mapped_column(Text, default="")
    state: Mapped[str] = mapped_column(String(80), default="")
    incident_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    facts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), default="New question")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    messages: Mapped[list["Message"]] = relationship(cascade="all, delete-orphan", order_by="Message.id")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(12))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # structured response, citations, timings
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LegalSource(Base):
    """One legal document (an Act, rule, notification or judgment) with provenance."""
    __tablename__ = "legal_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    doc_type: Mapped[str] = mapped_column(String(24), index=True)  # statute | rule | notification | judgment | synthetic
    title: Mapped[str] = mapped_column(String(500))
    identifier: Mapped[str] = mapped_column(String(200), default="")  # e.g. "Act 45 of 2023" or "2023 INSC 600"
    authority: Mapped[str] = mapped_column(String(200), default="")
    jurisdiction: Mapped[str] = mapped_column(String(100), default="India")
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="in_force")  # in_force | repealed | superseded | unknown
    status_note: Mapped[str] = mapped_column(Text, default="")  # only verified amendment/repeal information
    version: Mapped[str] = mapped_column(String(64), default="1")
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    is_synthetic: Mapped[bool] = mapped_column(default=False)  # test fixtures are never shown as real law
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    chunks: Mapped[list["LegalChunk"]] = relationship(cascade="all, delete-orphan", order_by="LegalChunk.ordinal")
    __table_args__ = (UniqueConstraint("identifier", "version", "doc_type", name="uq_source_version"),)


class LegalChunk(Base):
    __tablename__ = "legal_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("legal_sources.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    ref_label: Mapped[str] = mapped_column(String(200), default="")  # "Section 318" / "Paragraph 12"
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    embeddings: Mapped[list["ChunkEmbedding"]] = relationship(cascade="all, delete-orphan")


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"
    id: Mapped[int] = mapped_column(primary_key=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("legal_chunks.id", ondelete="CASCADE"), index=True)
    model_key: Mapped[str] = mapped_column(String(40))
    model_revision: Mapped[str] = mapped_column(String(64))
    dim: Mapped[int] = mapped_column(Integer)
    vector: Mapped[bytes] = mapped_column(LargeBinary)  # float32, L2-normalised
    __table_args__ = (UniqueConstraint("chunk_id", "model_key", name="uq_chunk_model"), Index("ix_emb_model", "model_key"))


class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), nullable=True)
    original_name: Mapped[str] = mapped_column(String(300))
    mime: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_name: Mapped[str] = mapped_column(String(80))  # random name on disk; never the user's filename
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued | processing | done | failed
    error: Mapped[str] = mapped_column(Text, default="")
    pages: Mapped[list[Any]] = mapped_column(JSON, default=list)  # [{"page":1,"text":"...","method":"text|ocr"}]
    analysis: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Draft(Base):
    __tablename__ = "drafts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), nullable=True)
    template_id: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200))
    facts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    content: Mapped[str] = mapped_column(Text, default="")
    authorities: Mapped[list[Any]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    revisions: Mapped[list["DraftRevision"]] = relationship(cascade="all, delete-orphan", order_by="DraftRevision.id")


class DraftRevision(Base):
    __tablename__ = "draft_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("drafts.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    """Security-relevant events. Never stores document contents or message text."""
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
