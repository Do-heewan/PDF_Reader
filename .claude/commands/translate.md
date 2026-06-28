---
description: 분할된 챕터의 source.txt를 영어 원문 한 줄·한국어 번역 한 줄로 정렬한 문장별 대역본으로 변환한다
argument-hint: <챕터 번호> (예: /translate 3)
allowed-tools: Bash, Read, Write
---

# /translate — 챕터 원문을 문장별 영-한 대역본으로 변환

`chapters/chapterNN/source.txt`(PyMuPDF로 추출한 챕터 원문 텍스트)를 읽어, **문장마다
영어 원문 한 줄 + 한국어 번역 한 줄**로 정렬한 대역본 파일을 만든다.
`/study`(개념을 자기 말로 재구성)와 달리, 이 커맨드는 **원문을 빠짐없이 문장 단위로
충실히 번역**한다 — 원서를 한 문장씩 대조하며 읽기 위한 학습 보조 자료다.
이번 호출에서 처리할 챕터 번호는 `$ARGUMENTS` 다. (비어 있으면 어느 챕터인지 묻고 멈춘다.)

## 절차

### 1. 챕터 번호 정규화
- `$ARGUMENTS` 의 숫자를 두 자리로 만든다 (`3` → `03`, `12` → `12`).
  대상 입력은 `chapters/chapter{NN}/source.txt`,
  출력은 `chapters/chapter{NN}/source.bilingual.txt`.
- 숫자가 없으면 번역하지 말고 어느 챕터인지 물은 뒤 멈춘다.

### 2. 원본 확인
`chapters/chapter{NN}/source.txt` 가 있는지 본다. 없으면 변환하지 말고 다음을 안내하고 멈춘다
(`source.txt` 는 분할 시 `--text` 옵션으로 생성된다):
```bash
python scripts/extract_chapters.py --chapter {N} --text   # 해당 챕터만 텍스트까지 추출
python scripts/extract_chapters.py --text                 # 전체를 텍스트까지 재추출
```

### 3. 읽기 · 전처리(클린업)
Read 도구로 `source.txt` 전체를 읽은 뒤, PyMuPDF 추출 특성을 고려해 **문장을 복원**한다.
이 정리를 건너뛰면 문장이 줄 단위로 잘려 번역이 엉킨다.

- **줄바꿈으로 잘린 문장 잇기**: 본문은 한 문장이 여러 줄에 걸쳐 있다. 마침표/물음표/느낌표로
  끝나지 않은 줄은 다음 줄과 이어 붙여 **온전한 문장**으로 만든다.
- **하이픈 분절 복원**: 줄 끝의 `‐`(U+2010)나 `-` 로 끊긴 단어(예: `remain‐\ning`,
  `depen-\ndencies`)는 붙여서 한 단어로 만든다.
- **머리글·바닥글·페이지 번호 제거**: 단독 숫자 줄(예: `29`), `16 | Chapter 2: …`,
  `Solution | 17` 같은 러닝 헤더/푸터는 버린다.
- **그림 캡션·표·코드 구분**: `Figure X-Y …`, `Example X-Y …`, 표, 코드/매니페스트 블록은
  산문 문장과 구분해 따로 다룬다(아래 §4 코드 규칙).

### 4. 문장 분리 · 번역
정리된 본문을 **영어 문장 경계**로 나누고, 각 문장을 한국어로 옮긴다.

- **문장 분리 주의**: 약어(`e.g.`, `i.e.`, `etc.`, `vs.`), 소수점, 코드 안의 마침표는
  문장 끝으로 오인하지 않는다.
- **충실 번역**: 자연스러운 한국어 기술 문체로 옮기되, `/study` 처럼 재구성·의역하지 말고
  **문장 대 문장으로 그 뜻을 그대로** 전달한다. 원문에 없는 내용을 더하거나 빼지 않는다.
- **코드·식별자·명령어는 번역하지 않는다**: 클래스·함수·명령·리소스 이름(예: `Pod`,
  `kubectl apply`, `RollingUpdate`), 매니페스트, 코드 블록은 원문 그대로 둔다. 코드/명령이
  한 줄을 통째로 차지하면 그 줄은 원문만 두고 번역 줄을 비우거나 `# (코드)` 로 표시한다.
- **전문 용어**: 책 맥락에 맞는 한국어로 옮기되 처음 등장 시 `한국어(원어)` 로 병기해도 좋다.
- **절 제목**(`Problem`, `Solution`, `Discussion`, `Rolling Deployment` 등)은 한 줄로 두고
  바로 아래에 한국어 번역을 단다(본문 문장 쌍과 같은 형식).

### 5. 출력
`chapters/chapter{NN}/source.bilingual.txt` 에 아래 형식으로 Write 한다.
**영어 문장 한 줄 → 그 아래 한국어 번역 한 줄 → 빈 줄** 의 반복이다.

```text
# {NN}. {챕터 제목}  ·  영-한 대역본 (source.txt 기준)

Problem
문제

We can provision isolated environments as namespaces in a self-service manner and place the applications in these environments with minimal human intervention through the scheduler.
우리는 격리된 환경을 네임스페이스로 셀프서비스하듯 마련하고, 스케줄러를 통해 사람 개입을 최소화하며 애플리케이션을 그 환경에 배치할 수 있다.

But with a growing number of microservices, continually updating and replacing them with newer versions becomes an increasing burden too.
그러나 마이크로서비스 수가 늘면, 이를 새 버전으로 끊임없이 갱신·교체하는 일 또한 점점 큰 부담이 된다.
```

### 6. 마무리
출력 파일 경로와 변환한 문장 수(대략)를 사용자에게 알린다. 원서를 보며 한 문장씩
대조해 읽도록 안내한다.

## 원칙
- **한 번에 한 챕터만** 변환한다.
- **원문을 빠뜨리거나 요약하지 않는다.** 모든 산문 문장을 대역으로 옮긴다(학습용 정합성).
- 번역은 자연스러운 한국어 기술 문체. 단 `/study` 처럼 재구성하지 말고 **문장 단위 충실 번역**.
- **코드·명령어·식별자·매니페스트는 번역하지 않고 원문 유지**한다.
- 특정 책·기술 스택을 가정하지 않는다. 용어·코드 언어는 그 챕터 원문에서 그대로 끌어온다.
- `source.bilingual.txt` 는 저작권 보호 원문에 기반한 산출물이므로 **로컬 전용**이다
  (`.gitignore` 의 `chapters/**/source*.txt` 규칙으로 커밋에서 제외된다).
