import sys
import os

# 현재 디렉토리를 sys.path에 추가하여 모듈을 임포트할 수 있게 함
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from sqlalchemy import text
from database import engine

def upgrade():
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'student'"))
            print("Successfully added 'role' column to 'users' table.")
        except Exception as e:
            print("Error or column already exists:", e)

if __name__ == "__main__":
    upgrade()
