import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import engine
from sqlalchemy import text

def add_columns():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE enrollments ADD COLUMN status VARCHAR(20) DEFAULT 'cart'"))
            conn.execute(text("ALTER TABLE enrollments ADD COLUMN credits INTEGER DEFAULT 3"))
            conn.commit()
            print("성공적으로 컬럼을 추가했습니다.")
        except Exception as e:
            print(f"이미 컬럼이 존재하거나 에러가 발생했습니다: {e}")

if __name__ == "__main__":
    add_columns()
