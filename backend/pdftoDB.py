import pdfplumber
import sqlite3
import os
import re

# 1. 데이터베이스 초기화
def init_db():
    conn = sqlite3.connect('mugang.db')
    cursor = conn.cursor()
    # 이미지의 구조에 맞춰 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS College (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    conn.commit()
    return conn

# 2. PDF에서 단과대학 정보 추출
def extract_colleges_from_pdf(file_path):
    colleges = set()
    
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            
            # PDF 상단 또는 표 머리글 근처의 단과대학 명칭 패턴 매칭
            # 예: "사범대학", "간호대학", "인문대학" 등 '대학'으로 끝나는 단어 추출
            matches = re.findall(r'(\S+대학)(?:\s|$)', text)
            for match in matches:
                # "대학전체" 같은 공통 항목은 제외 (필요시 포함)
                if match != "대학전체":
                    colleges.add(match)
                    
    return colleges

# 3. 메인 실행 로직
def main():
    conn = init_db()
    cursor = conn.cursor()
    
    # 처리할 PDF 파일 리스트
    pdf_files = [
        '2026_1_lecture_07_01.pdf', '2026_1_lecture_07_04.pdf',
        '2026_1_lecture_07_05.pdf', '2026_1_lecture_07_06.pdf',
        '2026_1_lecture_07_07.pdf'
    ]
    
    all_colleges = set()

    print("데이터 추출 중...")
    for file in pdf_files:
        if os.path.exists(file):
            found = extract_colleges_from_pdf(file)
            all_colleges.update(found)
            print(f"[{file}] 추출 완료: {found}")

    # 4. DB에 저장
    print("\nDB 저장 중...")
    for college_name in all_colleges:
        try:
            cursor.execute('INSERT INTO College (name) VALUES (?)', (college_name,))
        except sqlite3.IntegrityError:
            # 중복 데이터인 경우 무시
            pass

    conn.commit()
    
    # 결과 확인
    cursor.execute('SELECT * FROM College')
    print("\n--- 저장된 단과대학 목록 ---")
    for row in cursor.fetchall():
        print(f"ID: {row[0]} | 명칭: {row[1]}")
        
    conn.close()

if __name__ == "__main__":
    main()