"""5번 PDF에서 course_no 목록 추출"""
import os, re, json
import pdfplumber

pdf_path = r"C:\Users\junse\Desktop\vscode\team-project\mugang_aws\pdf\2026_1_lecture_07_05.pdf"
out_path = r"C:\Users\junse\Desktop\vscode\team-project\mugang_aws\tmp_course_nos.json"

course_nos = []

with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        table = page.extract_table()
        if not table:
            continue
        header = [re.sub(r'\s+', '', h or '') for h in table[0]]
        idx_course = header.index("수강번호") if "수강번호" in header else 3
        for row in table[1:]:
            c_no = row[idx_course] if idx_course < len(row) else None
            if c_no and c_no.strip().isdigit():
                course_nos.append(c_no.strip())

with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(list(set(course_nos)), f, ensure_ascii=False, indent=2)

print(f"완료! 수강번호 {len(set(course_nos))}개 → {out_path}")
