import re
from database import SessionLocal, engine
import models

# 2026 학과 안내서에서 추출한 단과대학-학과 원본 데이터
# 형식: (단과대학, [학과/학부(전공1, 전공2), ...])
COLLEGE_DATA = [
    ("자유전공학부", [
        "자유전공학부",
    ]),
    ("공공인재대학", [
        "공공안전학부(소방·행정학전공)",
        "공공안전학부(공직법무전공)",
        "경찰학부(경찰행정학전공, 자치경찰학전공)",
        "국방군사학과",
        "부동산지적학과",
    ]),
    ("글로벌경영대학", [
        "경영학부(경영학전공)",
        "경영학부(회계학전공)",
        "경제금융통상학과",
        "호텔관광경영학부(관광항공경영전공)",
        "호텔관광경영학부(호텔관광외식서비스전공)",
        "일본어일본학과",
    ]),
    ("사회과학대학", [
        "사회복지학과",
        "청소년상담복지학과",
        "아동가정복지학과",
        "평생교육심리복지학과",
        "미디어커뮤니케이션학부(영상콘텐츠전공)",
        "미디어커뮤니케이션학부(광고PR전공)",
        "문헌정보학과",
        "심리학과",
    ]),
    ("보건바이오대학", [
        "보건의료학과",
        "응급구조학과",
        "동물자원학과",
        "반려동물산업학과",
        "스마트원예학과",
        "식품가공학과",
        "난임의료산업학과",
    ]),
    ("IT·공과대학", [
        "건축공학과",
        "소방안전방재학과",
        "기계자동차공학부(기계공학전공, 미래자동차공학전공)",
        "식품영양학과",
        "조경산림정원학과",
        "친환경에너지학과",
        "전자전기공학부(반도체전자공학전공)",
        "전자전기공학부(전기공학전공)",
        "컴퓨터정보공학부(컴퓨터공학전공)",
        "컴퓨터정보공학부(컴퓨터소프트웨어전공)",
        "컴퓨터정보공학부(사이버보안전공)",
    ]),
    ("디자인예술대학", [
        "웹툰영상애니메이션학부(영상애니메이션전공, 웹툰전공)",
        "시각디자인융합학부(시각디자인전공)",
        "시각디자인융합학부(서비스마케팅디자인전공)",
        "산업디자인학과",
        "패션디자인학과",
        "뷰티학부(헤어디자인전공, 메이크업피부전공)",
        "실내건축디자인학과",
        "게임학과",
    ]),
    ("사범대학", [
        "국어교육과",
        "영어교육과",
        "역사교육과",
        "일반사회교육과",
        "지리교육과",
        "유아교육과",
        "특수교육과",
        "초등특수교육과",
        "유아특수교육과",
        "수학교육과",
        "물리교육과",
        "화학교육과",
        "생물교육과",
        "지구과학교육과",
    ]),
    ("재활과학대학", [
        "물리치료학과",
        "작업치료학과",
        "언어치료학과",
        "재활상담심리치료학과",
        "의료재활학과",
        "재활건강증진학과",
        "특수창의융합학과",
    ]),
    ("간호대학", [
        "간호학과",
    ]),
    ("체육레저학부", [
        "체육학과",
        "스포츠레저학과",
        "스포츠헬스케어학과",
    ]),
    ("문화콘텐츠학부", [
        "문화콘텐츠학부",
    ]),
    ("글로컬라이프대학", [
        "휴먼케어창의학부(심리복지·복지상담학전공, 자산관리·6차산업학전공)",
        "글로컬융합학부(평생교육·청소년학전공, 웰라이프·헬스케어학전공)",
    ]),
]


def major_to_dept(major: str) -> str:
    """전공명 → 학과명 변환
    - 경영학전공 → 경영학과  (이미 '학'으로 끝나면 '과'만 추가)
    - 시각디자인전공 → 시각디자인학과
    """
    name = major.removesuffix('전공')
    return name + ('과' if name.endswith('학') else '학과')


def expand_entry(raw: str) -> list[str]:
    """'학부명(전공1, 전공2)' 형식을 최종 학과명 리스트로 변환"""
    m = re.match(r'^(.+?)\((.+)\)$', raw)
    if not m:
        return [raw]  # 괄호 없음 → 그대로
    majors = [maj.strip() for maj in m.group(2).split(',')]
    return [major_to_dept(major) for major in majors]


def get_db_session():
    models.Base.metadata.create_all(bind=engine)
    return SessionLocal()


def main():
    db = get_db_session()

    # 원본 데이터 → (college, depart) 쌍 생성
    data = []
    for college, entries in COLLEGE_DATA:
        for entry in entries:
            for dept in expand_entry(entry):
                data.append((college, dept))

    print(f"총 {len(data)}개 학과 추출\n")
    for college, dept in data:
        print(f"  {college} → {dept}")

    print("\nDB 저장 중...")
    inserted = 0
    for college, dept in data:
        existing = db.query(models.Depart).filter(models.Depart.depart == dept).first()
        if not existing:
            db.add(models.Depart(college=college, depart=dept))
            inserted += 1

    db.commit()
    print(f"\n{inserted}개 학과 DB 저장 완료")

    departments = db.query(models.Depart).all()
    print(f"\n--- 저장된 학과 목록 (총 {len(departments)}개) ---")
    print(f"{'dept_no':<10} {'college':<20} {'depart':<50}")
    print("-" * 80)
    for dept in departments:
        print(f"{dept.dept_no:<10} {dept.college:<20} {dept.depart:<50}")

    db.close()


if __name__ == "__main__":
    main()
