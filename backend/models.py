from sqlalchemy import Column, String, Integer, BigInteger, DateTime, Date, ForeignKey, JSON, Time, Enum as SAEnum, Boolean
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
    __tablename__ = "user_tb"

    user_no = Column(BigInteger, primary_key=True, autoincrement=True)
    loginid = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(SAEnum('STUDENT', 'STAFF', name='role_enum'), nullable=False)
    user_name = Column(String(50), nullable=False, index=True)
    grade = Column(Integer, nullable=True)
    dept_no = Column(BigInteger, ForeignKey("depart_tb.dept_no", ondelete="SET NULL"), nullable=True)
    user_status = Column(SAEnum('재학', '휴학', '재직', '퇴직', name='status_enum'), nullable=False)
    birth_date = Column(Date, nullable=True)
    email = Column(String(150), unique=True, nullable=True)
    phone = Column(String(20), nullable=True)
    is_first_login = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    depart = relationship("Depart")





class Lecture(Base):
    __tablename__ = "lecture_tb"

    lecture_id = Column(Integer, primary_key=True, autoincrement=True)
    course_no = Column(String(20), unique=True)
    subject = Column(String(200), nullable=False)
    department = Column(String(100), index=True)
    dept_no = Column(BigInteger, ForeignKey("depart_tb.dept_no"), nullable=True)
    lec_grade = Column(String(10), index=True)
    credit = Column(Integer)
    professor = Column(String(50))
    type = Column(SAEnum('전공필수', '전공선택', '교양필수', '교양선택', '교직', '공통', name='lecture_category'), index=True)
    capacity = Column(Integer, default=0)
    count = Column(Integer, default=0)
    waitlist_capacity = Column(Integer, default=10) # 큐 정원
    version = Column(Integer, default=0)

    depart = relationship("Depart")
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
    classroom = Column(String(50))

    lecture = relationship("Lecture", back_populates="schedules")





class Enrollment(Base):
    __tablename__ = "enroll_tb"

    id = Column("enroll_no", BigInteger, primary_key=True, autoincrement=True)
    user_id = Column("loginid", BigInteger, ForeignKey("user_tb.user_no"))
    lecture_id = Column(BigInteger, ForeignKey("lecture_tb.lecture_id"))
    sche_no = Column(BigInteger, nullable=True)
    enroll_status = Column(SAEnum('COMPLETED', 'CANCELED', 'BASKET', name='enroll_status_enum'), nullable=True)
    status = Column(String(20), default="cart")
    created_at = Column("createdat", DateTime, default=datetime.utcnow)

    lecture = relationship("Lecture", back_populates="enrollments")
    user = relationship("User", foreign_keys=[user_id])


class Notice(Base):
    __tablename__ = "notice_tb"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    content = Column(String, nullable=False)
    author_id = Column(BigInteger, ForeignKey("user_tb.user_no"))
    created_at = Column(DateTime, default=datetime.utcnow)


class Waitlist(Base):
    """수강신청 대기열 (FIFO) 테이블"""
    __tablename__ = "waitlist_tb"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    lecture_id = Column(Integer, ForeignKey("lecture_tb.lecture_id", ondelete="CASCADE"), index=True)
    user_id = Column(BigInteger, ForeignKey("user_tb.user_no", ondelete="CASCADE"), index=True)
    status = Column(String(20), default="WAITING") # WAITING, PROMOTED, CANCELED
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    lecture = relationship("Lecture")


class Notification(Base):
    """사용자 인앱 알림 테이블"""
    __tablename__ = "notification_tb"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(BigInteger, ForeignKey("user_tb.user_no", ondelete="CASCADE"), index=True)
    message = Column(String(255), nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class SystemConfig(Base):
    __tablename__ = "system_config_tb"

    key = Column(String(100), primary_key=True)
    value = Column(String(255), nullable=False)


class EnrollmentSchedule(Base):
    """수강신청 일차별 기간 및 제한 설정"""
    __tablename__ = "enroll_schedule_tb"

    id = Column(Integer, primary_key=True, autoincrement=True)
    day_number = Column(Integer, nullable=False)          # 1, 2, 3
    open_datetime = Column(DateTime, nullable=False)      # 오픈 일시 (UTC)
    close_datetime = Column(DateTime, nullable=False)     # 마감 일시 (UTC)
    restriction_type = Column(String(30), nullable=False) # 'own_grade_dept' | 'own_college' | 'all'
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

