"""현재 DB에 저장된 강의들의 학과명(department)과 매핑 테스트"""
import os, json
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mugang:mugang@localhost:5432/mugang")

# 현재 코드에 있는 맵들 (복사본)
dept_alias = {
    "사회대": "사회과학대학", "사범대": "사범대학", "공공인재": "공공인재대학",
    "디예대": "디자인예술대학", "재과대": "재활과학대학", "문화콘텐츠": "문화콘텐츠학부",
    "글로컬라이프": "글로컬라이프대학", "보건바이오대학": "보건바이오대학",
    "글로벌경영대학": "글로벌경영대학", "체육레저학부": "체육레저학부",
    "문화콘텐츠학부": "문화콘텐츠학부", "IT·공과대학": "IT·공과대학", "대학전체": "대학전체",
}

fallback_mapping = {
    '특교유특초특': '사범대학', '수교화교': '사범대학', '물교지구': '사범대학', 
    '사범대': '사범대학', '영교': '사범대학', '역교': '사범대학', '일사': '사범대학',
    '국교': '사범대학', '지교': '사범대학', '유교': '사범대학',
    '자전융합': '자유전공학부', '자유전공': '자유전공학부',
    '공공인재': '공공인재대학', '공공': '공공인재대학',
    '글경': '글로벌경영대학', '글로벌경영': '글로벌경영대학',
    '사과': '사회과학대학', '사회대': '사회과학대학',
    '보건': '보건바이오대학', '재활': '재활과학대학', '재과대': '재활과학대학',
    '간호': '간호대학', '미술치료': '재활과학대학',
    '디예': '디자인예술대학', '디예대': '디자인예술대학',
    '체육': '체육레저학부',
    '문콘': '문화콘텐츠학부', '문화콘텐츠': '문화콘텐츠학부',
    '디지털미디어': '문화콘텐츠학부',
    'IT·공과': 'IT·공과대학',
    '글로컬': '글로컬라이프대학', '글로컬라이프': '글로컬라이프대학',
    '외식산업': '글로컬라이프대학', '생태관광': '글로컬라이프대학',
    '스마트팜': '글로컬라이프대학', '스마트센싱': 'IT·공과대학',
    '스마트제로': '글로컬라이프대학', '스포츠산업': '체육레저학부',
    '사이버수사': '공공인재대학', '글로벌ICT': 'IT·공과대학',
    '비즈니스데이터': '글로벌경영대학', '프리로스쿨': '공공인재대학',
    '동아시아': '사회과학대학', '도시인문': '사회과학대학',
    '대학전체': '교양대학',
}

def get_college(dept):
    if not dept: return "-"
    d = dept_alias.get(dept, dept)
    res = fallback_mapping.get(d)
    if not res:
        for k, v in fallback_mapping.items():
            if k in d: return v
    if not res:
        if any(kw in d for kw in ['전공', '창업학', '인문', '디지털미디어', '관광', '치유', '학']):
            return '연계/융합대학'
        return "미매핑(-)"
    return res

engine = create_engine(DATABASE_URL)
with engine.connect() as conn:
    rows = conn.execute(text("SELECT DISTINCT department FROM lecture_tb")).fetchall()
    print(f"총 {len(rows)}개의 고유 학과명이 발견되었습니다.\n")
    print(f"{'원문 학과명':<20} | {'최종 매핑 결과':<15}")
    print("-" * 40)
    for r in rows:
        dept = r[0]
        college = get_college(dept)
        print(f"{str(dept):<20} | {college}")
