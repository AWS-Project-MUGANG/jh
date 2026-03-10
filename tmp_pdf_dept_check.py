"""
PDF에서 수강학과(dept) 컬럼 값들을 추출해
depart_tb에 없는(매핑 안 되는) 항목을 찾아냄
"""
import sys, os, re
import pdfplumber

pdf_dir = os.path.join(os.path.dirname(__file__), "pdf")

time_re  = re.compile(r'([월화수목금토])\((\d{2}:\d{2})-(\d{2}:\d{2})\)')

dept_values = {}   # dept_name -> count

for fname in sorted(os.listdir(pdf_dir)):
    if not fname.endswith(".pdf"):
        continue
    fpath = os.path.join(pdf_dir, fname)
    print(f"\n{'='*60}")
    print(f"📄 {fname}")
    print(f"{'='*60}")
    try:
        with pdfplumber.open(fpath) as pdf:
            for pno, page in enumerate(pdf.pages, 1):
                table = page.extract_table()
                if not table:
                    continue

                # 헤더 파싱
                header = [re.sub(r'\s+', '', h or '') for h in table[0]]

                def col(name, fallback):
                    return header.index(name) if name in header else fallback

                idx_course = col("수강번호", 3)
                idx_dept   = col("수강학과", 2)

                for row in table[1:]:
                    if len(row) <= max(idx_course, idx_dept):
                        continue
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
    except Exception as e:
        print(f"  ❌ 오류: {e}")

print("\n" + "="*60)
print("📊 PDF에서 추출된 수강학과 값 목록 (빈도수 내림차순)")
print("="*60)
for dept, cnt in sorted(dept_values.items(), key=lambda x: -x[1]):
    print(f"  {cnt:4d}회  |  '{dept}'")

print(f"\n총 고유 학과값: {len(dept_values)}개")
