import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import engine, SessionLocal
import models
from main import get_password_hash

def init_db():
    db = SessionLocal()
    
    # 1. 학생 계정 생성
    student_id = "22517717"
    if not db.query(models.User).filter(models.User.loginid == student_id).first():
        hashed_pw = get_password_hash("1234")
        student = models.User(
            loginid=student_id,
            password=hashed_pw,
            user_name="임정현",
            role="STUDENT",
            user_status="재학"
        )
        db.add(student)
        print(f"학생 계정 생성 완료: {student_id} / 1234")
    else:
        print(f"학생 계정 이미 존재: {student_id}")

    # 2. 관리자/교수 계정 생성
    admin_id = "Admin-0012"
    if not db.query(models.User).filter(models.User.loginid == admin_id).first():
        hashed_pw = get_password_hash("1234")
        admin = models.User(
            loginid=admin_id,
            password=hashed_pw,
            user_name="임무강",
            role="STAFF",
            user_status="재직"
        )
        db.add(admin)
        print(f"관리자 계정 생성 완료: {admin_id} / 1234")
    else:
        print(f"관리자 계정 이미 존재: {admin_id}")

    db.commit()
    db.close()

if __name__ == "__main__":
    init_db()
