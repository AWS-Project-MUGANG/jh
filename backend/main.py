import logging
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title="무강대학교 AI 학사행정 서비스",
    description="학생 맞춤형 학사 서비스 (수강신청, 시간표, RAG 기반 질의응답)",
    version="1.0.0"
)

# CORS 미들웨어 적용 (프론트엔드 통신용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 개발 환경에서는 모두 허용, 운영 환경에서는 프론트 도메인만 허용하도록 변경
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Dummy Data Models ----
class LoginRequest(BaseModel):
    student_id: str
    password: str

class ChatRequest(BaseModel):
    session_id: str
    message: str

class FormRequest(BaseModel):
    form_type: str
    reason: str

# ---- API 라우터 (뼈대) ----

@app.get("/")
def read_root():
    return {"message": "무강대학교 AI 학사행정 API 서버가 실행 중입니다."}

@app.post("/api/v1/auth/login")
def login(req: LoginRequest):
    """
    학생 학번(사번)을 통한 SSO 형태의 로그인 처리
    """
    logger.info(f"로그인 시도: {req.student_id}")
    # TODO: 실제 DB 및 인증 로직 연동 필요
    if req.student_id and req.password:
        return {"access_token": "fake_jwt_token_12345", "user_id": "test_uuid_001"}
    raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 잘못되었습니다.")

@app.post("/api/v1/chat/ask")
def chat_ask(req: ChatRequest):
    """
    AI 학사 행정 상담 (RAG 기반 응답 로직 연결부)
    """
    # TODO: Pinecone / LLM(Bedrock 등) 연결 후 답변 생성 로직 연동
    logger.info(f"채팅 질의 수신 - session: {req.session_id}, msg: {req.message}")
    return {
        "reply": f"네, 질문하신 내용 '{req.message}'에 대해 확인 중입니다. (RAG 연동 전 기본 응답)",
        "sources": [{"title": "학칙 임시", "url": "#"}]
    }

@app.get("/api/v1/users/{user_id}/schedules")
def get_user_schedules(user_id: str, month: Optional[str] = None):
    """
    사용자의 개인/공통 학사 일정 조회
    """
    # TODO: 데이터베이스(RDS)에서 사용자별 일정 조회 로직 연동
    return {
        "schedules": [
            {"date": "2024-05-15T09:00:00", "title": "1학기 수강신청 시작"},
            {"date": "2024-05-20T18:00:00", "title": "1학기 시간표 최종 확정"}
        ]
    }

@app.post("/api/v1/forms/generate")
def generate_form(req: FormRequest):
    """
    문서 초안 자동 생성 (휴학 등)
    """
    # TODO: AI 문서 자동 완성 기능 연동
    return {
        "form_id": "draft_001",
        "status": "draft",
        "preview_json": {"applicant": "test", "reason": req.reason}
    }

if __name__ == "__main__":
    import uvicorn
    # uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    pass
