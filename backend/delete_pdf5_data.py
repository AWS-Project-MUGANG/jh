"""5번 PDF로 들어간 lecture_tb 데이터 삭제 (course_no 기준)"""
import json
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

# course_no 목록 로드
with open(r"C:\Users\junse\Desktop\vscode\team-project\mugang_aws\tmp_course_nos.json", encoding='utf-8') as f:
    course_nos = json.load(f)

engine = create_engine(DATABASE_URL)

with engine.begin() as conn:
    # schedule_tb는 CASCADE로 자동 삭제됨 (FK ondelete=CASCADE)
    result = conn.execute(
        text("DELETE FROM lecture_tb WHERE course_no = ANY(:nos)"),
        {"nos": course_nos}
    )
    deleted = result.rowcount

print(f"✅ lecture_tb에서 {deleted}개 강의 삭제 완료 (연관 schedule_tb도 CASCADE 삭제)")
