"""
PDF 5번 파일에서 수강학과 컬럼 값들을 추출
"""
import os, re
import pdfplumber

pdf_path = r"C:\Users\junse\Desktop\vscode\team-project\mugang_aws\pdf\2026_1_lecture_07_05.pdf"

dept_values = {}

print(f"분석 파일: {os.path.basename(pdf_path)}\n")

with pdfplumber.open(pdf_path) as pdf:
    for pno, page in enumerate(pdf.pages, 1):
        table = page.extract_table()
        if not table:
            continue

        header = [re.sub(r'\s+', '', h or '') for h in table[0]]

        def col(name, fallback):
            return header.index(name) if name in header else fallback

        idx_course = col("수강번호", 3)
        idx_dept   = col("수강학과", 2)

        # 첫 페이지 헤더 출력
        if pno == 1:
            print(f"헤더 컬럼: {header}")
            print()

        for row in table[1:]:
            c_no = row[idx_course] if idx_course < len(row) else None
            if not c_no:
                continue
            c_no = c_no.strip()
            if not c_no.isdigit():
                continue

            dept = row[idx_dept] if idx_dept < len(row) else None
            if dept:
                dept = dept.replace('\n', '').strip()
                dept_values[dept] = dept_values.get(dept, 0) + 1

print("=" * 50)
print("수강학과 값 목록 (빈도수 내림차순)")
print("=" * 50)
for dept, cnt in sorted(dept_values.items(), key=lambda x: -x[1]):
    print(f"  {cnt:3d}회  |  '{dept}'")

print(f"\n총 고유 학과값: {len(dept_values)}개")
