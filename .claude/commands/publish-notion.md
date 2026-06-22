---
description: 가장 최근(또는 지정한) chapterNN.md 학습노트를 MCP로 연결된 노션 페이지에 그대로 발행한다
argument-hint: "[챕터번호 | 노션 부모페이지 URL] (예: /publish-notion · /publish-notion 3)"
allowed-tools: Bash, Read, Write, mcp__claude_ai_Notion__notion-search, mcp__claude_ai_Notion__notion-fetch, mcp__claude_ai_Notion__notion-create-pages, mcp__claude_ai_Notion__notion-update-page, ReadMcpResourceTool
---

# /publish-notion — 학습노트를 노션에 발행

`chapters/chapterNN/chapterNN.md` 학습노트의 **내용을 그대로** 노션 페이지에 올린다.
같은 챕터를 다시 발행하면 새 페이지를 만들지 않고 **기존 페이지를 덮어쓴다**(멱등).
이번 호출의 인자는 `$ARGUMENTS` 다 — 챕터 번호이거나, 처음 발행 시 쓸 노션 부모페이지 URL/ID이거나, 비어 있을 수 있다.

## 절차

### 1. 대상 노트 결정
- `$ARGUMENTS` 에 **숫자**가 있으면 그 챕터를 두 자리로 정규화(`3` → `03`)해
  `chapters/chapter{NN}/chapter{NN}.md` 를 대상으로 한다.
- 숫자가 없으면 **가장 최근에 수정된 노트**를 자동 선택한다(Bash):
  ```bash
  find chapters -name 'chapter*.md' -printf '%T@ %p\n' | sort -rn | head -1
  ```
  경로에서 `{NN}` 을 뽑아낸다.
- 노트 파일이 하나도 없으면 발행하지 말고 멈춘 뒤, 먼저 `/study <챕터번호>` 로
  노트를 만들라고 안내한다.

### 2. 노트 읽기 · 제목/본문 분리
- Read 도구로 대상 `.md` 전체를 읽는다.
- **제목**: 첫 `# ` 헤딩 한 줄에서 `# ` 를 떼어낸 문자열(예: `01. 컨테이너 …`). 이것이 노션 페이지 제목이 된다.
- **본문**: 위 H1 한 줄을 **제외한** 나머지 전체. 노션은 제목을 속성(properties.title)으로 받으므로
  본문 맨 위에 H1 을 중복해 넣지 않는다(나머지 `> 학습일 …` 블록쿼트·`##` 섹션은 그대로 본문에 둔다).

### 3. 노션 마크다운 스펙 확인
콘텐츠를 만들기 전에 MCP 리소스 `notion://docs/enhanced-markdown-spec` 를 **ReadMcpResourceTool 로 한 번 읽어**
노션 표기법(코드블록·표·콜아웃 등)을 확인한다. 표기법을 추측하지 말 것.

### 4. 발행 위치 결정 (멱등 처리)
저장소 루트의 매핑 파일 `notion.json` 을 기준으로 분기한다. 형식:
```json
{ "parent_page_id": "<선택: 새 노트를 만들 부모페이지 ID>",
  "pages": { "01": "<해당 챕터의 노션 page_id>", "02": "..." } }
```

- **재발행** — `notion.json` 의 `pages["{NN}"]` 에 page_id 가 있으면:
  그 페이지를 `notion-update-page`(command `replace_content`, `new_str` = §2 본문)로 **덮어쓴다.**
  제목이 바뀌었으면 같은 호출에서 properties.title 도 갱신한다. → 6번으로.
  본문이 크면 `replace_content` 로 머리말만 덮어쓴 뒤 나머지는 아래 첫 발행과 같은 방식으로
  `insert_content`(`position: end`)로 분할 추가한다.

- **첫 발행** — 매핑이 없으면 부모 위치를 아래 순서로 정한다:
  1. `$ARGUMENTS` 에 노션 URL 또는 ID가 있으면 그것을 부모 `page_id` 로 쓴다.
  2. 없으면 `notion.json` 의 `parent_page_id` 를 쓴다.
  3. 둘 다 없으면 `notion-search` 로 책/노트 제목을 검색해 적절한 부모(예: "학습노트" 페이지)를 찾고,
     **사용자에게 그 페이지에 올려도 되는지 확인**한다. 마땅한 부모가 없으면 어느 페이지/데이터소스
     아래에 만들지 사용자에게 묻고 **멈춘다**(임의로 워크스페이스에 흩뿌리지 않는다).
  - 부모가 정해지면 `notion-create-pages` 로 생성한다:
    `parent` = `{ "type": "page_id", "page_id": "<부모>" }`,
    `properties.title` = §2 제목, `icon` = "📘"(선택).

> **본문이 크면 분할 추가(중요).** 긴 노트를 `notion-create-pages` 의 `content` 에 한 번에
>넣으면 MCP 호출이 페이로드 크기로 반려될 수 있다. 따라서 **생성 시엔 머리말(`> 학습일 …`
> 블록쿼트 + `## 한 줄 요약` 정도)만** `content` 로 넣고, 나머지 섹션은
> `notion-update-page`(command `insert_content`, `position: {"type":"end"}`)로 **여러 번 나눠
> append** 한다. 한 번에 한두 개 `##` 섹션씩 보내면 안정적이다. 코드블록(```text` …)의
> 박스 드로잉 문자는 그대로 둔다.

### 5. 매핑 기록
첫 발행으로 새 페이지를 만들었으면, 반환된 page_id 를 `notion.json` 의 `pages["{NN}"]` 에 적어
Write 로 저장한다(다음 재발행 때 덮어쓰기 위함). 파일이 없으면 새로 만든다.
부모를 인자로 받았다면 `parent_page_id` 에도 기록해 둔다.

### 6. 마무리
생성/갱신한 노션 페이지의 **URL** 과 발행한 챕터(번호·제목)를 사용자에게 보여준다.
재발행이었는지 새로 만들었는지도 한 줄로 알린다.

## 원칙
- **노트 내용을 가공하지 않는다.** `.md` 를 그대로 옮기는 것이 목적이다(요약·재작성 금지).
- **멱등**: 같은 챕터를 여러 번 발행해도 노션에 페이지가 중복 생성되지 않는다 — `notion.json` 매핑이 보장한다.
- **한 번에 한 챕터만** 발행한다.
- `notion.json` 은 개인 워크스페이스 매핑이므로 `.gitignore` 에 넣어 커밋하지 않는 것을 권장한다.
