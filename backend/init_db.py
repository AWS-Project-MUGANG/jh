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
    if not db.query(models.User).filter(models.User.student_id == student_id).first():
        hashed_pw = get_password_hash("1234")
        student = models.User(
            student_id=student_id,
            password_hash=hashed_pw,
            name="임정현",
            major="아동가족복지학과",
            degree_level="undergraduate",
            status="enrolled"
        )
        db.add(student)
        print(f"학생 계정 생성 완료: {student_id} / 1234")
    else:
        print(f"학생 계정 이미 존재: {student_id}")

    # 2. 관리자/교수 계정 생성
    admin_id = "Admin-0012"
    if not db.query(models.User).filter(models.User.student_id == admin_id).first():
        hashed_pw = get_password_hash("1234")
        admin = models.User(
            student_id=admin_id,
            password_hash=hashed_pw,
            name="김무강 교수",
            major="사회과학대학",
            degree_level="professor",
            status="active"
        )
        db.add(admin)
        print(f"관리자 계정 생성 완료: {admin_id} / 1234")
    else:
        print(f"관리자 계정 이미 존재: {admin_id}")

    db.commit()
    db.close()

if __name__ == "__main__":
    init_db()
