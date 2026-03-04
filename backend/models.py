from sqlalchemy import Column, String, Integer, BigInteger, DateTime, ForeignKey, JSON, Time, Enum as SAEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from database import Base


class Depart(Base):
    __tablename__ = "depart_tb"

    dept_no = Column(BigInteger, primary_key=True, autoincrement=True)
    college = Column(String(50), nullable=False)
    depart = Column(String(255), nullable=False)
    office_tel = Column(String(50), nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(50), unique=True, nullable=False)  # loginid
    password_hash = Column(String(255), nullable=False)
    name = Column(String(50), nullable=False)
    major = Column(String(100), nullable=False)
    degree_level = Column(String(20))
    language = Column(String(10), default="ko")
    grade = Column(Integer, nullable=True)  # 학년 (STUDENT일 때만 유의미)
    status = Column(String(20), default="enrolled")
    role = Column(String(20), default="student")
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
    role = Column(String(10), nullable=False)  # 'user' or 'assistant'
    content = Column(String, nullable=False)
    tokens_used = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class Lecture(Base):
    __tablename__ = "lecture_tb"

    lecture_id = Column(Integer, primary_key=True, autoincrement=True)
    course_no = Column(String(20), unique=True)
    subject = Column(String(200), nullable=False)
    department = Column(String(100))
    lec_grade = Column(String(10))
    credit = Column(Integer)
    professor = Column(String(50))
    classroom = Column(String(100))
    type = Column(SAEnum('전공필수', '전공선택', '교양필수', '교양선택', name='lecture_category'))
    capacity = Column(Integer, default=0)
    count = Column(Integer, default=0)
    version = Column(Integer, default=0)

    schedules = relationship("ScheduleTb", back_populates="lecture", cascade="all, delete-orphan")
    enrollments = relationship("Enrollment", back_populates="lecture")


class ScheduleTb(Base):
    __tablename__ = "schedule_tb"

    sche_no = Column(Integer, primary_key=True, autoincrement=True)
    lecture_id = Column(Integer, ForeignKey("lecture_tb.lecture_id", ondelete="CASCADE"))
    day_of_week = Column(String(1))
    start_min = Column(Integer)
    end_min = Column(Integer)
    start_time = Column(Time)
    end_time = Column(Time)

    lecture = relationship("Lecture", back_populates="schedules")


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
    lecture_id = Column(Integer, ForeignKey("lecture_tb.lecture_id"))
    status = Column(String(20), default="cart")
    created_at = Column(DateTime, default=datetime.utcnow)

    lecture = relationship("Lecture", back_populates="enrollments")
    grade = relationship("Grade", back_populates="enrollment", uselist=False)


class Grade(Base):
    __tablename__ = "grades"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    enrollment_id = Column(String, ForeignKey("enrollments.id"), unique=True)
    user_id = Column(String, ForeignKey("users.id"))
    score = Column(Integer)  # 0-100
    grade_letter = Column(String(5))  # A+, B0, etc.
    created_at = Column(DateTime, default=datetime.utcnow)

    enrollment = relationship("Enrollment", back_populates="grade")


class Notice(Base):
    __tablename__ = "notices"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    content = Column(String, nullable=False)
    author_id = Column(String, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)


class SystemConfig(Base):
    __tablename__ = "system_configs"

    key = Column(String(100), primary_key=True)
    value = Column(String(255), nullable=False)

