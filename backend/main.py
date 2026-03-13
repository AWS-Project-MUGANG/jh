import logging
import os
import time
import json
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import random
from jose import jwt
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, BigInteger, func, text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, joinedload, selectinload, Session
from sqlalchemy.types import Enum as SAEnum
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import uuid
import csv
import io
import pdfplumber
import re
import tempfile
import boto3
from botocore.config import Config

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

def ensure_schema_compatibility():
    """Legacy DB schema와 현재 ORM 모델 간의 최소 호환성 보정."""
    try:
        with engine.begin() as conn:
            # pgvector 확장 활성화 (벡터 검색 필수)
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            
            # user_tb: 구 스키마에 없을 수 있는 컬럼
            conn.execute(text("ALTER TABLE user_tb ADD COLUMN IF NOT EXISTS email VARCHAR(150)"))
            conn.execute(text("ALTER TABLE user_tb ADD COLUMN IF NOT EXISTS phone VARCHAR(20)"))
            conn.execute(text("ALTER TABLE user_tb ADD COLUMN IF NOT EXISTS is_first_login BOOLEAN DEFAULT TRUE"))

            # enroll_tb: 구 스키마에 없을 수 있는 컬럼
            conn.execute(text("ALTER TABLE enroll_tb ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'cart'"))

            # 구 DDL에서 sche_no가 NOT NULL이면 강의 담기 INSERT가 실패할 수 있어 해제
            conn.execute(text("ALTER TABLE enroll_tb ALTER COLUMN sche_no DROP NOT NULL"))
    except Exception as e:
        logger.warning(f"Schema compatibility patch skipped or partially failed: {e}")

# 시작 시 DB 스키마 보정 + 테이블 생성 (개발용)
ensure_schema_compatibility()
try:
    models.Base.metadata.create_all(bind=engine)
except Exception as e:
    # pgvector 확장이 설치되지 않은 DB일 경우 테이블 생성 실패로 서버가 죽는 것을 방지
    logger.error(f"테이블 생성 중 오류 발생 (DB 확장 기능 확인 필요): {e}")

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

# 프론트엔드 정적 파일 연결 (도커 환경 대응)
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")
    logger.info(f"정적 파일 경로 연결됨: {frontend_path}")
else:
    logger.info(f"정적 파일 경로 없음 (Docker/MSA 환경에서는 Nginx가 처리하므로 무시 가능): {frontend_path}")

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
    user_id: int
    session_id: str
    message: str

class FormRequest(BaseModel):
    form_type: str
    reason: str

class FormStatusRequest(BaseModel):
    status: str

class NoticeRequest(BaseModel):
    title: str
    content: str

class GradeRequest(BaseModel):
    enrollment_id: int
    user_id: int
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
    user_id: int
    lecture_id: int  # lecture_tb.lecture_id 참조

class EnrollmentScheduleDayRequest(BaseModel):
    day_number: int
    open_datetime: str   # UTC ISO string
    close_datetime: str  # UTC ISO string
    restriction_type: str  # 'own_grade_dept' | 'own_college' | 'all'
    is_active: bool = True

class EnrollmentScheduleBulkRequest(BaseModel):
    schedules: List[EnrollmentScheduleDayRequest]

class AdminCourseTime(BaseModel):
    day: int
    time: int

class AdminCourseCreateRequest(BaseModel):
    subject: str
    college: Optional[str] = None
    department: Optional[str] = None
    course_type: Optional[str] = None
    room: Optional[str] = None
    credit: int = 3
    capacity: int = 40
    professor_id: Optional[int] = None
    times: List[AdminCourseTime] = []

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


# ---- AI/ML 헬퍼 함수 (Bedrock) ----
def get_embedding(text: str) -> List[float]:
    """AWS Bedrock Titan 모델을 사용하여 텍스트 임베딩 생성 (1536차원)"""
    try:
        # 리전은 서울(ap-northeast-2) 또는 버지니아(us-east-1) 사용
        config = Config(connect_timeout=5, read_timeout=30)
        bedrock = boto3.client(service_name='bedrock-runtime', region_name='us-east-1', config=config)
        
        body = json.dumps({"inputText": text})
        response = bedrock.invoke_model(
            modelId="amazon.titan-embed-text-v1",
            contentType="application/json",
            accept="application/json",
            body=body
        )
        response_body = json.loads(response.get("body").read())
        return response_body.get("embedding")
    except Exception as e:
        logger.error(f"Bedrock Embedding Error: {e}")
        return []

def generate_answer_with_bedrock(query: str, context: str) -> str:
    """AWS Bedrock(Claude)을 사용하여 검색된 문맥 기반 답변 생성"""
    try:
        config = Config(connect_timeout=5, read_timeout=60)
        bedrock = boto3.client(service_name='bedrock-runtime', region_name='us-east-1', config=config)

        # Claude v2/v2.1 프롬프트
        prompt = f"\n\nHuman: 당신은 대학교 학사 행정 AI 어시스턴트입니다. 다음의 [참고 문서] 내용을 바탕으로 사용자의 [질문]에만 해당하는 내용을 간결하게 답변해주세요. 질문과 직접 관련 없는 정보는 포함하지 마세요. 문서에 없는 내용은 지어내지 말고, 정보가 부족하면 모른다고 답하세요. 답변은 2~3문장 이내로 핵심만 말하세요.\n\n[참고 문서]\n{context}\n\n[질문]\n{query}\n\nAssistant:"

        body = json.dumps({
            "prompt": prompt,
            "max_tokens_to_sample": 1000,
            "temperature": 0.1,  # 사실 기반 답변을 위해 낮춤
            "top_p": 0.9
        })

        response = bedrock.invoke_model(
            modelId="anthropic.claude-v2", 
            contentType="application/json",
            accept="application/json",
            body=body
        )
        response_body = json.loads(response.get("body").read())
        return response_body.get("completion")
    except Exception as e:
        logger.error(f"Bedrock Generation Error: {e}")
        return None

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
        "user_no": user.user_no,
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


# --- 단과대학/학과 목록 ---
@app.get("/api/v1/departments")
def get_departments(db: Session = Depends(get_db)):
    """단과대학 → 학과 목록 반환 (필터바 동적 로딩용)"""
    departs = db.query(models.Depart).order_by(models.Depart.college, models.Depart.depart).all()
    colleges = {}
    for d in departs:
        if d.college not in colleges:
            colleges[d.college] = []
        colleges[d.college].append(d.depart)
    return {"colleges": colleges}


# --- 필터 옵션 (단과대 + 학년) ---
@app.get("/api/v1/admin/filter-options")
def get_filter_options(db: Session = Depends(get_db)):
    """관리자 필터바용: DB에서 단과대 목록 및 강의 학년 목록 반환"""
    departs = db.query(models.Depart.college).distinct().order_by(models.Depart.college).all()
    colleges = [row.college for row in departs if row.college]

    grades = (
        db.query(models.Lecture.lec_grade)
        .filter(models.Lecture.lec_grade.isnot(None))
        .distinct()
        .order_by(models.Lecture.lec_grade)
        .all()
    )
    grade_list = [str(row.lec_grade) for row in grades if row.lec_grade]

    return {"colleges": colleges, "grades": grade_list}


# --- 강의 (lecture_tb) ---
@app.get("/api/v1/lectures")
def get_lectures(
    page: int = 1,
    size: int = 50,
    college: Optional[str] = None,
    lec_grade: Optional[str] = None,
    lecture_type: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """강의 목록 조회 (수강신청 화면용) - 페이지네이션 + 필터 + selectinload 최적화"""
    query = db.query(models.Lecture).options(
        selectinload(models.Lecture.schedules),  # OneToMany: selectinload로 Cartesian product 방지
        joinedload(models.Lecture.depart)        # ManyToOne: joinedload 유지
    )

    # 필터 적용
    if college:
        query = query.join(models.Depart, models.Lecture.dept_no == models.Depart.dept_no).filter(
            models.Depart.college == college
        )
    if lec_grade:
        query = query.filter(models.Lecture.lec_grade == lec_grade)
    if lecture_type:
        query = query.filter(models.Lecture.type == lecture_type)
    if search:
        query = query.filter(models.Lecture.subject.ilike(f"%{search}%"))

    total = query.count()
    lectures = query.offset((page - 1) * size).limit(size).all()

    # FK가 없는 레거시 데이터 처리를 위한 맵 (필요할 때만 생성)
    dept_college_map = None
    college_set = None
    dept_alias = {
        "사회대": "사회과학대학",
        "사범대": "사범대학",
        "공공인재": "공공인재대학",
        "디예대": "디자인예술대학",
        "재과대": "재활과학대학",
        "문화콘텐츠": "문화콘텐츠학부",
        "글로컬라이프": "글로컬라이프대학",
        "대학전체": "대학전체",
    }

    result = []
    for lec in lectures:
        schedules = [
            {
                "day_of_week": s.day_of_week,
                "start_time": str(s.start_time) if s.start_time else None,
                "end_time": str(s.end_time) if s.end_time else None,
                "classroom": s.classroom,
            }
            for s in lec.schedules
        ]

        # 1. FK 관계(depart)가 있으면 우선 사용 (가장 빠름)
        if lec.depart:
            college_name = lec.depart.college
            department = lec.depart.depart
        else:
            # 2. FK가 없으면 문자열 매칭 시도 (레거시 데이터 대응)
            if dept_college_map is None:
                dept_college_map = {d.depart: d.college for d in db.query(models.Depart).all()}
                college_set = set(dept_college_map.values())
            department = lec.department
            if department in dept_alias:
                department = dept_alias[department]
            college_name = dept_college_map.get(department)
            
            # 3. 매핑 실패 시 확장된 fallback_mapping 사용
            college = None
            if not college_name:
                fallback_mapping = {
                    '특교유특초특': '사범대학', '수교화교': '사범대학', '물교지구': '사범대학', 
                    '사범대': '사범대학', '영교': '사범대학', '역교': '사범대학', '일사': '사범대학',
                    '국교': '사범대학', '지교': '사범대학', '유교': '사범대학',
                    '자전융합': '자유전공학부', '자유전공': '자유전공학부',
                    '공공인재': '공공인재대학', '공공': '공공인재대학', '프리로스쿨': '공공인재대학',
                    '글경': '글로벌경영대학', '글로벌경영': '글로벌경영대학', '비즈니스데이터': '글로벌경영대학',
                    '사과': '사회과학대학', '사회대': '사회과학대학', '동아시아': '사회과학대학', '도시인문': '사회과학대학',
                    # 보건/의료/재활
                    '보건': '보건바이오대학', '재활': '재활과학대학', '재과대': '재활과학대학',
                    '간호': '간호대학', '미술치료': '재활과학대학',
                    # 예술/디자인/체육
                    '디예': '디자인예술대학', '디예대': '디자인예술대학',
                    '체육': '체육레저학부', '스포츠산업': '체육레저학부',
                    # 문화콘텐츠/미디어
                    '문콘': '문화콘텐츠학부', '문화콘텐츠': '문화콘텐츠학부',
                    '디지털미디어': '문화콘텐츠학부',
                    # IT/공과
                    'IT·공과': 'IT·공과대학', '글로벌ICT': 'IT·공과대학', '스마트센싱': 'IT·공과대학',
                    # 글로컬/외식/생태/스마트 계열 (글로컬라이프대학)
                    '글로컬': '글로컬라이프대학', '글로컬라이프': '글로컬라이프대학', 
                    '외식산업': '글로컬라이프대학', '생태관광': '글로컬라이프대학', 
                    '스마트팜': '글로컬라이프대학', '스마트제로': '글로컬라이프대학',
                    # 교양
                    '대학전체': '교양대학',
                }
                college = fallback_mapping.get(department)
                if not college:
                    for k, v in fallback_mapping.items():
                        if k in department:
                            college = v
                            break

                # 그럼에도 불구하고 매핑이 없으면 연계/융합전공 처리
                if not college:
                    if any(kw in department for kw in ['전공', '창업학', '인문', '디지털미디어', '관광', '치유', '학']):
                        college = '연계/융합대학'
                    else:
                        college = '기타대학'

            if not college_name and college:
                college_name = college

            # department 값이 실제 단과대/학부명인 경우 college로 승격
            if not college_name and department and college_set and department in college_set:
                college_name = department
                department = None

            # 대학전체 표기
            if department == "대학전체":
                college_name = "대학전체"
                department = None
                            
        # 강의실 '-' 처리
        classroom = lec.classroom
        if not classroom or classroom.strip() == '-' or classroom.strip() == '':
            classroom = "미지정"

        result.append({
            "lecture_id": lec.lecture_id,
            "course_no": lec.course_no,
            "subject": lec.subject,
            "college": college_name,
            "department": department,
            "lec_grade": lec.lec_grade,
            "credit": lec.credit,
            "professor": lec.professor,
            "classroom": schedules[0]["classroom"] if schedules else (lec.classroom or None),
            "type": lec.type,
            "capacity": lec.capacity,
            "count": lec.count,
            "schedules": schedules,
        })

    return {
        "lectures": result,
        "total": total,
        "page": page,
        "size": size,
        "total_pages": (total + size - 1) // size,
    }


@app.get("/api/v1/lectures/{lecture_id}")
def get_lecture_detail(lecture_id: int, db: Session = Depends(get_db)):
    """단일 강의 조회 (시간표 캐시용)"""
    lec = db.query(models.Lecture).options(
        selectinload(models.Lecture.schedules),
        joinedload(models.Lecture.depart)
    ).filter(models.Lecture.lecture_id == lecture_id).first()

    if not lec:
        raise HTTPException(status_code=404, detail="강의를 찾을 수 없습니다.")

    schedules = [
        {
            "day_of_week": s.day_of_week,
            "start_time": str(s.start_time) if s.start_time else None,
            "end_time": str(s.end_time) if s.end_time else None,
            "classroom": s.classroom,
        }
        for s in lec.schedules
    ]

    return {
        "lecture_id": lec.lecture_id,
        "subject": lec.subject,
        "college": lec.depart.college if lec.depart else None,
        "department": lec.depart.depart if lec.depart else lec.department,
        "credit": lec.credit,
        "professor": lec.professor,
        "classroom": schedules[0]["classroom"] if schedules else lec.classroom,
        "type": lec.type,
        "capacity": lec.capacity,
        "count": lec.count,
        "schedules": schedules,
    }



# --- 수강신청 (enrollments) ---

@app.get("/api/v1/enrollments/{user_id}")
def get_user_enrollments(user_id: int, db: Session = Depends(get_db)):
    """사용자의 수강신청 내역 조회 (lecture_tb 조인) - CANCELED 제외"""
    dept_college_map = {d.depart: d.college for d in db.query(models.Depart).all()}
    enrollments = db.query(models.Enrollment).options(
        joinedload(models.Enrollment.lecture).joinedload(models.Lecture.depart),
        joinedload(models.Enrollment.lecture).selectinload(models.Lecture.schedules)
    ).filter(
        models.Enrollment.user_id == user_id,
        models.Enrollment.enroll_status != "CANCELED"
    ).all()
    result = []
    for en in enrollments:
        lec = en.lecture
        college = (lec.depart.college if lec.depart else dept_college_map.get(lec.department)) if lec else None
        classroom = (lec.schedules[0].classroom if lec.schedules else None) if lec else None
        lec_schedules = [
            {
                "day_of_week": s.day_of_week,
                "start_time": str(s.start_time) if s.start_time else None,
                "end_time": str(s.end_time) if s.end_time else None,
                "classroom": s.classroom,
            }
            for s in (lec.schedules if lec else [])
        ]
        result.append({
            "id": en.id,
            "lecture_id": en.lecture_id,
            "subject": lec.subject if lec else None,
            "college": college,
            "department": (lec.depart.depart if lec.depart else lec.department) if lec else None,
            "classroom": classroom,
            "professor": lec.professor if lec else None,
            "type": lec.type if lec else None,
            "credits": lec.credit if lec else None,
            "enroll_status": en.enroll_status,  # BASKET | COMPLETED | CANCELED
            "created_at": en.created_at.isoformat(),
            "schedules": lec_schedules,
        })
    return {"schedules": result}


@app.post("/api/v1/enrollments")
def create_enrollment(req: EnrollmentRequest, db: Session = Depends(get_db)):
    """수강신청 1건 저장 (정원 체크 + 대기열 편입 + 낙관적 락)"""
    # 새 스케줄 시스템이 설정된 경우 해당 시스템 우선 사용, 없으면 구 SystemConfig 방식
    schedule_exists = db.query(models.EnrollmentSchedule).filter(
        models.EnrollmentSchedule.is_active == True
    ).first()
    if schedule_exists:
        if not _get_active_schedule(db):
            raise HTTPException(status_code=403, detail="현재는 수강신청 기간이 아닙니다.")
    elif not is_enrollment_period_active(db):
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
        try:
            db.commit()
        except SQLAlchemyError as e:
            db.rollback()
            logger.exception("Waitlist insert failed")
            raise HTTPException(status_code=500, detail=f"대기열 등록 중 DB 오류가 발생했습니다: {str(e)}")
        
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

    # 구 DB에서는 sche_no가 NOT NULL일 수 있어 강의의 첫 스케줄을 기본값으로 사용
    first_schedule = db.query(models.ScheduleTb).filter(
        models.ScheduleTb.lecture_id == req.lecture_id
    ).order_by(models.ScheduleTb.sche_no.asc()).first()

    new_enrollment = models.Enrollment(
        user_id=req.user_id,
        lecture_id=req.lecture_id,
        sche_no=first_schedule.sche_no if first_schedule else None,
        enroll_status="BASKET"
    )
    db.add(new_enrollment)
    try:
        db.commit()
        db.refresh(new_enrollment)
    except IntegrityError as e:
        db.rollback()
        logger.exception("Enrollment insert integrity error")
        raise HTTPException(status_code=409, detail=f"수강신청 저장 중 무결성 오류가 발생했습니다: {str(e.orig)}")
    except SQLAlchemyError as e:
        db.rollback()
        logger.exception("Enrollment insert failed")
        raise HTTPException(status_code=500, detail=f"수강신청 저장 중 DB 오류가 발생했습니다: {str(e)}")

    return {"message": "예비 수강신청이 완료되었습니다.", "enrollment_id": new_enrollment.id, "enroll_status": "BASKET"}


@app.put("/api/v1/enrollments/{enrollment_id}/confirm")
def confirm_enrollment(enrollment_id: int, db: Session = Depends(get_db)):
    """수강 장바구니 → 최종 신청 확정"""
    schedule_exists = db.query(models.EnrollmentSchedule).filter(
        models.EnrollmentSchedule.is_active == True
    ).first()
    if schedule_exists:
        if not _get_active_schedule(db):
            raise HTTPException(status_code=403, detail="현재는 수강신청 기간이 아닙니다.")
    elif not is_enrollment_period_active(db):
        raise HTTPException(status_code=403, detail="현재는 수강신청 기간이 아닙니다.")

    en = db.query(models.Enrollment).filter(models.Enrollment.id == enrollment_id).first()
    if not en:
        raise HTTPException(status_code=404, detail="해당 수강 내역이 없습니다.")
    en.enroll_status = "COMPLETED"
    db.commit()
    return {"message": "최종 수강신청이 확정되었습니다."}


@app.delete("/api/v1/enrollments/{enrollment_id}")
def drop_enrollment(enrollment_id: int, db: Session = Depends(get_db)):
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
            enroll_status="COMPLETED"
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
def get_student_stats(user_id: int, db: Session = Depends(get_db)):
    """학생용: 이수 학점 및 성적 조회"""
    enrollments = db.query(models.Enrollment).options(
        joinedload(models.Enrollment.lecture)
    ).filter(
        models.Enrollment.user_id == user_id,
        models.Enrollment.enroll_status == "COMPLETED"
    ).all()

    current_credits = sum(en.lecture.credit for en in enrollments if en.lecture and en.lecture.credit)

    grades = db.query(models.Grade).filter(models.Grade.user_id == user_id).all()

    # enrollment를 한 번에 map으로 로드 (루프 내 개별 쿼리 제거)
    enrollment_ids = [g.enrollment_id for g in grades]
    enrollment_map = {}
    if enrollment_ids:
        loaded = db.query(models.Enrollment).options(
            joinedload(models.Enrollment.lecture)
        ).filter(models.Enrollment.id.in_(enrollment_ids)).all()
        enrollment_map = {en.id: en for en in loaded}

    grade_points = {"A+": 4.5, "A0": 4.0, "B+": 3.5, "B0": 3.0, "C+": 2.5, "C0": 2.0, "D+": 1.5, "D0": 1.0, "F": 0.0}

    total_point_sum = 0
    total_credit_sum = 0
    for g in grades:
        en = enrollment_map.get(g.enrollment_id)
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
    page: int = 1,
    size: int = 10,
    college: Optional[str] = None,
    grade: Optional[str] = None,
    lecture_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """관리자용: 개설 과목별 수강생 현황 (페이지네이션 적용)"""
    # 1. 강의(Lecture)를 기준으로 먼저 페이징
    query = db.query(models.Lecture).options(
        joinedload(models.Lecture.depart)
    )

    # 필터 적용
    if lecture_id:
        query = query.filter(models.Lecture.lecture_id == lecture_id)
    if grade:
        query = query.filter(models.Lecture.lec_grade == grade)
    if college:
        query = query.join(models.Depart, models.Lecture.dept_no == models.Depart.dept_no)\
                     .filter(models.Depart.college == college)

    # 전체 개수 및 페이징 처리
    total = query.count()
    lectures = query.order_by(models.Lecture.subject).offset((page - 1) * size).limit(size).all()

    # 레거시 데이터(dept_no 없는 강의) 대비 fallback map - 필요할 때만 생성
    dept_college_map = None

    classes_result = []

    for lec in lectures:
        # 해당 강의의 수강생(COMPLETED) 조회
        enrollments = db.query(models.Enrollment).options(
            joinedload(models.Enrollment.user)
        ).filter(
            models.Enrollment.lecture_id == lec.lecture_id,
            models.Enrollment.enroll_status == "COMPLETED"
        ).all()

        # college 필터가 없거나 이미 DB에서 걸렸으므로, 레거시 fallback만 처리
        if college and not lec.dept_no:
            if dept_college_map is None:
                dept_college_map = {d.depart: d.college for d in db.query(models.Depart).all()}
            if dept_college_map.get(lec.department) != college:
                continue

        student_list = []
        for en in enrollments:
            user = en.user
            student_list.append({
                "enrollment_id": en.id,
                "user_id": en.user_id,
                "student_id": user.loginid if user else "Unknown",
                "name": user.user_name if user else "Unknown"
            })

        classes_result.append({
            "lecture_id": lec.lecture_id,
            "subject": lec.subject,
            "capacity": lec.capacity or 0,
            "count": lec.count or 0,
            "students": student_list
        })

    return {
        "classes": classes_result,
        "total": total,
        "page": page,
        "size": size,
        "total_pages": (total + size - 1) // size
    }


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
    # CSV 헤더 예시: subject, department, professor, type, credit, capacity, waitlist_capacity
    for row in reader:
        lectures_to_insert.append(
            models.Lecture(
                subject=row.get("subject"),
                department=row.get("department"),
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
    room_re = re.compile(r'([가-힣A-Za-z0-9]+관-\d+|[가-힣A-Za-z0-9]+-\d{3,4})')
    # PDF에서 나오는 약어 → depart_tb의 정식 학과명으로 매핑 (dept_map으로 dept_no 연결)
    dept_alias = {
        # 약어 → 정식명
        "사회대": "사회과학대학",
        "사범대": "사범대학",
        "공공인재": "공공인재대학",
        "디예대": "디자인예술대학",
        "재과대": "재활과학대학",
        "문화콘텐츠": "문화콘텐츠학부",
        "글로컬라이프": "글로컬라이프대학",
        # PDF 5번에서 발견된 추가 명칭/약어 매핑
        "글경": "글로벌경영대학",
        "보건": "보건바이오대학",
        "디예": "디자인예술대학",
        "문콘": "문화콘텐츠학부",
        "글로컬": "글로컬라이프대학",
        "사과": "사회과학대학",
        # 정식명(이미 depart_tb에 존재) → 동일
        "보건바이오대학": "보건바이오대학",
        "글로벌경영대학": "글로벌경영대학",
        "체육레저학부": "체육레저학부",
        "문화콘텐츠학부": "문화콘텐츠학부",
        "IT·공과대학": "IT·공과대학",
        # 연계/융합전공 계열 (depart_tb에 없는 경우 그대로 저장)
        "대학전체": "대학전체",
    }
    
    try:
        # 루프 진입 전 사전 로드 — 행마다 쿼리 대신 dict 조회 (O(n) → O(1))
        existing_course_nos = {
            r[0] for r in db.query(models.Lecture.course_no).all()
        }
        dept_map = {
            d.depart: d.dept_no for d in db.query(models.Depart).all()
        }

        # PDF 파싱 (changepdftocsv.py 원본 로직 이식)
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if not table: continue

                current_grade = ""
                current_type = ""
                header = [re.sub(r'\s+', '', h or '') for h in table[0]]

                def col(name, fallback):
                    return header.index(name) if name in header else fallback

                idx_grade = col("학년", 0)
                idx_type = col("구분", 1)
                idx_dept = col("수강학과", 2)
                idx_course = col("수강번호", 3)
                idx_subject = col("교과목명", 4)
                idx_credit = col("학점", 5)
                idx_prof = col("담당교수", 7)
                idx_time = col("강의시간", 8)
                idx_room = col("강의실", 9)

                def cell(row, idx):
                    return row[idx] if idx is not None and idx < len(row) else None
                for row in table[1:]:
                    try:
                        c_no = cell(row, idx_course)
                        if not c_no: continue
                        c_no = c_no.strip()
                        if not c_no.isdigit():
                            continue

                        raw_time = cell(row, idx_time) if cell(row, idx_time) else ""

                        # 중복 여부 체크 — dict 조회 (쿼리 없음)
                        if c_no in existing_course_nos:
                            continue
                        existing_course_nos.add(c_no)  # 같은 PDF 내 중복도 방지

                        # 학년/구분 상태 유지 로직 추가 (빈칸이면 직전 값 유지)
                        if cell(row, idx_grade) and cell(row, idx_grade).strip():
                            current_grade = cell(row, idx_grade).strip()
                        if cell(row, idx_type) and cell(row, idx_type).strip():
                            current_type = cell(row, idx_type).strip()
                            
                        # 구분 값 매핑 (models.py의 lecture_category enum은 한국어 값 사용)
                        type_str = ""
                        type_mapping = {
                            '전필': '전공필수', '전선': '전공선택',
                            '교필': '교양필수', '교선': '교양선택',
                            '교직': '교직', '공통': '공통',
                            '일선': '전공선택', '기필': '교양필수',
                            '기선': '교양선택', '기초': '교양필수'
                        }
                        if current_type:
                            key = current_type[:2] if len(current_type) >= 2 else current_type
                            type_str = type_mapping.get(key, '전공선택')
                        else:
                            type_str = '전공선택'
                            
                        c_dept = cell(row, idx_dept).replace('\n', '') if cell(row, idx_dept) else ""
                        if c_dept in dept_alias:
                            c_dept = dept_alias[c_dept]
                        c_prof = cell(row, idx_prof).replace('\n', '') if cell(row, idx_prof) else "미지정"
                        c_room = cell(row, idx_room).replace('\n', '') if cell(row, idx_room) else ""
                        if not c_room:
                            m = room_re.search(raw_time or "")
                            if m:
                                c_room = m.group(1)
                        if not c_room:
                            c_room = "미지정"
                        
                        # lecture_tb 데이터 생성
                        lecture = models.Lecture(
                            course_no=c_no,
                            subject=cell(row, idx_subject).replace('\n', '') if cell(row, idx_subject) else "",
                            department=c_dept,
                            dept_no=dept_map.get(c_dept),
                            lec_grade=current_grade,
                            credit=int(cell(row, idx_credit)) if cell(row, idx_credit) and str(cell(row, idx_credit)).isdigit() else 3,
                            professor=c_prof,
                            classroom=c_room,
                            type=type_str,
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
                                end_time=end + ":00",
                                classroom=c_room
                            )
                            db.add(schedule)
                        
                        # 스케줄 정보가 없어도 강의실 자체는 강의 정보에 들어갔으므로 통과
                        db.flush() # schedule도 flush를 바로 날려서 확인
                    except Exception as loop_e:
                        import traceback
                        print(f"[{c_no}] Row processing failed:", row)
                        traceback.print_exc()
                        db.rollback()
                        continue
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"PDF 파싱 중 서버 에러: {str(e)}")
    finally:
        os.remove(tmp_path)
        
    return {"message": "PDF 강의 계획서 파싱 및 DB 정보 등록이 성공적으로 완료되었습니다."}


@app.post("/api/v1/admin/courses")
def create_admin_course(req: AdminCourseCreateRequest, db: Session = Depends(get_db)):
    """관리자: 개별 강의 직접 개설 API"""
    import random
    
    # 중복되지 않는 수강번호 생성
    course_no = str(random.randint(100000, 999999))
    while db.query(models.Lecture).filter(models.Lecture.course_no == course_no).first():
        course_no = str(random.randint(100000, 999999))
    
    # 수강구분 매핑
    type_mapping = {
        '전필': '전공필수', '전선': '전공선택', '교필': '교양필수', '교선': '교양선택',
        '교직': '교직', '공통': '공통'
    }
    final_type = req.course_type
    if final_type in type_mapping:
        final_type = type_mapping[final_type]
    elif not final_type or final_type not in ['전공필수', '전공선택', '교양필수', '교양선택', '교직', '공통']:
        final_type = '전공선택'

    new_lecture = models.Lecture(
        course_no=course_no,
        subject=req.subject,
        department=req.department,
        credit=req.credit,
        professor="관리자", 
        type=final_type,
        capacity=req.capacity,
        classroom=req.room,
        version=0
    )
    db.add(new_lecture)
    db.flush()
    
    days_map = {1: '월', 2: '화', 3: '수', 4: '목', 5: '금'}
    for t in req.times:
        day_str = days_map.get(t.day, '월')
        start_hour = 9 + t.time
        start_min = start_hour * 60
        end_min = start_min + 50
        
        new_schedule = models.ScheduleTb(
            lecture_id=new_lecture.lecture_id,
            day_of_week=day_str,
            start_min=start_min,
            end_min=end_min,
            start_time=f"{start_hour:02d}:00:00",
            end_time=f"{start_hour:02d}:50:00",
            classroom=req.room
        )
        db.add(new_schedule)
        
    db.commit()
    return {"message": "강의가 성공적으로 개설되었습니다.", "lecture_id": new_lecture.lecture_id, "course_no": course_no}


@app.delete("/api/v1/admin/courses/{lecture_id}")
def delete_admin_course(lecture_id: int, db: Session = Depends(get_db)):
    """관리자: 개설 강의 삭제 API (404 에러 해결용)"""
    lecture = db.query(models.Lecture).filter(models.Lecture.lecture_id == lecture_id).first()
    if not lecture:
        raise HTTPException(status_code=404, detail="해당 강의를 찾을 수 없습니다.")
    
    # 관련 스케줄 및 신청 내역은 DB FK CASCADE 설정에 따라 자동 삭제됨 (모델 확인 완료)
    db.delete(lecture)
    db.commit()
    return {"message": "강의가 성공적으로 삭제되었습니다."}


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
            new_en = models.Enrollment(user_id=req.user_id, lecture_id=l_id, enroll_status="BASKET")
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

    # 1. RAG 벡터 검색 우선 수행 (업로드된 매뉴얼 내용 확인)
    query_vector = get_embedding(user_msg)
    rag_docs = []
    
    if query_vector:
        # 유사도 검색 (상위 3개)
        rag_docs = db.query(models.RagDocument).order_by(
            models.RagDocument.embedding.l2_distance(query_vector)
        ).limit(3).all()

    # 2. 검색 결과가 있으면 LLM으로 답변 생성
    if rag_docs:
        # LLM에 전달할 문맥(Context)에 메타데이터(출처, 페이지) 추가
        context_parts = []
        for d in rag_docs:
            source = d.doc_metadata.get('source', d.title) if d.doc_metadata else d.title
            page = d.doc_metadata.get('page') if d.doc_metadata else None
            page_info = f" (페이지: {page})" if page else ""
            context_parts.append(f"문서 출처: {source}{page_info}\n내용: {d.content}")
        context_text = "\n\n---\n\n".join(context_parts)

        generated_answer = generate_answer_with_bedrock(user_msg, context_text)
        
        # 답변에 포함될 출처 정보(sources)에도 메타데이터 활용
        sources = []
        for d in rag_docs:
            source = d.doc_metadata.get('source', d.title) if d.doc_metadata else d.title
            page = d.doc_metadata.get('page') if d.doc_metadata else None
            title = f"{source} (p.{page})" if page else source
            sources.append({"title": title, "url": "#rag"})
        source_info = sources

        if generated_answer:
            reply_text = generated_answer
        else:
            # 생성 실패 시 안내 메시지만 반환 (원문 덤프 금지)
            reply_text = "관련 내용을 학사 매뉴얼에서 찾았으나 AI 답변 생성에 실패했습니다. 학사지원팀에 직접 문의하시거나 학사 매뉴얼을 확인해주세요."

    # 3. 검색 결과가 없을 때만 기존 하드코딩 규칙 적용 (Fallback)
    elif "수강신청" in user_msg or "장바구니" in user_msg:
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
        reply_text = "죄송합니다. 질문하신 내용과 관련된 학사 규정을 찾을 수 없습니다. (2026 학생 매뉴얼을 업로드하면 답변이 가능합니다)"

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

    # 관련 user_id만 모아 한 번에 조회 — 루프 내 N+1 제거
    user_ids = list({f.user_id for f in forms if f.user_id})
    user_map = {}
    if user_ids:
        users = db.query(models.User).filter(models.User.user_no.in_(user_ids)).all()
        user_map = {u.user_no: u for u in users}

    result = []
    for f in forms:
        user = user_map.get(f.user_id)
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
async def upload_rag_document(
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """관리자용: AI 지식베이스 문서(PDF/TXT) 업로드 및 청킹"""
    try:
        content = ""
        # 1. 파일 내용 추출
        if file.filename.lower().endswith(".pdf"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(await file.read())
                tmp_path = tmp.name
            
            try:
                with pdfplumber.open(tmp_path) as pdf:
                    page_contents = []
                    for i, page in enumerate(pdf.pages, 1):
                        try:
                            text = page.extract_text() or ""
                            
                            # 표(Table) 추출 후 마크다운 포맷으로 변환
                            tables = page.extract_tables()
                            if tables:
                                text += "\n\n[표 데이터 구조화]\n"
                                for j, table in enumerate(tables, 1):
                                    try:
                                        if not table: continue
                                        # None 값 처리 및 줄바꿈 제거 (한 줄로 평탄화)
                                        clean_table = [[str(cell).replace('\n', '<br>') if cell is not None else "" for cell in row] for row in table]
                                        if not clean_table or not clean_table[0]: continue
                                        
                                        # 첫 번째 행을 헤더로 사용
                                        headers = clean_table[0]
                                        md = "| " + " | ".join(headers) + " |\n"
                                        md += "| " + " | ".join(["---"] * len(headers)) + " |\n"
                                        for row in clean_table[1:]:
                                            md += "| " + " | ".join(row) + " |\n"
                                        text += md + "\n"
                                    except Exception as table_e:
                                        logger.warning(f"PDF '{file.filename}'의 Page {i}, Table {j} 처리 중 오류: {table_e}")
                                        continue # 테이블 처리 실패 시 다음 테이블로
                            page_contents.append(text)
                        except Exception as page_e:
                            logger.warning(f"PDF '{file.filename}'의 Page {i} 처리 중 오류: {page_e}")
                            continue # 페이지 처리 실패 시 다음 페이지로
                    content = "\n\n".join(page_contents)
                    
                    # [디버깅] 파싱된 텍스트 길이 및 앞부분 로그 출력
                    logger.info(f"PDF 파싱 결과: 총 {len(content)}자 추출됨.")
                    if len(content) > 0:
                        logger.info(f"내용 미리보기: {content[:200]}...")
                    else:
                        logger.warning("⚠️ PDF 내용이 비어있습니다. (이미지 스캔본일 가능성 높음)")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        else:
            content = (await file.read()).decode("utf-8", errors="ignore")

        # 2. 내용 검증 (빈 파일이면 DB 저장 차단)
        if not content.strip():
            raise HTTPException(status_code=400, detail="파일에서 텍스트를 추출할 수 없습니다. (텍스트 복사가 가능한 PDF인지 확인해주세요)")

        # 3. Chunking 개선 (단순 글자 수 자르기 -> 문단/표 단위 보존 시도)
        # LangChain의 RecursiveCharacterTextSplitter와 유사한 로직을 간단히 구현
        chunks = []
        current_chunk = ""
        # 문단(\n\n) 단위로 먼저 분리하여 의미 덩어리를 유지
        paragraphs = content.split('\n\n')
        
        for p in paragraphs:
            if len(current_chunk) + len(p) < 800:  # 800자 미만이면 붙이기
                current_chunk += p + "\n\n"
            else:
                chunks.append(current_chunk.strip())
                current_chunk = p + "\n\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())

        # 3. 각 청크별 임베딩 생성 및 DB 저장 (Vector DB 역할)
        for i, chunk in enumerate(chunks):
            if not chunk.strip(): continue
            vector = get_embedding(chunk)
            if vector:
                new_doc = models.RagDocument(
                    title=f"{title} (Part {i+1})",
                    content=chunk,
                    embedding=vector
                )
                db.add(new_doc)
        
        db.commit()

        return {"message": f"'{title}' 문서가 {len(chunks)}개의 청크로 분할되어 벡터 데이터베이스에 저장되었습니다."}
    except Exception as e:
        logger.error(f"RAG Upload Failed: {e}")
        raise HTTPException(status_code=500, detail="문서 처리 중 오류가 발생했습니다.")


@app.post("/api/v1/admin/rag/load-csv-data")
def load_csv_data(db: Session = Depends(get_db)):
    """
    관리자용: backend/pdf/ 폴더의 CSV 형식 txt 파일 4개를
    (enroll.txt, grade.txt, schedule_2026.txt, score.txt)
    자연어 문장으로 변환하여 RAG 벡터 DB에 일괄 적재합니다.
    이미 같은 title이 존재하면 건너뜁니다(중복 방지).
    """
    base_dir = os.path.dirname(__file__)
    pdf_dir  = os.path.join(base_dir, "pdf")

    def csv_rows(filename: str):
        path = os.path.join(pdf_dir, filename)
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {filename}")
        with open(path, encoding="utf-8") as f:
            return list(csv.DictReader(f))

    results = {}

    # ── 1. enroll.txt : 수강신청 학점 기준 ──
    title_prefix = "수강신청 학점 기준"
    existing = {r.title for r in db.query(models.RagDocument.title).filter(
        models.RagDocument.title.like(f"{title_prefix}%")).all()}
    rows = csv_rows("enroll.txt")
    count = 0
    for i, row in enumerate(rows):
        구분 = row.get("구분","").strip()
        연간 = row.get("수강신청학점(연간)","").strip()
        학기 = row.get("수강신청학점(학기)","").strip()
        비고 = row.get("비고","").strip()
        parts = []
        if 연간: parts.append(f"연간 최대 {연간}학점")
        if 학기: parts.append(f"학기당 최대 {학기}학점")
        if 비고: parts.append(f"비고: {비고}")
        chunk = f"{구분}의 수강신청 학점 기준 — " + ", ".join(parts) + "."
        doc_title = f"{title_prefix} ({i+1})"
        if doc_title in existing: continue
        vec = get_embedding(chunk)
        if vec:
            db.add(models.RagDocument(title=doc_title, content=chunk, embedding=vec))
            count += 1
    results["enroll.txt"] = count

    # ── 2. grade.txt : 학과별 졸업 학점 기준 ──
    title_prefix = "학과별 졸업학점 기준"
    existing = {r.title for r in db.query(models.RagDocument.title).filter(
        models.RagDocument.title.like(f"{title_prefix}%")).all()}
    rows = csv_rows("grade.txt")
    count = 0
    for i, row in enumerate(rows):
        대학   = row.get("대학","").strip()
        모집   = row.get("모집단위명","").strip()
        학과   = row.get("학과(전공)","").strip()
        교양공 = row.get("교양공통(이상)","").strip()
        교양균 = row.get("교양균형(이상)","").strip()
        교양계 = row.get("교양계","").strip()
        단일   = row.get("단일·심화전공자","").strip()
        복수   = row.get("복수전공자","").strip()
        졸업   = row.get("졸업학점","").strip()
        chunk = (f"{대학} {모집} {학과}의 졸업 요건: "
                 f"교양공통 {교양공}학점 이상, 교양균형 {교양균}학점 이상, 교양 합계 {교양계}학점, "
                 f"단일·심화전공자 전공 {단일}학점, 복수전공자 전공 {복수}학점, "
                 f"총 졸업학점 {졸업}학점.")
        doc_title = f"{title_prefix} ({i+1})"
        if doc_title in existing: continue
        vec = get_embedding(chunk)
        if vec:
            db.add(models.RagDocument(title=doc_title, content=chunk, embedding=vec))
            count += 1
    results["grade.txt"] = count

    # ── 3. schedule_2026.txt : 2026학년도 학사일정 ──
    title_prefix = "2026학년도 학사일정"
    existing = {r.title for r in db.query(models.RagDocument.title).filter(
        models.RagDocument.title.like(f"{title_prefix}%")).all()}
    rows = csv_rows("schedule_2026.txt")
    # 학사일정은 행이 적으므로 전체를 하나의 청크로 묶음
    lines = [f"{r.get('월','').strip()} {r.get('일자(요일)','').strip()}: {r.get('학사내용','').strip()}"
             for r in rows if r.get('학사내용','').strip()]
    chunk_size = 15  # 15행씩 한 청크
    count = 0
    for i in range(0, len(lines), chunk_size):
        chunk = "\n".join(lines[i:i+chunk_size])
        doc_title = f"{title_prefix} ({i//chunk_size+1})"
        if doc_title in existing: continue
        vec = get_embedding(chunk)
        if vec:
            db.add(models.RagDocument(title=doc_title, content=chunk, embedding=vec))
            count += 1
    results["schedule_2026.txt"] = count

    # ── 4. score.txt : 성적 등급 기준 ──
    title_prefix = "성적 등급 기준"
    existing = {r.title for r in db.query(models.RagDocument.title).filter(
        models.RagDocument.title.like(f"{title_prefix}%")).all()}
    rows = csv_rows("score.txt")
    lines = []
    for row in rows:
        등급 = row.get("등급","").strip()
        평점 = row.get("평점","").strip()
        범위 = row.get("실점(범위)","").strip()
        if 등급:
            lines.append(f"{등급}등급: 평점 {평점}점, 실점 {범위}점")
    chunk = "성적 등급 및 평점 기준표.\n" + "\n".join(lines)
    doc_title = f"{title_prefix} (1)"
    count = 0
    if doc_title not in existing:
        vec = get_embedding(chunk)
        if vec:
            db.add(models.RagDocument(title=doc_title, content=chunk, embedding=vec))
            count += 1
    results["score.txt"] = count

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB 저장 중 오류: {str(e)}")

    total = sum(results.values())
    logger.info(f"CSV RAG 적재 완료: {results}")
    return {
        "message": f"총 {total}개의 청크가 RAG DB에 저장되었습니다.",
        "detail": results
    }


@app.post("/api/v1/admin/rag/load-manual")
def load_manual_from_local(db: Session = Depends(get_db)):
    """
    관리자용: 서버 로컬에 위치한 '@2026_2026_student_menual.pdf' 파일을 읽어
    관리자용: 서버 로컬에 위치한 '2026_student_menual.pdf' 파일을 읽어
    자동으로 텍스트를 추출하고 임베딩하여 RAG DB에 적재합니다.
    """
    filename = "@2026_2026_student_menual.pdf"
    filename = "2026_student_menual.pdf"
    
    # 1. 파일 경로 탐색 (우선순위: backend/pdf > 상위/pdf)
    base_dir = os.path.dirname(__file__)
    candidates = [
        os.path.join(base_dir, "pdf", filename),      # 1순위: backend/pdf (배포 환경 권장)
        os.path.join(base_dir, "..", "pdf", filename) # 2순위: mugang_aws/pdf (기존 로컬 환경)
    ]
    
    file_path = None
    for path in candidates:
        if os.path.exists(path):
            file_path = path
            break
            
    if not file_path:
        raise HTTPException(status_code=404, detail=f"서버에서 '{filename}' 파일을 찾을 수 없습니다. 'backend/pdf' 폴더에 파일을 넣어주세요.")

    # 2. 파싱 및 텍스트 추출
    content = ""
    try:
        logger.info(f"'{file_path}' 파일 파싱을 시작합니다...")
        with pdfplumber.open(file_path) as pdf:
            page_contents = []
            for i, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                page_contents.append(text)
            content = "\n\n".join(page_contents)
    except Exception as e:
        logger.error(f"PDF 파싱 중 심각한 오류 발생: {e}", exc_info=True)
        logger.error(f"PDF Parsing Error: {e}")
        raise HTTPException(status_code=500, detail=f"PDF 파싱 실패: {str(e)}")

    if not content.strip():
        raise HTTPException(status_code=400, detail="PDF에서 텍스트를 추출할 수 없습니다.")

    # 3. 청킹 (Chunking) 및 임베딩
    logger.info(f"총 {len(content)}자의 텍스트를 추출했습니다. 청킹 및 임베딩을 시작합니다.")
    chunks = []
    current_chunk = ""
    for p in content.split('\n\n'):
        if len(current_chunk) + len(p) < 800:
            current_chunk += p + "\n\n"
        else:
            chunks.append(current_chunk.strip())
            current_chunk = p + "\n\n"
    if current_chunk:
        chunks.append(current_chunk.strip())

    title = "2026 학생 매뉴얼"
    count = 0
    for i, chunk in enumerate(chunks):
        logger.info(f"청크 {i+1}/{len(chunks)} 임베딩 및 저장 중...")
        if not chunk.strip(): continue
        vector = get_embedding(chunk)
        if vector:
            # doc_metadata가 모델에 정의되어 있다면 활용 가능
            new_doc = models.RagDocument(
                title=f"{title} (Part {i+1})",
                content=chunk,
                embedding=vector
            )
            db.add(new_doc)
            count += 1
    try:
        db.commit()
        logger.info(f"총 {count}개의 청크를 DB에 성공적으로 커밋했습니다.")
    except Exception as e:
        logger.error(f"DB 커밋 중 오류 발생: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"임베딩 데이터 저장 중 DB 오류가 발생했습니다: {str(e)}")
    
    return {
        "message": "PDF 임베딩 및 DB 저장이 완료되었습니다.",
        "file_name": filename,
        "file_path": os.path.abspath(file_path),
        "total_characters": len(content),
        "total_chunks_created": len(chunks),
        "db_saved_count": count
    }


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


# --- 사용자 정보 조회 ---
@app.get("/api/v1/users/{user_id}")
def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.user_no == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return {
        "user_id": user.user_no,
        "name": user.user_name,
        "student_id": user.loginid,
        "grade": user.grade,
        "college": user.depart.college if user.depart else None,
        "depart": user.depart.depart if user.depart else None,
        "status": user.user_status,
        "email": user.email,
        "phone": user.phone,
        "role": user.role
    }


# --- 사용자 정보 수정 ---
@app.put("/api/v1/users/{user_id}")
def update_user_profile(user_id: int, req: UserUpdateRequest, db: Session = Depends(get_db)):
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
def enrollment_access_check(user_id: int, lecture_id: Optional[int] = None, db: Session = Depends(get_db)):
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

# --- 서버 시간 API ---

@app.get("/api/time")
def get_server_time(db: Session = Depends(get_db)):
    """외부 서버 시간 확인 사이트(네이비즘 등)가 참조하는 서버 시간 엔드포인트.
    SystemConfig에 저장된 오프셋(ms)을 적용한 UTC 기준 Unix 타임스탬프(ms) 반환."""
    offset_cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == "server_time_offset_ms").first()
    offset_ms = int(offset_cfg.value) if offset_cfg else 0
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000) + offset_ms
    return {"timestamp_ms": now_ms, "offset_ms": offset_ms}


@app.get("/api/v1/admin/server-time")
def get_server_time_config(db: Session = Depends(get_db)):
    """관리자용: 현재 서버 시간 + 오프셋 설정 조회"""
    offset_cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == "server_time_offset_ms").first()
    offset_ms = int(offset_cfg.value) if offset_cfg else 0
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000) + offset_ms
    return {"timestamp_ms": now_ms, "offset_ms": offset_ms}


class ServerTimeOffsetRequest(BaseModel):
    offset_ms: int  # 조정할 오프셋 (밀리초, 음수 가능)


@app.post("/api/v1/admin/server-time-offset")
def set_server_time_offset(req: ServerTimeOffsetRequest, db: Session = Depends(get_db)):
    """관리자용: 서버 시간 오프셋 설정 (ms 단위)"""
    cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == "server_time_offset_ms").first()
    if cfg:
        cfg.value = str(req.offset_ms)
    else:
        db.add(models.SystemConfig(key="server_time_offset_ms", value=str(req.offset_ms)))
    db.commit()
    return {"message": "서버 시간 오프셋이 설정되었습니다.", "offset_ms": req.offset_ms}


# --- 시스템 상태 캐시 변수 (메모리 상주) ---
_cached_system_status = None
_last_status_update = 0

@app.get("/api/v1/admin/system-status")
def get_system_status(db: Session = Depends(get_db)):
    """관리자용: 시스템 모니터링 데이터 (초극한 최적화: 1 RTT + 캐시)"""
    global _cached_system_status, _last_status_update
    
    now_ts = time.time()
    # 3초 캐시: 초고속 응답
    if _cached_system_status and (now_ts - _last_status_update < 3):
        return _cached_system_status

    t0 = time.time()
    try:
        # PostgreSQL의 JSON 기능을 활용해 메트릭, 최근 내역, 일정을 한 번의 DB 왕복으로 모두 가져옴
        super_query = text("""
            WITH stats AS (
                SELECT 
                    (SELECT count(*) FROM enroll_tb WHERE enroll_status = 'COMPLETED') as completed,
                    (SELECT count(*) FROM enroll_tb WHERE enroll_status = 'BASKET') as basket,
                    (SELECT count(*) FROM enroll_tb WHERE enroll_status = 'CANCELED') as canceled,
                    (SELECT count(*) FROM waitlist_tb WHERE status = 'WAITING') as waiting,
                    (SELECT count(*) FROM waitlist_tb WHERE status = 'PROMOTED') as promoted,
                    (SELECT count(*) FROM user_tb WHERE role = 'STUDENT') as students,
                    (SELECT count(*) FROM lecture_tb) as lectures,
                    (SELECT value FROM system_config_tb WHERE key = 'server_time_offset_ms' LIMIT 1) as offset_ms
            ),
            recent AS (
                SELECT array_to_json(array_agg(t)) as list
                FROM (
                    SELECT enroll_no, loginid as user_id, lecture_id, enroll_status as status, 
                           to_char(createdat, 'YYYY-MM-DD"T"HH24:MI:SS"Z"') as created_at
                    FROM enroll_tb
                    ORDER BY createdat DESC
                    LIMIT 5
                ) t
            ),
            active AS (
                SELECT row_to_json(s) as info
                FROM (
                    SELECT day_number, restriction_type, 
                           to_char(close_datetime, 'YYYY-MM-DD"T"HH24:MI:SS"Z"') as close_datetime
                    FROM enroll_schedule_tb
                    WHERE is_active = true 
                      AND open_datetime <= (now() AT TIME ZONE 'UTC')
                      AND close_datetime >= (now() AT TIME ZONE 'UTC')
                    ORDER BY day_number ASC
                    LIMIT 1
                ) s
            )
            SELECT stats.*, recent.list as recent_list, active.info as active_info
            FROM stats, recent, active;
        """)
        
        row = db.execute(super_query).fetchone()
        db_latency_ms = round((time.time() - t0) * 1000, 1)

        # JSON 파싱 및 결과 구성
        recent_enrollments = row.recent_list if row.recent_list else []
        active_day = row.active_info # 이미 dict 형태
        offset_ms = int(row.offset_ms) if row.offset_ms else 0
        server_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        result = {
            "db_status": "정상",
            "db_latency_ms": db_latency_ms,
            "server_time_ms": server_time_ms + offset_ms,
            "offset_ms": offset_ms,
            "enrollment_active": active_day is not None,
            "active_day": active_day,
            "enrollments": {
                "completed": row.completed,
                "basket": row.basket,
                "canceled": row.canceled
            },
            "waitlist": {
                "waiting": row.waiting,
                "promoted": row.promoted
            },
            "total_students": row.students,
            "total_lectures": row.lectures,
            "recent_enrollments": recent_enrollments
        }
        
        _cached_system_status = result
        _last_status_update = now_ts
        return result

    except Exception as e:
        logger.error(f"Super status error: {e}")
        db.rollback()
        return {"db_status": "오류", "db_latency_ms": -1}



# --- 임시 DB 보정 엔드포인트 (1회 사용 후 삭제 예정) ---
@app.post("/api/v1/admin/fix-users")
def fix_users_once(secret: str, db: Session = Depends(get_db)):
    """Admin-0012 이름 수정 및 22517717 학과 연결 (임시 엔드포인트)"""
    if secret != "mugang-fix-2026":
        raise HTTPException(status_code=403, detail="Forbidden")

    results = []

    # 1. Admin-0012 이름 수정
    admin = db.query(models.User).filter(models.User.loginid == "Admin-0012").first()
    if admin:
        admin.user_name = "임무강"
        results.append(f"Admin-0012 이름 → 임무강")
    else:
        results.append("Admin-0012 없음")

    # 2. 22517717 학과 연결
    student = db.query(models.User).filter(models.User.loginid == "22517717").first()
    if student:
        dept = db.query(models.Depart).filter(
            models.Depart.depart.ilike("%글로벌ICT%")
        ).first()
        if not dept:
            dept = db.query(models.Depart).filter(
                models.Depart.college.ilike("%IT%")
            ).first()
        if dept:
            student.dept_no = dept.dept_no
            results.append(f"22517717 dept_no={dept.dept_no} ({dept.college} / {dept.depart})")
        else:
            it_depts = db.query(models.Depart).filter(
                models.Depart.college.ilike("%IT%") | models.Depart.depart.ilike("%ICT%")
            ).all()
            results.append(f"학과 못찾음. IT계열: {[d.depart for d in it_depts]}")
    else:
        results.append("22517717 없음")

    db.commit()
    return {"results": results}


# --- 프론트엔드 정적 파일 서빙 ---
# (API 경로를 먼저 정의한 후 마지막에 마운트해야 API가 우선순위를 가집니다)
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)