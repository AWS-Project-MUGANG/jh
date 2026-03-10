"""5번 PDF 수강학과 값 분석"""
import os, re, json
import pdfplumber

pdf_path = r"C:\Users\junse\Desktop\vscode\team-project\mugang_aws\pdf\2026_1_lecture_07_05.pdf"
out_path = r"C:\Users\junse\Desktop\vscode\team-project\mugang_aws\tmp_dept_list.json"

dept_values = {}

with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        table = page.extract_table()
        if not table:
            continue
        header = [re.sub(r'\s+', '', h or '') for h in table[0]]
        idx_course = header.index("수강번호") if "수강번호" in header else 3
        idx_dept   = header.index("수강학과") if "수강학과" in header else 2

        for row in table[1:]:
            c_no = row[idx_course] if idx_course < len(row) else None
            if not c_no or not c_no.strip().isdigit():
                continue
            dept = row[idx_dept] if idx_dept < len(row) else None
            if dept:
                dept = dept.replace('\n', '').strip()
                dept_values[dept] = dept_values.get(dept, 0) + 1

# JSON으로 저장 (인코딩 문제 없음)
with open(out_path, 'w', encoding='utf-8') as f:
    sorted_data = dict(sorted(dept_values.items(), key=lambda x: -x[1]))
    json.dump(sorted_data, f, ensure_ascii=False, indent=2)

print(f"완료! {out_path} 에 저장됨. 항목수={len(dept_values)}")
