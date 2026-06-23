import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
from sqlalchemy.sql import text

class RawMessage(Base):
    __tablename__ = "raw_messages"
    __table_args__ = (
        Index("ix_raw_messages_group_id", "group_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    group_id = Column(String, nullable=False)
    user_name = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    is_processed = Column(Boolean, default=False, nullable=False)

class ExtractedUrl(Base):
    __tablename__ = "extracted_urls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    group_id = Column(String, nullable=False)
    url = Column(String, nullable=False)
    raw_content = Column(Text, nullable=False)
    is_processed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
