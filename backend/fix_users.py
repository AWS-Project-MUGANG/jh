"""
사용자 프로필 데이터 보정 스크립트
- Admin-0012: 이름 "임무강"으로 수정
- 22517717 (임정현): IT·공과대학 / 글로벌ICT전공 dept_no 연결
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
import models


def fix_users():
    db = SessionLocal()
    try:
        # 1. Admin-0012 이름 수정
        admin = db.query(models.User).filter(models.User.loginid == "Admin-0012").first()
        if admin:
            admin.user_name = "임무강"
            print(f"[OK] Admin-0012 이름 → 임무강")
        else:
            print("[SKIP] Admin-0012 계정 없음")

        # 2. 학생 22517717에 IT·공과대학 / 글로벌ICT전공 연결
        student = db.query(models.User).filter(models.User.loginid == "22517717").first()
        if student:
            dept = (
                db.query(models.Depart)
                .filter(
                    models.Depart.college == "IT·공과대학",
                    models.Depart.depart == "글로벌ICT전공",
                )
                .first()
            )
            if dept:
                student.dept_no = dept.dept_no
                print(f"[OK] 22517717 dept_no → {dept.dept_no} (IT·공과대학 / 글로벌ICT전공)")
            else:
                # 유사 이름으로 재시도
                dept = (
                    db.query(models.Depart)
                    .filter(models.Depart.depart.ilike("%글로벌ICT%"))
                    .first()
                )
                if dept:
                    student.dept_no = dept.dept_no
                    print(f"[OK] 22517717 dept_no → {dept.dept_no} ({dept.college} / {dept.depart})")
                else:
                    print("[WARN] 글로벌ICT전공 학과를 DB에서 찾지 못했습니다.")
                    # 등록된 IT·공과대학 학과 목록 출력
                    it_depts = db.query(models.Depart).filter(
                        models.Depart.college.ilike("%IT%")
                    ).all()
                    if it_depts:
                        print("  → IT 계열 학과 목록:")
                        for d in it_depts:
                            print(f"     dept_no={d.dept_no}  {d.college} / {d.depart}")
        else:
            print("[SKIP] 22517717 계정 없음")

        db.commit()
        print("\n완료: DB 커밋 성공")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    fix_users()
