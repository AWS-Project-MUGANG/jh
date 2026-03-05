import logging
import os
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, BigInteger
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.types import Enum as SAEnum
from sqlalchemy.pool import StaticPool
import uuid
import csv
import io
import pdfplumber
import re
import tempfile

# DB 연동
from database import engine, get_db, Base
import models

# ---- 인증 처리용 설정 (비밀번호 암호화 & JWT) ----
import bcrypt

SECRET_KEY = "mugang_super_secret_key"
ALGORITHM = "HS256"

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 시작 시 DB 테이블 자동 생성 (개발용)
models.Base.metadata.create_all(bind=engine)

# FastAPI 앱 생성
app = FastAPI(
    title="무강대학교 AI 학사행정 서비스",
    description="학생 맞춤형 학사 서비스 (수강신청, 시간표, RAG 기반 질의응답)",
    version="1.0.0"
)

# CORS 미들웨어
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

# ---- API 요청/응답 데이터 모델 (Pydantic) ----
class FirstSetupRequest(BaseModel):
    student_id: str
    token: str
    new_password: str
    email: str
    phone: str

class FindIdRequest(BaseModel):
    name: str
    email: str

class FindPwRequest(BaseModel):
    student_id: str
    email: str

class LoginRequest(BaseModel):
    student_id: str
    password: str

class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    message: str

class FormRequest(BaseModel):
    form_type: str
    reason: str

class FormStatusRequest(BaseModel):
    status: str

class RAGUploadRequest(BaseModel):
    title: str
    content: str

class NoticeRequest(BaseModel):
    title: str
    content: str

class GradeRequest(BaseModel):
    enrollment_id: str
    user_id: str
    score: int
    grade_letter: str

class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    major: Optional[str] = None
    status: Optional[str] = None

class EnrollmentPeriodRequest(BaseModel):
    start_time: str  # ISO Format
    end_time: str    # ISO Format

class EnrollmentRequest(BaseModel):
    user_id: str
    lecture_id: int  # lecture_tb.lecture_id 참조

class EnrollmentScheduleDayRequest(BaseModel):
    day_number: int
    open_datetime: str   # UTC ISO string
    close_datetime: str  # UTC ISO string
    restriction_type: str  # 'own_grade_dept' | 'own_college' | 'all'
    is_active: bool = True

class EnrollmentScheduleBulkRequest(BaseModel):
    schedules: List[EnrollmentScheduleDayRequest]

# ---- 헬퍼 함수 ----
def is_enrollment_period_active(db: Session):
    """현재 시각이 수강신청 가능 기간인지 확인 (구 SystemConfig 방식)"""
    start_config = db.query(models.SystemConfig).filter(models.SystemConfig.key == "enrollment_start").first()
    end_config = db.query(models.SystemConfig).filter(models.SystemConfig.key == "enrollment_end").first()

    if not start_config or not end_config:
        return True  # 설정이 없으면 기본적으로 허용 (테스트 편의성)

    try:
        now = datetime.now(timezone.utc)
        start = datetime.fromisoformat(start_config.value.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_config.value.replace("Z", "+00:00"))
        return start <= now <= end
    except Exception as e:
        print(f"Period check error: {e}")
        return True


def _get_active_schedule(db: Session):
    """현재 시각에 해당하는 EnrollmentSchedule 반환 (없으면 None)"""
    now = datetime.utcnow()
    schedules = db.query(models.EnrollmentSchedule).filter(
        models.EnrollmentSchedule.is_active == True
    ).order_by(models.EnrollmentSchedule.day_number).all()
    for s in schedules:
        if s.open_datetime <= now <= s.close_datetime:
            return s
    return None


def _check_enrollment_access(user: models.User, lecture_id: int, db: Session) -> dict:
    """학생이 해당 강의를 신청할 수 있는지 일정·제한 검사"""
    if user.role == 'STAFF':
        return {"allowed": True, "reason": "관리자 계정", "active_day": None}

    schedules_exist = db.query(models.EnrollmentSchedule).filter(
        models.EnrollmentSchedule.is_active == True
    ).first()

    if not schedules_exist:
        # 새 스케줄 미설정 시 기존 SystemConfig 방식 사용
        if not is_enrollment_period_active(db):
            return {"allowed": False, "reason": "현재는 수강신청 기간이 아닙니다."}
        return {"allowed": True, "reason": "기간 내", "active_day": None}

    active = _get_active_schedule(db)
    if not active:
        return {"allowed": False, "reason": "현재 수강신청 기간이 아닙니다.", "active_day": None}

    if active.restriction_type == 'all':
        return {"allowed": True, "reason": "전체 수강신청 기간", "active_day": active.day_number}

    lecture = db.query(models.Lecture).filter(models.Lecture.lecture_id == lecture_id).first()
    if not lecture:
        return {"allowed": False, "reason": "강의 정보를 찾을 수 없습니다."}

    # 단과대학 조회 (user_tb에 major 없으므로 학년만 체크)
    if active.restriction_type == 'own_college':
        return {"allowed": True, "reason": "단과대학 제한 (학과정보 없음, 허용)", "active_day": active.day_number}

    if active.restriction_type == 'own_grade_dept':
        if lecture.lec_grade and user.grade and str(user.grade) != str(lecture.lec_grade):
            return {"allowed": False,
                    "reason": f"1일차는 본인 학년({user.grade}학년) 강의만 신청 가능합니다.",
                    "active_day": active.day_number}
        return {"allowed": True, "reason": "학년 일치", "active_day": active.day_number}

    return {"allowed": True, "reason": "허용", "active_day": active.day_number}


# ---- API 라우터 ----

@app.get("/api/health")
def api_status():
    return {"message": "무강대학교 AI 학사행정 API 서버가 정상 실행 중입니다."}

@app.get("/")
def read_root():
    return RedirectResponse(url="/static/pages/auth/login.html")


# --- 인증 ---
# 기존 학생 자율 회원가입 제거: 관리자가 1234 초기비번으로 일괄등록 한다고 가정합니다.

@app.post("/api/v1/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """학번/사번과 비밀번호로 로그인 (JWT 발급)"""
    logger.info(f"로그인 시도: {req.student_id}")

    user = db.query(models.User).filter(models.User.loginid == req.student_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="존재하지 않는 학번/사번입니다.")
    if not verify_password(req.password, user.password):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")

    # 초기 접속(비밀번호가 1234일 때 등)인 경우
    if user.is_first_login:
        # 제한된 짧은 수명의 토큰 발급 (필수 정보 수정용)
        update_token = create_access_token(data={"sub": user.loginid, "type": "first_setup"})
        return {
            "require_setup": True,
            "setup_token": update_token,
            "message": "초기 비밀번호를 변경하고 개인정보(이메일, 연락처)를 등록해야 합니다."
        }

    access_token = create_access_token(data={"sub": user.loginid, "id": user.user_no})

    return {
        "require_setup": False,
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.user_no,
        "name": user.user_name,
        "role": user.role
    }

@app.post("/api/v1/auth/first-setup")
def first_setup(req: FirstSetupRequest, db: Session = Depends(get_db)):
    """초기 로그인 시 비밀번호와 이메일/전락처 수정 처리"""
    try:
        payload = jwt.decode(req.token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "first_setup" or payload.get("sub") != req.student_id:
            raise HTTPException(status_code=401, detail="유효하지 않은 설정 토큰입니다.")
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않거나 만료된 설정 토큰입니다.")

    user = db.query(models.User).filter(models.User.loginid == req.student_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")

    # 중복 이메일 기입 차단
    existing_email = db.query(models.User).filter(models.User.email == req.email, models.User.user_no != user.user_no).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다.")

    user.password = get_password_hash(req.new_password)
    user.email = req.email
    user.phone = req.phone
    user.is_first_login = False
    
    db.commit()
    return {"message": "초기 설정이 완료되었습니다. 새로운 비밀번호로 로그인해주세요."}


@app.post("/api/v1/auth/find-id")
def find_id(req: FindIdRequest, db: Session = Depends(get_db)):
    """이름과 이메일로 학번(ID) 찾기 (마스킹 처리)"""
    user = db.query(models.User).filter(
        models.User.user_name == req.name,
        models.User.email == req.email
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="일치하는 가입 정보가 없습니다.")
    
    # 학번 마스킹 예: 2023***12
    id_str = user.loginid
    if len(id_str) > 4:
        masked_id = id_str[:4] + "*" * (len(id_str) - 6) + id_str[-2:]
    else:
        masked_id = id_str
        
    return {"message": "학번 조회가 완료되었습니다.", "student_id": masked_id}


@app.post("/api/v1/auth/find-pw")
def find_pw(req: FindPwRequest, db: Session = Depends(get_db)):
    """학번과 이메일로 임시 비밀번호 발급"""
    user = db.query(models.User).filter(
        models.User.loginid == req.student_id,
        models.User.email == req.email
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="일치하는 가입 정보가 없습니다.")
    
    # 임시 비밀번호 발급
    temp_pw = "temp1234!"
    user.password = get_password_hash(temp_pw)
    user.is_first_login = True  # 재설정 시 접속하면 강제로 또 비번 바꾸도록 함.
    db.commit()
    
    return {
        "message": "임시 비밀번호가 발급되었습니다. (실제 환경에서는 이메일로 전송됩니다.)", 
        "temp_password": temp_pw
    }



# ---- 이하 생략: 수강신청 관련 엔드포인트 진행 ----


# --- 강의 (lecture_tb) ---
@app.get("/api/v1/lectures")
def get_lectures(db: Session = Depends(get_db)):
    """강의 목록 전체 조회 (수강신청 화면용) - schedule_tb 조인"""
    lectures = db.query(models.Lecture).all()
    result = []
    for lec in lectures:
        schedules = [
            {
                "day_of_week": s.day_of_week,
                "start_time": str(s.start_time) if s.start_time else None,
                "end_time": str(s.end_time) if s.end_time else None,
            }
            for s in lec.schedules
        ]
        result.append({
            "lecture_id": lec.lecture_id,
            "course_no": lec.course_no,
            "subject": lec.subject,
            "department": lec.department,
            "lec_grade": lec.lec_grade,
            "credit": lec.credit,
            "professor": lec.professor,
            "classroom": lec.classroom,
            "type": lec.type,
            "capacity": lec.capacity,
            "count": lec.count,
            "schedules": schedules,
        })
    return {"lectures": result}



# --- 수강신청 (enrollments) ---

@app.get("/api/v1/enrollments/{user_id}")
def get_user_enrollments(user_id: str, db: Session = Depends(get_db)):
    """사용자의 수강신청 내역 조회 (lecture_tb 조인)"""
    enrollments = db.query(models.Enrollment).filter(models.Enrollment.user_id == user_id).all()
    result = []
    for en in enrollments:
        lec = en.lecture
        result.append({
            "id": en.id,
            "lecture_id": en.lecture_id,
            "subject": lec.subject if lec else None,
            "department": lec.department if lec else None,
            "classroom": lec.classroom if lec else None,
            "professor": lec.professor if lec else None,
            "type": lec.type if lec else None,
            "credits": lec.credit if lec else None,
            "status": en.status,
            "created_at": en.created_at.isoformat()
        })
    return {"schedules": result}


@app.post("/api/v1/enrollments")
def create_enrollment(req: EnrollmentRequest, db: Session = Depends(get_db)):
    """수강신청 1건 저장 (정원 체크 + 대기열 편입 + 낙관적 락)"""
    if not is_enrollment_period_active(db):
        raise HTTPException(status_code=403, detail="현재는 수강신청 기간이 아닙니다.")

    user = db.query(models.User).filter(models.User.user_no == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")

    access = _check_enrollment_access(user, req.lecture_id, db)
    if not access["allowed"]:
        raise HTTPException(status_code=403, detail=access["reason"])

    # 중복 수강/대기인지 검사
    existing_enrollment = db.query(models.Enrollment).filter(
        models.Enrollment.user_id == req.user_id,
        models.Enrollment.lecture_id == req.lecture_id
    ).first()
    if existing_enrollment:
        raise HTTPException(status_code=400, detail="이미 신청(수강/장바구니)이 완료된 과목입니다.")
        
    existing_waitlist = db.query(models.Waitlist).filter(
        models.Waitlist.user_id == req.user_id,
        models.Waitlist.lecture_id == req.lecture_id,
        models.Waitlist.status == "WAITING"
    ).first()
    if existing_waitlist:
        raise HTTPException(status_code=400, detail="이미 대기열에 등록된 과목입니다.")

    lecture = db.query(models.Lecture).filter(models.Lecture.lecture_id == req.lecture_id).first()
    if not lecture:
        raise HTTPException(status_code=404, detail="강의 정보를 찾을 수 없습니다.")

    # 1. 정원이 꽉 찼는지 확인
    if lecture.capacity > 0 and lecture.count >= lecture.capacity:
        # 1-1. 대기열 정원 체크
        current_waitlist_count = db.query(models.Waitlist).filter(
            models.Waitlist.lecture_id == req.lecture_id,
            models.Waitlist.status == "WAITING"
        ).count()
        
        if current_waitlist_count >= lecture.waitlist_capacity:
            raise HTTPException(status_code=409, detail="수강 정원 및 대기열 정원이 모두 초과되었습니다.")
            
        # 1-2. 대기열 등록 (Insert Waitlist)
        new_waitlist = models.Waitlist(
            lecture_id=req.lecture_id,
            user_id=req.user_id,
            status="WAITING"
        )
        db.add(new_waitlist)
        db.commit()
        
        # 내 순번 도출
        my_order = db.query(models.Waitlist).filter(
            models.Waitlist.lecture_id == req.lecture_id,
            models.Waitlist.status == "WAITING",
            models.Waitlist.created_at <= new_waitlist.created_at
        ).count()
        
        return {
            "message": f"수강 정원이 초과되어 대기열에 등록되었습니다. (나의 대기: {my_order}번)", 
            "status": "waitlisted",
            "waitlist_order": my_order
        }

    # 2. 정원 여유 시 낙관적 락으로 수강신청 저장
    original_version = lecture.version
    updated_rows = db.query(models.Lecture).filter(
        models.Lecture.lecture_id == req.lecture_id,
        models.Lecture.version == original_version
    ).update({"count": models.Lecture.count + 1, "version": original_version + 1})

    if updated_rows == 0:
        db.rollback()
        raise HTTPException(status_code=409, detail="수강신청 중 충돌이 발생했습니다. 다시 시도해주세요.")

    new_enrollment = models.Enrollment(
        user_id=req.user_id,
        lecture_id=req.lecture_id,
        status="enrolled"
    )
    db.add(new_enrollment)
    db.commit()
    db.refresh(new_enrollment)
    return {"message": "수강신청이 성공적으로 확정되었습니다.", "enrollment_id": new_enrollment.id, "status": "enrolled"}


@app.put("/api/v1/enrollments/{enrollment_id}/confirm")
def confirm_enrollment(enrollment_id: str, db: Session = Depends(get_db)):
    """수강 장바구니 → 최종 신청 확정"""
    if not is_enrollment_period_active(db):
        raise HTTPException(status_code=403, detail="현재는 수강신청 기간이 아닙니다.")

    en = db.query(models.Enrollment).filter(models.Enrollment.id == enrollment_id).first()
    if not en:
        raise HTTPException(status_code=404, detail="해당 수강 내역이 없습니다.")
    en.status = "enrolled"
    db.commit()
    return {"message": "최종 수강신청이 확정되었습니다."}


@app.delete("/api/v1/enrollments/{enrollment_id}")
def drop_enrollment(enrollment_id: str, db: Session = Depends(get_db)):
    """수강 철회 및 대기열 승급(Promotion) 로직 (트랜잭션 롤백 포함)"""
    en = db.query(models.Enrollment).filter(models.Enrollment.id == enrollment_id).first()
    if not en:
        raise HTTPException(status_code=404, detail="해당 수강 내역이 없습니다.")
        
    lecture_id = en.lecture_id
    lecture = db.query(models.Lecture).filter(models.Lecture.lecture_id == lecture_id).first()
    
    # 1. 수강 내역 삭제
    db.delete(en)
    
    # 2. 대기열 승급 로직 적용
    promoted_waitlist = db.query(models.Waitlist).filter(
        models.Waitlist.lecture_id == lecture_id,
        models.Waitlist.status == "WAITING"
    ).order_by(models.Waitlist.created_at.asc()).first()
    
    if promoted_waitlist:
        # 대기자를 승급시키므로 lecture count는 줄이지 않고 그대로 유지
        promoted_waitlist.status = "PROMOTED"
        
        new_en = models.Enrollment(
            user_id=promoted_waitlist.user_id,
            lecture_id=lecture_id,
            status="enrolled"
        )
        db.add(new_en)
        
        # 알림(Notification) 생성
        noti = models.Notification(
            user_id=promoted_waitlist.user_id,
            message=f"[{lecture.subject}] 과목의 대기열 순서가 도래하여 수강신청이 확정되었습니다!"
        )
        db.add(noti)
    else:
        # 대기자가 없으면 lecture count만 감소 (낙관적 락으로 꼬이지 않게 보호)
        original_version = lecture.version
        updated_rows = db.query(models.Lecture).filter(
            models.Lecture.lecture_id == lecture_id,
            models.Lecture.version == original_version
        ).update({"count": models.Lecture.count - 1, "version": original_version + 1})
        
        if updated_rows == 0:
            db.rollback()
            raise HTTPException(status_code=409, detail="처리 중 충돌이 발생했습니다.")

    db.commit()
    return {"message": "정상적으로 수강을 철회했습니다."}


# --- 학생 통계 ---
@app.get("/api/v1/student/{user_id}/stats")
def get_student_stats(user_id: str, db: Session = Depends(get_db)):
    """학생용: 이수 학점 및 성적 조회"""
    enrollments = db.query(models.Enrollment).filter(
        models.Enrollment.user_id == user_id,
        models.Enrollment.status == "enrolled"
    ).all()

    current_credits = sum(en.lecture.credit for en in enrollments if en.lecture and en.lecture.credit)

    grades = db.query(models.Grade).filter(models.Grade.user_id == user_id).all()

    grade_points = {"A+": 4.5, "A0": 4.0, "B+": 3.5, "B0": 3.0, "C+": 2.5, "C0": 2.0, "D+": 1.5, "D0": 1.0, "F": 0.0}

    total_point_sum = 0
    total_credit_sum = 0
    for g in grades:
        en = db.query(models.Enrollment).filter(models.Enrollment.id == g.enrollment_id).first()
        if en and en.lecture and g.grade_letter in grade_points:
            total_point_sum += grade_points[g.grade_letter] * en.lecture.credit
            total_credit_sum += en.lecture.credit

    gpa = round(total_point_sum / total_credit_sum, 2) if total_credit_sum > 0 else 0.0

    return {
        "total_credits": total_credit_sum + 85,  # 기존 이수 학점 85 가정
        "grad_req_credits": 130,
        "gpa": gpa,
        "current_semester_credits": current_credits
    }


# --- 관리자: 수강 현황 및 대시보드 ---
@app.get("/api/v1/admin/enrollments")
def get_admin_enrollments(
    college: Optional[str] = None,
    grade: Optional[str] = None,
    lecture_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """관리자용: 개설 과목별 수강생 전체 현황 (필터링 추가)"""
    query = db.query(models.Enrollment)
    
    # 조인을 활용한 동적 필터링 처리 (예시 수준)
    if lecture_id:
        query = query.filter(models.Enrollment.lecture_id == lecture_id)
        
    enrollments = query.all()
    summary = {}
    for en in enrollments:
        lec = en.lecture
        # 필터링 적용 여부 체크 로직 등 보완 가능
        if college and lec and lec.department != college:
            continue
            
        subject_key = lec.subject if lec else "Unknown"
        if subject_key not in summary:
            summary[subject_key] = {
                "lecture_id": en.lecture_id,
                "subject": subject_key,
                "capacity": lec.capacity if lec else 0,
                "count": lec.count if lec else 0,
                "students": []
            }
        user = db.query(models.User).filter(models.User.user_no == en.user_id).first()
        summary[subject_key]["students"].append({
            "enrollment_id": en.id,
            "user_id": en.user_id,
            "student_id": user.loginid if user else "Unknown",
            "name": user.user_name if user else "Unknown"
        })
    return {"classes": list(summary.values())}


@app.get("/api/v1/admin/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    """관리자용: 대시보드 통계 데이터"""
    student_count = db.query(models.User).filter(models.User.role == "STUDENT").count()
    enrollment_count = db.query(models.Enrollment).count()
    waitlist_count = db.query(models.Waitlist).count()

    return {
        "total_students": student_count,
        "total_enrollments": enrollment_count,
        "total_waitlists": waitlist_count
    }


@app.post("/api/v1/admin/courses/batch")
async def upload_courses_batch(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """CSV 파일을 통한 다중 교과목 일괄 생성 API (1,000건 Bulk Insert)"""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV 파일만 업로드 가능합니다.")
        
    content = await file.read()
    stringio = io.StringIO(content.decode("utf-8"))
    reader = csv.DictReader(stringio)
    
    lectures_to_insert = []
    # CSV 헤더 예시: subject, department, classroom, professor, type, credit, capacity, waitlist_capacity
    for row in reader:
        lectures_to_insert.append(
            models.Lecture(
                subject=row.get("subject"),
                department=row.get("department"),
                classroom=row.get("classroom"),
                professor=row.get("professor"),
                type=row.get("type"),
                credit=int(row.get("credit", 3)),
                capacity=int(row.get("capacity", 40)),
                waitlist_capacity=int(row.get("waitlist_capacity", 10))
            )
        )
        
    # 메모리에 모아둔 데이터를 한 번에 밀어넣음
    db.add_all(lectures_to_insert)
    db.commit()
    
    return {"message": f"성공적으로 {len(lectures_to_insert)}개의 강의가 일괄 개설되었습니다."}

@app.post("/api/v1/admin/courses/upload-pdf")
async def upload_courses_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """PDF 강의계획서 자동 파싱 및 DB 적재 API (pdfplumber)"""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")
        
    # 임시 파일 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
        
    def to_mins(t_str):
        h, m = map(int, t_str.split(':'))
        return h * 60 + m

    time_re = re.compile(r'([월화수목금토])\((\d{2}:\d{2})-(\d{2}:\d{2})\)')
    
    try:
        # PDF 파싱 (changepdftocsv.py 원본 로직 이식)
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if not table: continue
                
                for row in table[1:]:
                    try:
                        c_no = row[3].strip()
                        raw_time = row[8] if row[8] else ""
                        
                        # 중복 여부 체크 (동일 학수번호)
                        existing_lecture = db.query(models.Lecture).filter(models.Lecture.course_no == c_no).first()
                        if existing_lecture:
                            continue
                        
                        # lecture_tb 데이터 생성
                        lecture = models.Lecture(
                            course_no=c_no,
                            subject=row[4].replace('\n', ''),
                            department=row[2].replace('\n', ''),
                            lec_grade=row[1],
                            credit=int(row[5]) if row[5].isdigit() else 3,
                            professor=row[7].replace('\n', '') if row[7] else "미지정",
                            classroom=row[9].replace('\n', '') if row[9] else "미지정",
                            type=row[0][:2],
                            capacity=40,
                            version=0
                        )
                        db.add(lecture)
                        db.flush() # ID 획득을 위해 flush
                        
                        # schedule_tb 데이터 분리 및 저장
                        matches = time_re.findall(raw_time)
                        for day, start, end in matches:
                            schedule = models.ScheduleTb(
                                lecture_id=lecture.lecture_id,
                                day_of_week=day,
                                start_min=to_mins(start),
                                end_min=to_mins(end),
                                start_time=start + ":00",
                                end_time=end + ":00"
                            )
                            db.add(schedule)
                    except Exception:
                        continue
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"PDF 파싱 중 서버 에러: {str(e)}")
    finally:
        os.remove(tmp_path)
        
    return {"message": "PDF 강의 계획서 파싱 및 DB 정보 등록이 성공적으로 완료되었습니다."}


class AIRecommendRequest(BaseModel):
    user_id: int
    preference: str
    
@app.post("/api/v1/student/ai/recommend")
def get_ai_recommendation(req: AIRecommendRequest, db: Session = Depends(get_db)):
    """AI를 활용한 학생 맞춤형 과목 추천 (Bedrock Mocking) 및 장바구니 자동 적재"""
    user = db.query(models.User).filter(models.User.user_no == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")
        
    # 실제 환경에서는 boto3로 Bedrock Titan/Claude를 호출해 아래 로직 수행
    # 현재는 전체 강의 중 랜덤하게 또는 Mock 로직으로 응답한다고 가정.
    all_lectures = db.query(models.Lecture).limit(5).all()
    recommended_ids = [lec.lecture_id for lec in all_lectures[:3]] # 3개 추천
    
    inserted_count = 0
    for l_id in recommended_ids:
        # 이미 담겼는지 확인
        existing = db.query(models.Enrollment).filter(
            models.Enrollment.user_id == req.user_id,
            models.Enrollment.lecture_id == l_id
        ).first()
        if not existing:
            new_en = models.Enrollment(user_id=req.user_id, lecture_id=l_id, status="cart")
            db.add(new_en)
            inserted_count += 1
            
    db.commit()
    
    return {
        "message": f"AI 분석 결과에 따라 {inserted_count}개의 과목이 장바구니에 담겼습니다.",
        "recommended_count": len(recommended_ids),
        "popular_chat_keywords": [
            {"keyword": "수강신청", "count": 145},
            {"keyword": "휴학", "count": 89},
            {"keyword": "기숙사", "count": 56},
            {"keyword": "졸업요건", "count": 34}
        ]
    }


# --- 챗봇 ---
@app.post("/api/v1/chat/ask")
def chat_ask(req: ChatRequest, db: Session = Depends(get_db)):
    """AI 학사 행정 상담 (RAG 기반 응답 로직 연결부 - Mocking)"""
    logger.info(f"채팅 질의 수신 - session: {req.session_id}, msg: {req.message}")

    session = db.query(models.ChatSession).filter(models.ChatSession.id == req.session_id).first()
    if not session:
        session = models.ChatSession(id=req.session_id, user_id=req.user_id, title=req.message[:20])
        db.add(session)
        db.commit()

    db.add(models.ChatMessage(session_id=req.session_id, role="user", content=req.message))
    db.commit()

    user_msg = req.message.lower()
    reply_text = "질문하신 내용에 대해 현재 확인 중입니다. 학사지원팀에 문의해주세요."
    source_info = []

    if "수강신청" in user_msg or "장바구니" in user_msg:
        reply_text = "수강신청은 좌측 '수강 신청' 메뉴에서 진행하실 수 있습니다. 장바구니에 담은 후 정해진 기간 내에 최종 신청을 완료해야 합니다."
        source_info = [{"title": "학사 규정: 제20조 수강신청", "url": "#sugang"}]
    elif "휴학" in user_msg or "군휴학" in user_msg:
        reply_text = "휴학 신청 서류(일반휴학원) 초안을 자동으로 생성하여 결재함에 제출했습니다. 교학팀의 검토 후 최종 승인됩니다."
        source_info = [{"title": "학사 규정: 휴학 및 복학 안내", "url": "#leave"}]
        db.add(models.Form(
            user_id=req.user_id,
            form_type="일반휴학원",
            form_data={"reason": "AI 챗봇을 통한 자동 휴학 신청 접수"},
            status="pending"
        ))
        db.commit()
    elif "장학금" in user_msg or "국가장학금" in user_msg:
        reply_text = "성적우수 장학금은 별도의 신청 없이 자동으로 선발되며, 국가장학금은 매 학기 한국장학재단 홈페이지에서 신청하셔야 합니다."
        source_info = [{"title": "장학 안내 공지", "url": "#scholarship"}]
    elif "졸업" in user_msg or "요건" in user_msg:
        reply_text = "졸업을 위해서는 130학점 이상 이수와 필수 전공/교양 과목을 모두 들어야 하며, 졸업 논문 혹은 대체 자격증(토익 800점 등)을 제출하셔야 합니다."
        source_info = [{"title": "총칙: 졸업 요건 규정", "url": "#graduation"}]
    else:
        reply_text = f"말씀하신 '{req.message}' 에 대한 구체적인 문서를 찾고 있습니다. (RAG 연동 전 테스트 응답)"

    db.add(models.ChatMessage(session_id=req.session_id, role="assistant", content=reply_text))
    db.commit()

    return {"reply": reply_text, "sources": source_info}


# --- 서류 ---
@app.post("/api/v1/forms/generate")
def generate_form(req: FormRequest):
    """문서 초안 자동 생성"""
    return {
        "form_id": "draft_001",
        "status": "draft",
        "preview_json": {"applicant": "test", "reason": req.reason}
    }


@app.get("/api/v1/forms")
def get_all_forms(db: Session = Depends(get_db)):
    """관리자용: 신청된 모든 폼 내역 조회"""
    forms = db.query(models.Form).order_by(models.Form.created_at.desc()).all()
    result = []
    for f in forms:
        user = db.query(models.User).filter(models.User.user_no == f.user_id).first()
        result.append({
            "id": f.id,
            "form_type": f.form_type,
            "status": f.status,
            "student_id": user.loginid if user else "Unknown",
            "name": user.user_name if user else "Unknown",
            "created_at": f.created_at.isoformat()
        })
    return {"forms": result}


@app.put("/api/v1/forms/{form_id}/status")
def update_form_status(form_id: str, req: FormStatusRequest, db: Session = Depends(get_db)):
    """관리자용: 폼 결재 승인/반려 상태 업데이트"""
    form = db.query(models.Form).filter(models.Form.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="서류를 찾을 수 없습니다.")
    form.status = req.status
    db.commit()
    return {"message": f"서류 상태가 {req.status}(으)로 변경되었습니다."}


# --- RAG ---
@app.post("/api/v1/admin/rag/upload")
def upload_rag_document(req: RAGUploadRequest, db: Session = Depends(get_db)):
    """관리자용: AI 지식베이스 문서 업로드"""
    new_doc = models.DocumentMetadata(
        doc_type="rag_knowledge",
        title=req.title,
        source_url=req.content[:100]
    )
    db.add(new_doc)
    db.commit()
    return {"message": f"'{req.title}' 항목이 AI 지식베이스에 성공적으로 임베딩(업로드) 되었습니다."}


# --- 공지사항 ---
@app.post("/api/v1/notices")
def create_notice(req: NoticeRequest, db: Session = Depends(get_db)):
    db.add(models.Notice(title=req.title, content=req.content))
    db.commit()
    return {"message": "공지가 등록되었습니다."}


@app.get("/api/v1/notices")
def get_notices(db: Session = Depends(get_db)):
    notices = db.query(models.Notice).order_by(models.Notice.created_at.desc()).all()
    return {"notices": notices}


# --- 성적 ---
@app.post("/api/v1/admin/grades")
def submit_grade(req: GradeRequest, db: Session = Depends(get_db)):
    existing = db.query(models.Grade).filter(models.Grade.enrollment_id == req.enrollment_id).first()
    if existing:
        existing.score = req.score
        existing.grade_letter = req.grade_letter
    else:
        db.add(models.Grade(
            enrollment_id=req.enrollment_id,
            user_id=req.user_id,
            score=req.score,
            grade_letter=req.grade_letter
        ))
    db.commit()
    return {"message": "성적이 정상적으로 입력되었습니다."}


# --- 사용자 정보 수정 ---
@app.put("/api/v1/users/{user_id}")
def update_user_profile(user_id: str, req: UserUpdateRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.user_no == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    if req.name:   user.user_name = req.name
    if req.status: user.user_status = req.status
    db.commit()
    return {"message": "프로필 정보가 수정되었습니다."}


# --- 수강신청 일차별 스케줄 설정 (신규) ---

@app.get("/api/v1/admin/enrollment-schedule")
def get_enrollment_schedule(db: Session = Depends(get_db)):
    """관리자용: 수강신청 일차별 기간·제한 조회"""
    schedules = db.query(models.EnrollmentSchedule).order_by(
        models.EnrollmentSchedule.day_number
    ).all()
    return {"schedules": [
        {
            "id": s.id,
            "day_number": s.day_number,
            "open_datetime": s.open_datetime.isoformat() + "Z",
            "close_datetime": s.close_datetime.isoformat() + "Z",
            "restriction_type": s.restriction_type,
            "is_active": s.is_active,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        } for s in schedules
    ]}


@app.post("/api/v1/admin/enrollment-schedule")
def save_enrollment_schedule(req: EnrollmentScheduleBulkRequest, db: Session = Depends(get_db)):
    """관리자용: 수강신청 일차별 기간·제한 저장 (upsert)"""
    for day_req in req.schedules:
        try:
            open_dt = datetime.fromisoformat(day_req.open_datetime.replace("Z", ""))
            close_dt = datetime.fromisoformat(day_req.close_datetime.replace("Z", ""))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"날짜 형식 오류: {e}")

        existing = db.query(models.EnrollmentSchedule).filter(
            models.EnrollmentSchedule.day_number == day_req.day_number
        ).first()
        if existing:
            existing.open_datetime = open_dt
            existing.close_datetime = close_dt
            existing.restriction_type = day_req.restriction_type
            existing.is_active = day_req.is_active
            existing.updated_at = datetime.utcnow()
        else:
            db.add(models.EnrollmentSchedule(
                day_number=day_req.day_number,
                open_datetime=open_dt,
                close_datetime=close_dt,
                restriction_type=day_req.restriction_type,
                is_active=day_req.is_active,
            ))
    db.commit()
    return {"message": "수강신청 일정이 저장되었습니다."}


@app.get("/api/v1/enrollment/access-check")
def enrollment_access_check(user_id: str, lecture_id: Optional[int] = None, db: Session = Depends(get_db)):
    """학생용: 현재 수강신청 가능 여부 및 활성 일차 반환"""
    user = db.query(models.User).filter(models.User.user_no == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    result = _check_enrollment_access(user, lecture_id, db)
    return result


# --- 수강신청 기간 설정 (구 SystemConfig 방식) ---
@app.get("/api/v1/admin/config/enrollment-period")
def get_enrollment_period(db: Session = Depends(get_db)):
    start = db.query(models.SystemConfig).filter(models.SystemConfig.key == "enrollment_start").first()
    end = db.query(models.SystemConfig).filter(models.SystemConfig.key == "enrollment_end").first()
    return {
        "start": start.value if start else None,
        "end": end.value if end else None,
        "is_active": is_enrollment_period_active(db)
    }


@app.post("/api/v1/admin/config/enrollment-period")
def set_enrollment_period(req: EnrollmentPeriodRequest, db: Session = Depends(get_db)):
    start = db.query(models.SystemConfig).filter(models.SystemConfig.key == "enrollment_start").first()
    if not start:
        db.add(models.SystemConfig(key="enrollment_start", value=req.start_time))
    else:
        start.value = req.start_time

    end = db.query(models.SystemConfig).filter(models.SystemConfig.key == "enrollment_end").first()
    if not end:
        db.add(models.SystemConfig(key="enrollment_end", value=req.end_time))
    else:
        end.value = req.end_time

    db.commit()
    return {"message": "수강신청 기간이 설정되었습니다."}

# --- 프론트엔드 정적 파일 서빙 ---
# (API 경로를 먼저 정의한 후 마지막에 마운트해야 API가 우선순위를 가집니다)
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
