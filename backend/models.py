from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(20), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(50), nullable=False)
    major = Column(String(100), nullable=False)
    degree_level = Column(String(20))
    language = Column(String(10), default="ko")
    status = Column(String(20), default="enrolled")
    created_at = Column(DateTime, default=datetime.utcnow)

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    title = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("ChatMessage", backref="session")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("chat_sessions.id"))
    role = Column(String(10), nullable=False) # 'user' or 'assistant'
    content = Column(String, nullable=False)
    tokens_used = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(String)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    schedule_type = Column(String(50))

class Form(Base):
    __tablename__ = "forms"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    form_type = Column(String(50), nullable=False)
    form_data = Column(JSON, nullable=False)
    status = Column(String(20), default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)

class DocumentMetadata(Base):
    __tablename__ = "document_metadata"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    source_url = Column(String(500))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Enrollment(Base):
    __tablename__ = "enrollments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    subject = Column(String(255), nullable=False)
    college = Column(String(100))
    department = Column(String(100))
    room = Column(String(100))
    status = Column(String(20), default="cart")
    credits = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 성적과의 관계
    grade = relationship("Grade", back_populates="enrollment", uselist=False)

class Grade(Base):
    __tablename__ = "grades"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    enrollment_id = Column(String, ForeignKey("enrollments.id"), unique=True)
    user_id = Column(String, ForeignKey("users.id"))
    score = Column(Integer) # 0-100
    grade_letter = Column(String(5)) # A+, B0, etc.
    created_at = Column(DateTime, default=datetime.utcnow)

    enrollment = relationship("Enrollment", back_populates="grade")

class Notice(Base):
    __tablename__ = "notices"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    content = Column(String, nullable=False)
    author_id = Column(String, ForeignKey("users.id")) # 관리자 ID
    created_at = Column(DateTime, default=datetime.utcnow)

class SystemConfig(Base):
    __tablename__ = "system_configs"

    key = Column(String(100), primary_key=True)
    value = Column(String(255), nullable=False)

