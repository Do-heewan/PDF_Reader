#!/usr/bin/env python3
"""검증용 더미 PDF 생성기.

목차(outline)가 있는 작은 PDF를 만들어 extract_chapters.py 의 감지/분할 로직을
실제 원서 없이 확인한다. (테스트 용도 — 산출물이 아니다.)
"""
from pathlib import Path
import fitz

# (제목, 시작 1-based 페이지). 마지막 챕터는 문서 끝까지.
SPEC = [
    ("Chapter 1 Introduction", 1),
    ("Chapter 2 Pods", 4),
    ("Chapter 3 Deployments", 9),
    ("Chapter 4 Services", 12),
]
TOTAL_PAGES = 15

doc = fitz.open()
for i in range(TOTAL_PAGES):
    page = doc.new_page()
    page.insert_text((72, 72), f"page {i + 1}", fontsize=14)

# 가장 얕은 레벨(1)에 챕터 목차를 단다.
toc = [[1, title, start] for title, start in SPEC]
doc.set_toc(toc)

out = Path(__file__).resolve().parent.parent / "data" / "dummy.pdf"
out.parent.mkdir(parents=True, exist_ok=True)
doc.save(out)
doc.close()
print(f"wrote {out}  ({TOTAL_PAGES} pages, {len(SPEC)} chapters)")
