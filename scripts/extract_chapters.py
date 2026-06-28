#!/usr/bin/env python3
"""챕터 분할기 (구성요소 ①).

PDF 원서를 챕터별 `source.pdf` 로 자르고, `toc.json` 을 만든다.
요약·정리는 하지 않는다 — 그건 `/study` 슬래시 커맨드의 몫이다.

자세한 설계는 .claude/CLAUDE.md 섹션 5 참고.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

try:  # PyMuPDF 는 배포판에 따라 모듈명이 다르다.
    import fitz  # type: ignore
except ImportError:  # pragma: no cover - 환경 의존
    import pymupdf as fitz  # type: ignore

# Windows 기본 콘솔(cp949)에서 한글·em-dash 출력이 깨지지 않도록 UTF-8 로 고정.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):  # pragma: no cover - 환경 의존
        pass


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "data"
DEFAULT_OUT = ROOT / "chapters"
TOC_PATH = ROOT / "toc.json"

# "Chapter 5" / "제5장" / "5장" 형태의 챕터 머리글. 캡처 그룹 1 = 챕터 번호.
CHAPTER_PATTERNS = [
    re.compile(r"^\s*chapter\s+(\d+)\b", re.IGNORECASE),
    re.compile(r"^\s*제\s*(\d+)\s*장"),
    re.compile(r"^\s*(\d+)\s*장\b"),
]


@dataclass
class Chapter:
    index: int       # 챕터 논리 번호(= 폴더명 chapterNN)
    title: str
    start: int       # 1-based 물리 페이지(포함)
    end: int         # 1-based 물리 페이지(포함)


# --------------------------------------------------------------------------- #
# 입력 해석
# --------------------------------------------------------------------------- #
def resolve_pdf(pdf_arg: str | None) -> Path:
    """`--pdf` 가 있으면 그것을, 없으면 data/ 안의 유일한 PDF를 쓴다."""
    if pdf_arg:
        p = Path(pdf_arg)
        if not p.is_absolute():
            p = (ROOT / p).resolve()
        if not p.exists():
            sys.exit(f"[오류] PDF를 찾을 수 없습니다: {p}")
        return p

    if not DEFAULT_DATA.exists():
        sys.exit(f"[오류] data/ 폴더가 없습니다. PDF를 {DEFAULT_DATA} 에 넣어주세요.")
    pdfs = sorted(DEFAULT_DATA.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"[오류] {DEFAULT_DATA} 안에 PDF가 없습니다. 원서 PDF 1개를 넣어주세요.")
    if len(pdfs) > 1:
        names = "\n  - ".join(p.name for p in pdfs)
        sys.exit(
            f"[오류] data/ 안에 PDF가 {len(pdfs)}개 있습니다. 하나만 두거나 --pdf 로 지정하세요:\n  - {names}"
        )
    return pdfs[0]


def match_chapter_number(text: str) -> int | None:
    for pat in CHAPTER_PATTERNS:
        m = pat.match(text)
        if m:
            return int(m.group(1))
    return None


# --------------------------------------------------------------------------- #
# 챕터 감지
# --------------------------------------------------------------------------- #
def _finalize(starts: list[tuple[int, str, int]], page_count: int) -> list[Chapter]:
    """(index, title, start) 목록 → end 채운 Chapter 목록.

    같은 챕터 번호가 헤더·푸터로 중복 감지되면 가장 앞 페이지만 남긴다.
    """
    seen: dict[int, tuple[int, str, int]] = {}
    for index, title, start in starts:
        if index not in seen or start < seen[index][2]:
            seen[index] = (index, title, start)
    ordered = sorted(seen.values(), key=lambda t: t[2])

    chapters: list[Chapter] = []
    for i, (index, title, start) in enumerate(ordered):
        end = ordered[i + 1][2] - 1 if i + 1 < len(ordered) else page_count
        chapters.append(Chapter(index=index, title=title.strip(), start=start, end=end))
    return chapters


def detect_from_outline(doc) -> list[Chapter]:
    toc = doc.get_toc(simple=True)  # [[level, title, page(1-based)], ...]
    if not toc:
        return []

    # 1) 제목이 "Chapter N" 패턴과 맞는 항목 우선(3개 이상일 때).
    matched: list[tuple[int, str, int]] = []
    for level, title, page in toc:
        if page < 1:
            continue
        num = match_chapter_number(title)
        if num is not None:
            matched.append((num, title, page))
    if len(matched) >= 3:
        return _finalize(matched, doc.page_count)

    # 2) 패턴이 안 맞으면 가장 얕은 레벨 항목을 챕터로 간주.
    levels = [lvl for lvl, _t, pg in toc if pg >= 1]
    if not levels:
        return []
    top = min(levels)
    flat = [(t, pg) for lvl, t, pg in toc if pg >= 1 and lvl == top]
    starts = [(i + 1, t, pg) for i, (t, pg) in enumerate(flat)]
    return _finalize(starts, doc.page_count)


def detect_from_pages(doc) -> list[Chapter]:
    """목차가 없을 때 각 페이지 상단 6줄에서 챕터 머리글을 스캔."""
    starts: list[tuple[int, str, int]] = []
    for pno in range(doc.page_count):
        text = doc.load_page(pno).get_text("text")
        for line in text.splitlines()[:6]:
            num = match_chapter_number(line)
            if num is not None:
                starts.append((num, line.strip(), pno + 1))  # 1-based
                break
    return _finalize(starts, doc.page_count)


def detect_chapters(doc) -> list[Chapter]:
    chapters = detect_from_outline(doc)
    if chapters:
        return chapters
    return detect_from_pages(doc)


# --------------------------------------------------------------------------- #
# toc.json
# --------------------------------------------------------------------------- #
def load_toc() -> tuple[str | None, list[Chapter]]:
    data = json.loads(TOC_PATH.read_text(encoding="utf-8"))
    return data.get("source"), [Chapter(**c) for c in data["chapters"]]


def write_toc(source_name: str, chapters: list[Chapter]) -> None:
    payload = {"source": source_name, "chapters": [asdict(c) for c in chapters]}
    TOC_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# --------------------------------------------------------------------------- #
# 분할
# --------------------------------------------------------------------------- #
def split_chapter(doc, ch: Chapter, out_dir: Path, with_text: bool) -> None:
    folder = out_dir / f"chapter{ch.index:02d}"
    folder.mkdir(parents=True, exist_ok=True)

    out = fitz.open()
    out.insert_pdf(doc, from_page=ch.start - 1, to_page=ch.end - 1)  # 0-based, 양끝 포함
    out.save(folder / "source.pdf")
    out.close()

    if with_text:
        parts = [
            doc.load_page(p).get_text("text")
            for p in range(ch.start - 1, ch.end)  # end 포함
        ]
        (folder / "source.txt").write_text("\n".join(parts), encoding="utf-8")

    pages = ch.end - ch.start + 1
    print(f"  ✔ chapter{ch.index:02d}  pp.{ch.start}–{ch.end} ({pages}p)  {ch.title}")


def print_inspect(source_name: str, chapters: list[Chapter]) -> None:
    print(f"\n[감지 결과] {source_name} — 챕터 {len(chapters)}개\n")
    print(f"  {'#':>3}  {'pp.':>11}  {'pages':>5}  제목")
    print(f"  {'-'*3}  {'-'*11}  {'-'*5}  {'-'*20}")
    for c in chapters:
        rng = f"{c.start}–{c.end}"
        print(f"  {c.index:>3}  {rng:>11}  {c.end - c.start + 1:>5}  {c.title}")
    print()


# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description="PDF 원서를 챕터별로 분할한다.")
    ap.add_argument("--inspect", action="store_true", help="감지 결과만 출력(파일 생성 안 함)")
    ap.add_argument("--chapter", type=int, metavar="N", help="N번 챕터만 (재)분할")
    ap.add_argument("--text", action="store_true", help="source.pdf 와 함께 source.txt 도 추출")
    ap.add_argument("--reindex", action="store_true", help="toc.json 무시하고 목차 재감지")
    ap.add_argument("--pdf", metavar="PATH", help="PDF 경로 직접 지정(생략 시 data/ 자동 탐색)")
    ap.add_argument("--out-dir", metavar="DIR", help=f"챕터 폴더 위치(기본 {DEFAULT_OUT})")
    args = ap.parse_args()

    pdf_path = resolve_pdf(args.pdf)
    out_dir = Path(args.out_dir).resolve() if args.out_dir else DEFAULT_OUT

    doc = fitz.open(pdf_path)

    # 챕터 목록 확보 — toc.json(사람 교정본) 우선, --reindex 면 재감지.
    # 단, toc.json 의 source 가 현재 PDF와 다르면(= data/ 의 책이 바뀐 경우)
    # 옛 책의 페이지 범위로 새 책을 자르지 않도록 자동으로 재감지한다.
    from_existing_toc = TOC_PATH.exists() and not args.reindex
    if from_existing_toc:
        toc_source, chapters = load_toc()
        if toc_source is not None and toc_source != pdf_path.name:
            print(
                f"[경고] toc.json 은 다른 책('{toc_source}')용입니다. "
                f"현재 PDF '{pdf_path.name}' 와 달라 목차를 재감지합니다.\n"
                "       같은 책을 파일명만 바꾼 경우라면 toc.json 의 \"source\" 를 "
                "새 파일명으로 고친 뒤 다시 실행하세요(교정한 페이지 범위 보존)."
            )
            from_existing_toc = False

    if not from_existing_toc:
        chapters = detect_chapters(doc)
        if not chapters:
            sys.exit(
                "[오류] 챕터를 감지하지 못했습니다.\n"
                f"      목차(outline)도 페이지 머리글도 없는 PDF로 보입니다.\n"
                f"      {TOC_PATH} 를 직접 작성한 뒤 다시 실행하세요. 형식:\n"
                '      {"source": "book.pdf", "chapters": ['
                '{"index":1,"title":"Intro","start":1,"end":12}]}'
            )

    if args.inspect:
        print_inspect(pdf_path.name, chapters)
        return

    # 감지/재감지한 경우에만 toc.json 갱신(교정본은 보존).
    if not from_existing_toc:
        write_toc(pdf_path.name, chapters)
        print(f"[저장] {TOC_PATH.relative_to(ROOT)}")

    targets = chapters
    if args.chapter is not None:
        targets = [c for c in chapters if c.index == args.chapter]
        if not targets:
            avail = ", ".join(str(c.index) for c in chapters)
            sys.exit(f"[오류] {args.chapter}번 챕터가 없습니다. 가능한 번호: {avail}")

    print(f"[분할] {pdf_path.name} → {out_dir.relative_to(ROOT)}/")
    for ch in targets:
        split_chapter(doc, ch, out_dir, args.text)

    doc.close()
    print("[완료] 이제 `/study <챕터번호>` 로 학습노트를 만드세요.")


if __name__ == "__main__":
    main()
