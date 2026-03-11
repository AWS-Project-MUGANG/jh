"""
PDF 강의 시간표를 CSV로 변환 후 DB에 삽입하는 프로그램
DB 테이블: lecture_tb, schedule_tb
"""

import pdfplumber
import re
import pandas as pd
from sqlalchemy import create_engine, text
from typing import List, Dict, Optional, Tuple
import os

# =====================================================
# 1. 유틸리티 함수
# =====================================================

def to_mins(t_str: str) -> int:
    """시간 문자열(HH:MM)을 분으로 변환"""
    h, m = map(int, t_str.split(':'))
    return h * 60 + m


def clean_text(value: Optional[str]) -> str:
    """텍스트 정리 (줄바꿈 제거, 공백 정리)"""
    if not value:
        return ""
    return value.replace('\n', '').strip()


def parse_credit(credit_str: Optional[str]) -> int:
    """학점 문자열을 정수로 변환"""
    if not credit_str:
        return 3  # 기본값
    # 숫자만 추출
    match = re.search(r'\d+', credit_str)
    if match:
        return int(match.group())
    return 3


def map_lecture_type(type_str: Optional[str]) -> str:
    """
    구분 값을 DB ENUM에 맞게 매핑
    ENUM: 'MAJOR_REQUIRED', 'MAJOR_ELECTIVE', 'LIBERAL_REQUIRED', 
          'LIBERAL_ELECTIVE', 'TEACHING', 'COMMON'
    """
    if not type_str:
        return "MAJOR_ELECTIVE"
    
    type_str = clean_text(type_str)
    
    type_mapping = {
        '전필': 'MAJOR_REQUIRED',
        '전선': 'MAJOR_ELECTIVE',
        '교필': 'LIBERAL_REQUIRED',
        '교선': 'LIBERAL_ELECTIVE',
        '교직': 'TEACHING',
        '공통': 'COMMON',
        '일선': 'MAJOR_ELECTIVE',
        '기필': 'LIBERAL_REQUIRED',
        '기선': 'LIBERAL_ELECTIVE',
    }
    
    # 앞 2글자로 매칭
    key = type_str[:2] if len(type_str) >= 2 else type_str
    return type_mapping.get(key, 'MAJOR_ELECTIVE')


def parse_schedule(raw_time: str, classroom: str = "") -> List[Dict]:
    """
    강의시간 문자열 파싱
    예: '화(10:00-12:50)' -> [{'day_of_week': '화', 'start_time': '10:00:00', 'end_time': '12:50:00', 'classroom': '...'}]
    
    같은 강의가 주 2회면 (예: 월(09:00-10:15)\n수(09:00-10:15))
    -> 2개의 스케줄 레코드가 생성되고, 같은 lecture_id로 연결됨
    """
    if not raw_time:
        return []
    
    # 패턴: 요일(시작-종료)
    pattern = r'([월화수목금토일])\((\d{2}:\d{2})-(\d{2}:\d{2})\)'
    matches = re.findall(pattern, raw_time)
    
    schedules = []
    for day, start, end in matches:
        schedules.append({
            'day_of_week': day,                    # bpchar(1) - 요일 한 글자
            'start_time': f"{start}:00",           # time 타입 (HH:MM:SS)
            'end_time': f"{end}:00",               # time 타입 (HH:MM:SS)
            'classroom': clean_text(classroom)     # varchar(50) - 강의실
        })
    
    return schedules


# =====================================================
# 2. PDF 파싱 함수
# =====================================================

def extract_lectures_from_pdf(pdf_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    PDF에서 강의 데이터 추출
    Returns: (lecture_df, schedule_df)
    """
    lectures = []
    schedules = []
    
    # 현재 학년/구분 추적 (빈 셀은 이전 값 사용)
    current_grade = ""
    current_type = ""
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if not tables:
                continue
            
            table = tables[0]
            
            for row_idx, row in enumerate(table):
                # 헤더 행 스킵 (첫 페이지의 첫 행 또는 헤더 패턴)
                if row_idx == 0:
                    first_cell = clean_text(row[0]) if row[0] else ""
                    if first_cell in ['학년', ''] or '학년' in first_cell:
                        continue
                
                # 컬럼 인덱스
                # [0]:학년, [1]:구분, [2]:수강학과, [3]:수강번호, [4]:교과목명
                # [5]:학점, [6]:시간, [7]:담당교수, [8]:강의시간, [9]:강의실
                
                try:
                    # 필수 필드 확인: 수강번호
                    course_no = clean_text(row[3]) if len(row) > 3 and row[3] else ""
                    if not course_no or not course_no.isdigit():
                        continue
                    
                    # 학년/구분 업데이트 (빈 값이면 이전 값 유지)
                    if row[0] and clean_text(row[0]):
                        current_grade = clean_text(row[0])
                    if row[1] and clean_text(row[1]):
                        current_type = clean_text(row[1])
                    
                    # 강의 데이터 구성 (classroom은 schedule_tb에서 관리)
                    lecture = {
                        'course_no': course_no,
                        'subject': clean_text(row[4]) if len(row) > 4 else "",
                        'department': clean_text(row[2]) if len(row) > 2 else "",
                        'lec_grade': current_grade,
                        'credit': parse_credit(row[5]) if len(row) > 5 else 3,
                        'professor': clean_text(row[7]) if len(row) > 7 and row[7] else "미지정",
                        'type': map_lecture_type(current_type),
                        'capacity': 40,          # 기본값
                        'count': 0,              # 초기값
                        'version': 0,            # 초기값
                        'waitlist_capacity': 10  # 기본값
                    }
                    
                    lectures.append(lecture)
                    
                    # 스케줄 파싱 (classroom 포함)
                    raw_time = row[8] if len(row) > 8 and row[8] else ""
                    classroom = row[9] if len(row) > 9 and row[9] else "미지정"
                    schedule_list = parse_schedule(raw_time, classroom)
                    
                    for sch in schedule_list:
                        sch['course_no'] = course_no  # 나중에 lecture_id로 교체
                        schedules.append(sch)
                    
                except Exception as e:
                    # 파싱 실패 시 해당 행 스킵
                    print(f"Warning: 페이지 {page_idx+1}, 행 {row_idx} 파싱 실패: {e}")
                    continue
    
    lecture_df = pd.DataFrame(lectures)
    schedule_df = pd.DataFrame(schedules)
    
    return lecture_df, schedule_df


# =====================================================
# 3. CSV 저장 함수
# =====================================================

def save_to_csv(lecture_df: pd.DataFrame, schedule_df: pd.DataFrame, output_dir: str = "."):
    """DataFrame을 CSV로 저장"""
    
    lecture_path = os.path.join(output_dir, "lecture_tb.csv")
    schedule_path = os.path.join(output_dir, "schedule_tb.csv")
    
    lecture_df.to_csv(lecture_path, index=False, encoding='utf-8-sig')
    schedule_df.to_csv(schedule_path, index=False, encoding='utf-8-sig')
    
    print(f"✅ lecture_tb.csv 저장 완료: {len(lecture_df)}건")
    print(f"✅ schedule_tb.csv 저장 완료: {len(schedule_df)}건")
    
    return lecture_path, schedule_path


# =====================================================
# 4. DB 삽입 함수
# =====================================================

def insert_to_db(lecture_df: pd.DataFrame, schedule_df: pd.DataFrame, db_url: str):
    """
    DataFrame을 DB에 삽입
    
    Args:
        lecture_df: 강의 데이터 DataFrame
        schedule_df: 스케줄 데이터 DataFrame  
        db_url: DB 연결 문자열 (예: postgresql://user:pw@localhost:5432/db)
    """
    engine = create_engine(db_url)
    
    # 1) lecture_tb에 삽입
    print("📤 lecture_tb 데이터 삽입 중...")
    
    # course_no -> lecture_id 매핑을 위한 딕셔너리
    course_to_lecture_id = {}
    
    with engine.connect() as conn:
        for idx, row in lecture_df.iterrows():
            # INSERT 후 RETURNING으로 lecture_id 가져오기
            insert_sql = text("""
                INSERT INTO lecture_tb 
                (course_no, subject, department, lec_grade, credit, 
                 professor, type, capacity, count, version, waitlist_capacity)
                VALUES 
                (:course_no, :subject, :department, :lec_grade, :credit,
                 :professor, :type::lecture_category, :capacity, :count, :version, :waitlist_capacity)
                RETURNING lecture_id
            """)
            
            result = conn.execute(insert_sql, {
                'course_no': row['course_no'],
                'subject': row['subject'],
                'department': row['department'],
                'lec_grade': row['lec_grade'],
                'credit': row['credit'],
                'professor': row['professor'],
                'type': row['type'],
                'capacity': row['capacity'],
                'count': row['count'],
                'version': row['version'],
                'waitlist_capacity': row['waitlist_capacity']
            })
            
            lecture_id = result.fetchone()[0]
            course_to_lecture_id[row['course_no']] = lecture_id
        
        conn.commit()
    
    print(f"✅ lecture_tb 삽입 완료: {len(lecture_df)}건")
    
    # 2) schedule_tb에 삽입
    if not schedule_df.empty:
        print("📤 schedule_tb 데이터 삽입 중...")
        
        # course_no를 lecture_id로 변환
        schedule_df['lecture_id'] = schedule_df['course_no'].map(course_to_lecture_id)
        
        # lecture_id가 없는 행 제거
        schedule_df = schedule_df.dropna(subset=['lecture_id'])
        schedule_df['lecture_id'] = schedule_df['lecture_id'].astype(int)
        
        with engine.connect() as conn:
            for idx, row in schedule_df.iterrows():
                insert_sql = text("""
                    INSERT INTO schedule_tb 
                    (lecture_id, day_of_week, start_time, end_time, classroom)
                    VALUES 
                    (:lecture_id, :day_of_week, :start_time::time, :end_time::time, :classroom)
                """)
                
                conn.execute(insert_sql, {
                    'lecture_id': row['lecture_id'],
                    'day_of_week': row['day_of_week'],
                    'start_time': row['start_time'],
                    'end_time': row['end_time'],
                    'classroom': row['classroom']
                })
            
            conn.commit()
        
        print(f"✅ schedule_tb 삽입 완료: {len(schedule_df)}건")


# =====================================================
# 5. 메인 실행
# =====================================================

def process_pdf_to_csv_and_db(
    pdf_path: str, 
    output_dir: str = ".", 
    db_url: Optional[str] = None,
    save_csv: bool = True
):
    """
    PDF를 처리하여 CSV 저장 및 DB 삽입
    
    Args:
        pdf_path: PDF 파일 경로
        output_dir: CSV 저장 디렉토리
        db_url: DB 연결 문자열 (None이면 DB 삽입 생략)
        save_csv: CSV 저장 여부
    """
    print(f"📂 PDF 파일 처리 중: {pdf_path}")
    
    # 1) PDF 파싱
    lecture_df, schedule_df = extract_lectures_from_pdf(pdf_path)
    print(f"📊 추출 완료: 강의 {len(lecture_df)}건, 스케줄 {len(schedule_df)}건")
    
    # 2) CSV 저장
    if save_csv:
        save_to_csv(lecture_df, schedule_df, output_dir)
    
    # 3) DB 삽입 (URL이 제공된 경우)
    if db_url:
        insert_to_db(lecture_df, schedule_df, db_url)
    
    return lecture_df, schedule_df


# =====================================================
# 실행 예시
# =====================================================

if __name__ == "__main__":
    # 설정
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    OUTPUT_DIR = BASE_DIR

    # 처리할 PDF 파일 목록
    pdf_files = sorted([
        f for f in os.listdir(BASE_DIR)
        if f.endswith('.pdf') and 'lecture' in f
    ])
    # 1. PDF 파일 찾기 (backend 폴더 우선, 없으면 상위 pdf 폴더 검색)
    search_dirs = [BASE_DIR, os.path.join(os.path.dirname(BASE_DIR), "pdf")]
    pdf_files = []

    for d in search_dirs:
        if os.path.exists(d):
            files = [os.path.join(d, f) for f in os.listdir(d) if f.endswith('.pdf')]
            if files:
                pdf_files = sorted(files)
                print(f"📁 '{d}' 경로에서 {len(pdf_files)}개의 PDF 파일을 찾았습니다.")
                break

    if not pdf_files:
        print("처리할 PDF 파일이 없습니다.")
        print(f"❌ PDF 파일을 찾을 수 없습니다. 검색 경로: {search_dirs}")
        exit(1)

    # 2. DB 연결 설정 (로컬 Docker 실행 기준: localhost)
    # Docker 내부에서 실행 시: postgresql://mugang:mugang@db:5432/mugang
    # 로컬 터미널에서 실행 시: postgresql://mugang:mugang@localhost:5432/mugang
    db_url = os.getenv("DATABASE_URL", "postgresql://mugang:mugang@localhost:5432/mugang")

    all_lectures = []
    all_schedules = []

    for pdf_path in pdf_files:
        lecture_df, schedule_df = process_pdf_to_csv_and_db(
            pdf_path=pdf_path,
            output_dir=OUTPUT_DIR,
            db_url=db_url,
            save_csv=True
        )
        all_lectures.append(lecture_df)
        all_schedules.append(schedule_df)

    # 전체 합치기
    combined_lectures = pd.concat(all_lectures, ignore_index=True)
    combined_schedules = pd.concat(all_schedules, ignore_index=True)

    save_to_csv(combined_lectures, combined_schedules, OUTPUT_DIR)

    print("\n" + "="*60)
    print(f"📋 lecture_tb 샘플 (상위 5개):")
    print(combined_lectures.head().to_string())

    print(f"\n📋 schedule_tb 샘플 (상위 10개):")
    print(combined_schedules.head(10).to_string())