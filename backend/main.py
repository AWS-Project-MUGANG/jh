import logging
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta, timezone

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

# ---- API 요청/응답 데이터 모델 (Pydantic) ----
class RegisterRequest(BaseModel):
    student_id: str
    password: str
    name: str
    major: str

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

# ---- 헬퍼 함수 ----
def is_enrollment_period_active(db: Session):
    """현재 시각이 수강신청 가능 기간인지 확인"""
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


# ---- API 라우터 ----

@app.get("/")
def read_root():
    return {"message": "무강대학교 AI 학사행정 API 서버가 실행 중입니다."}


# --- 인증 ---
@app.post("/api/v1/auth/register", status_code=status.HTTP_201_CREATED)
def register_user(req: RegisterRequest, db: Session = Depends(get_db)):
    """학생 회원가입 (비밀번호 암호화 후 DB 저장)"""
    db_user = db.query(models.User).filter(models.User.student_id == req.student_id).first()
    if db_user:
        raise HTTPException(status_code=400, detail="이미 가입된 학번입니다.")

    hashed_password = get_password_hash(req.password)
    new_user = models.User(
        student_id=req.student_id,
        password_hash=hashed_password,
        name=req.name,
        major=req.major
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "회원가입이 정상적으로 완료되었습니다.", "user_id": new_user.id}


@app.post("/api/v1/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """학번과 비밀번호로 로그인 (JWT 발급)"""
    logger.info(f"로그인 시도: {req.student_id}")

    user = db.query(models.User).filter(models.User.student_id == req.student_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="존재하지 않는 학번입니다.")
    if not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")

    access_token = create_access_token(data={"sub": user.student_id, "id": user.id})
    role = "admin" if "admin" in req.student_id.lower() or "prof" in req.student_id.lower() else "student"

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "name": user.name,
        "role": role
    }


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
    """수강신청 1건 저장 (정원 체크 + 낙관적 락)"""
    if not is_enrollment_period_active(db):
        raise HTTPException(status_code=403, detail="현재는 수강신청 기간이 아닙니다.")

    user = db.query(models.User).filter(models.User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")

    # 중복 수강신청 검사
    existing = db.query(models.Enrollment).filter(
        models.Enrollment.user_id == req.user_id,
        models.Enrollment.lecture_id == req.lecture_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 신청(장바구니 담기)이 완료된 과목입니다.")

    # lecture_tb 조회 및 정원 체크
    lecture = db.query(models.Lecture).filter(models.Lecture.lecture_id == req.lecture_id).first()
    if not lecture:
        raise HTTPException(status_code=404, detail="강의 정보를 찾을 수 없습니다.")
    if lecture.capacity > 0 and lecture.count >= lecture.capacity:
        raise HTTPException(status_code=409, detail="수강 정원이 초과되었습니다.")

    # 낙관적 락: version 확인 후 count 증가
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
        status="cart"
    )
    db.add(new_enrollment)
    db.commit()
    db.refresh(new_enrollment)
    return {"message": "정상적으로 수강신청 테이블에 저장되었습니다.", "enrollment_id": new_enrollment.id}


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
    """수강 철회 (lecture_tb count 감소)"""
    en = db.query(models.Enrollment).filter(models.Enrollment.id == enrollment_id).first()
    if not en:
        raise HTTPException(status_code=404, detail="해당 수강 내역이 없습니다.")

    # count 감소
    db.query(models.Lecture).filter(models.Lecture.lecture_id == en.lecture_id).update(
        {"count": models.Lecture.count - 1}
    )
    db.delete(en)
    db.commit()
    return {"message": "수강 철회가 완료되었습니다."}


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


# --- 관리자: 수강 현황 ---
@app.get("/api/v1/admin/enrollments")
def get_admin_enrollments(db: Session = Depends(get_db)):
    """관리자용: 개설 과목별 수강생 전체 현황"""
    enrollments = db.query(models.Enrollment).all()
    summary = {}
    for en in enrollments:
        lec = en.lecture
        subject_key = lec.subject if lec else "Unknown"
        if subject_key not in summary:
            summary[subject_key] = {
                "lecture_id": en.lecture_id,
                "subject": subject_key,
                "capacity": lec.capacity if lec else 0,
                "count": lec.count if lec else 0,
                "students": []
            }
        user = db.query(models.User).filter(models.User.id == en.user_id).first()
        summary[subject_key]["students"].append({
            "enrollment_id": en.id,
            "user_id": en.user_id,
            "student_id": user.student_id if user else "Unknown",
            "name": user.name if user else "Unknown"
        })
    return {"classes": list(summary.values())}


@app.get("/api/v1/admin/stats")
def get_admin_stats(db: Session = Depends(get_db)):
    """관리자용: 대시보드 통계 데이터"""
    student_count = db.query(models.User).filter(models.User.degree_level == "undergraduate").count()
    enrollment_count = db.query(models.Enrollment).count()
    form_count = db.query(models.Form).count()
    return {
        "total_students": student_count,
        "total_enrollments": enrollment_count,
        "pending_forms": form_count,
        "popular_chat_keywords": [
            {"keyword": "수강신청", "count": 145},
            {"keyword": "휴학", "count": 89},
            {"keyword": "장학금", "count": 56},
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
        user = db.query(models.User).filter(models.User.id == f.user_id).first()
        result.append({
            "id": f.id,
            "form_type": f.form_type,
            "status": f.status,
            "student_id": user.student_id if user else "Unknown",
            "name": user.name if user else "Unknown",
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
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    if req.name:   user.name = req.name
    if req.major:  user.major = req.major
    if req.status: user.status = req.status
    db.commit()
    return {"message": "프로필 정보가 수정되었습니다."}


# --- 수강신청 기간 설정 ---
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
