# PDF Reader — 개발 서적 챕터별 학습노트 생성기

**어떤 개발 서적이든**(영문이든 한글이든) PDF를 **챕터별로 분할**하고, 각 챕터를 읽어
**한국어 학습노트(`.md`)**로 정리해 주는 **범용** 로컬 도구입니다.

- 특정 책·주제에 묶이지 않습니다. `data/` 에 넣는 PDF만 바꾸면 어떤 책이든 그대로 동작합니다.
- 책 제목·챕터 수·전문 용어는 입력 PDF에서 동적으로 끌어옵니다(코드·커맨드 수정 불필요).
- 원문 언어와 무관하게 결과 노트는 **항상 한국어**로 작성합니다.

> 활용 예: 한 권을 챕터 단위로 꾸준히 학습하고, 핵심을 자기 말로 재구성해 블로그·노트에
> 정리하는 데 쓸 수 있습니다. (저장소 소유자는 쿠버네티스 원서를 하루 1챕터씩 학습하는
> 용도로 쓰고 있지만, 이는 **하나의 사용 예시일 뿐 프로젝트의 목적이 아닙니다.**)

---

## 핵심 설계 — 2단계 분리

이 프로젝트는 역할을 둘로 나눕니다. 한 책 전체를 매번 AI에 넣지 않으려는 의도입니다.

| 단계 | 담당 | 하는 일 |
|------|------|---------|
| ① **분할** | 코드 (`scripts/extract_chapters.py`) | PDF 목차를 읽어 챕터 경계를 찾고 챕터별 PDF로 자른다. 결정론적. |
| ② **정리** | AI (`/study` 커맨드) | 잘린 챕터 PDF **하나만** 읽고 학습노트를 만든다. 그림·다이어그램까지 해석. |

→ 토큰·비용 절약 · 다이어그램 보존(텍스트만 뽑으면 그림이 소실됨) · 재현성 확보.

`/study` 는 책의 핵심을 **자기 말로 재구성한 한국어 학습노트**(`chapterNN.md`)를 만듭니다.

---

## 폴더 구조

```
.
├── data/                       # 학습할 책 PDF 1개 (입력, 책 무관) — git 제외
├── scripts/
│   └── extract_chapters.py     # 챕터 분할기 (구성요소 ①)
├── chapters/                   # 분할 결과 (자동 생성)
│   └── chapterNN/
│       ├── source.pdf          # 분할 원본 (읽기 입력) — git 제외
│       ├── source.txt          # 텍스트 추출본 — git 제외
│       └── chapterNN.md        # 학습노트 (/study 산출물)
├── .claude/
│   ├── CLAUDE.md               # 프로젝트 설계·운영 기준
│   └── commands/
│       └── study.md            # /study 슬래시 커맨드 (구성요소 ②)
├── toc.json                    # 챕터↔페이지 매핑 (자동 생성·수동 교정 가능)
└── requirements.txt
```

---

## 사용법

### 0. 설치

```bash
pip install -r requirements.txt   # pymupdf
```

### 1. 분할 — `scripts/extract_chapters.py`

학습할 책 PDF 1개를 `data/` 에 넣고(영문·한글 무관):

```bash
python scripts/extract_chapters.py --inspect   # 챕터 감지 결과만 확인(파일 생성 안 함)
python scripts/extract_chapters.py --text      # 분할 실행(+텍스트 추출)
```

| 플래그 | 동작 |
|--------|------|
| (없음) | 전체 챕터 분할 |
| `--inspect` | 감지된 챕터 구조만 출력 |
| `--chapter N` | N번 챕터만 (재)분할 |
| `--text` | `source.pdf` 와 함께 `source.txt` 도 추출 |
| `--reindex` | `toc.json` 무시하고 목차 재감지 |
| `--pdf PATH` | PDF 경로 직접 지정 |
| `--out-dir DIR` | 챕터 폴더 생성 위치(기본 `chapters/`) |

**챕터 감지 우선순위**: `toc.json`(사람 교정본) → PDF 내장 목차 → 페이지 머리글 스캔.
감지가 어긋나면 `toc.json` 의 `start`/`end` 를 직접 고친 뒤 `--chapter N` 으로 재분할합니다.

### 2. 정리 — `/study`

[Claude Code](https://claude.com/claude-code) 에서 챕터 번호와 함께 실행합니다:

```
/study 1
```

`chapters/chapter01/source.pdf` 를 그림까지 읽어 `chapter01.md` 학습노트를 만듭니다.
직전 챕터 노트가 있으면 '지난 시간에 학습한 내용'으로 이어 주며, **한 번에 한 챕터만**
생성합니다(매일 학습이 목적).

---

## 진행 관리

- `toc.json` — 챕터↔페이지 매핑. 감지가 틀리면 직접 교정할 수 있는 정답 파일입니다.

## 기술 스택

- Python 3.10+
- [PyMuPDF](https://pymupdf.readthedocs.io/) (`pymupdf`) — 목차 읽기 · 분할 · 텍스트 추출

자세한 설계·작성 규칙은 [`.claude/CLAUDE.md`](.claude/CLAUDE.md) 를 참고하세요.
