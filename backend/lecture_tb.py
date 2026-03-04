import pdfplumber
import re
import pandas as pd
from sqlalchemy import create_engine

# 1. 시간 변환 함수
def to_mins(t_str):
    h, m = map(int, t_str.split(':'))
    return h * 60 + m

# 2. PDF 파싱 및 데이터 정규화
def process_lectures_to_db(pdf_list, db_url):
    engine = create_engine(db_url)
    time_re = re.compile(r'([월화수목금토])\((\d{2}:\d{2})-(\d{2}:\d{2})\)')
    
    for pdf_path in pdf_list:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if not table: continue
                
                for row in table[1:]:
                    # PDF 컬럼 순서에 따라 인덱스 조정 필요 (예시 기준)
                    # row[0]:구분, row[1]:학년, row[2]:학과, row[3]:수강번호, row[4]:과목명...
                    try:
                        c_no = row[3].strip()
                        raw_time = row[8] if row[8] else ""
                        
                        # lecture_tb 데이터 준비
                        lec_data = {
                            "course_no": c_no,
                            "subject": row[4].replace('\n', ''),
                            "department": row[2].replace('\n', ''),
                            "lec_grade": row[1],
                            "credit": int(row[5]) if row[5].isdigit() else 3,
                            "professor": row[7].replace('\n', '') if row[7] else "미지정",
                            "classroom": row[9].replace('\n', '') if row[9] else "미지정",
                            "type": row[0][:2], # '공통', '전선' 등 ENUM 매칭
                            "capacity": 40,      # PDF에 정원 정보가 없다면 기본값 부여
                            "version": 0
                        }
                        
                        # DB에 강의 저장 후 lecture_id 가져오기
                        df_lec = pd.DataFrame([lec_data])
                        df_lec.to_sql('lecture_tb', engine, if_exists='append', index=False)
                        
                        # 생성된 ID 조회 (또는 서브쿼리 활용)
                        res = engine.execute(f"SELECT lecture_id FROM lecture_tb WHERE course_no='{c_no}'")
                        l_id = res.fetchone()[0]

                        # schedule_tb 데이터 분리 및 저장
                        matches = time_re.findall(raw_time)
                        for day, start, end in matches:
                            sch_data = {
                                "lecture_id": l_id,
                                "day_of_week": day,
                                "start_min": to_mins(start),
                                "end_min": to_mins(end),
                                "start_time": start,
                                "end_time": end
                            }
                            pd.DataFrame([sch_data]).to_sql('schedule_tb', engine, if_exists='append', index=False)
                    except:
                        continue

# 사용 예시
# process_lectures_to_db(['2026_1_lecture_07_01.pdf'], 'postgresql://user:pw@localhost:5432/db')