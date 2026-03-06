import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# .env 파일 로드 (환경변수)
load_dotenv()

# PostgreSQL DB URL (예: postgresql://user:password@localhost/mugang_db)
# 로컬 테스트를 위해 임시 sqlite 사용 가능, 가이드라인에 따라 PostgreSQL 주소 입력 필요
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

_is_sqlite = "sqlite" in SQLALCHEMY_DATABASE_URL

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    # PostgreSQL 커넥션 풀 설정 (sqlite는 풀 불필요)
    **({} if _is_sqlite else {
        "pool_size": 10,        # 상시 유지할 연결 수 (t3.medium 기준 적정값)
        "max_overflow": 20,     # 피크 시 최대 추가 연결 수
        "pool_pre_ping": True,  # 유휴 연결 유효성 검사 (RDS 재시작 후 끊김 방지)
        "pool_recycle": 1800,   # 30분마다 연결 갱신 (RDS idle timeout 대응)
    })
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# DB 세션 의존성 주입용 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
