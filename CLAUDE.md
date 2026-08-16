# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

`doc/시스템설계서.html`의 설계를 계약 우선(contract-first) 레이어드 아키텍처로 구현한 MCP 서버입니다.
CompanyX 데이터셋(문서 202 청크 / KG 노드 133 / 엣지 354)에 대해 `vector_search`, `nl2sql`,
`knowledge_graph` 세 개의 MCP 툴을 stdio로 노출합니다. 인프라는 PostgreSQL(pgvector + pg_trgm)과
Ollama입니다.

## 명령어

```bash
python -m pip install -e '.[test]'      # src/ 레이아웃 패키지 + 테스트 의존성
pytest                                   # 전체 (pythonpath=src, testpaths=tests)
pytest tests/test_tools.py::test_이름 -q  # 단일 테스트
python -m adapters.mcp_sdk_server        # MCP 서버 (stdio)
python -m ingest data/companyx-dataset-v1.0.zip  # 데이터셋 적재(임베딩 포함)
docker compose up -d --build             # postgres(+sql/ 자동 초기화) / ollama / mcp
python tests/mcp_e2e.py                  # 컨테이너 안에서 실행하는 stdio list/call E2E
```

`pytest`로 도는 테스트는 `tests/fakes.py`의 FakeDb/FakeLlm만 쓰므로 DB·Ollama 없이 통과합니다.
`mcp_e2e.py`는 실 인프라가 필요하고 pytest 수집 대상이 아닙니다(파일명이 `test_`로 시작하지 않음).

## 아키텍처

### 레이어 규칙
각 도메인 모듈(`vector`, `nl2sql`, `kg`)은 동일한 4단 구조를 반복합니다.

```
domain/      순수 함수 — I/O 금지 (chunker, rrf, guard, prompt, ontology, planner …)
repository   SQL 문자열만 보유. contracts.infra.Db 프로토콜에만 의존
service      도메인 + repo + LLM 조합, 결과를 *Outcome 데이터클래스로 반환
adapter      Outcome → contracts.tool.ToolResult 변환, Tool 프로토콜 구현
provider     ModuleSpec 조립 — 라우터에 자신을 등록하는 유일한 진입점
```

의존 방향은 항상 adapter → service → (domain, repository) → contracts. 상위 레이어가
`psycopg`/`httpx`를 직접 import하지 않습니다. 구체 구현은 `infra/`(PostgresDb, OllamaClient)에만
존재하고 `router/registry.py`에서 한 번 주입됩니다. 새 모듈을 만들 때도 이 5단을 그대로 따르세요.

### 계약 (`src/contracts/`)
- `tool.py` — 모든 툴의 공통 출력 `ToolResult(status, answer_basis, provenance, candidate_actions, notes, candidates)`.
  `AnswerBasis`는 `__post_init__`에서 `row_count == len(rows)`와 비어 있지 않은 `unit`을 강제하므로
  새 결과 경로를 만들 때 단위 문자열을 반드시 채워야 합니다. 빈 결과는 `empty_result()` 헬퍼 사용.
- `ToolStatus` — ok / empty / entity_not_found / guard_rejected / timeout / upstream_error.
  예외를 밖으로 던지는 대신 이 상태로 변환하는 것이 이 코드베이스의 오류 처리 방식입니다.
- `infra.py` — Db / Llm / Tracer 프로토콜과 DbError·LlmError 계열 예외.

### 모듈 플러그인 계약 (`src/contracts/module.py`)
**라우터는 어떤 모듈도 이름으로 알지 않습니다.** 각 모듈은 `provider.py`에서 `provide(db, llm, cfg)
-> ModuleSpec`을 노출하고, 그 안에 라우터가 필요한 전부를 담습니다.

| 필드 | 의미 |
|---|---|
| `tool` | `Tool` 프로토콜 구현체. 언어·전송 방식은 여기 뒤에 숨는다 |
| `signal` | `SignalSpec` — 키워드/가중치/정규식 보너스/엔터티 보너스 |
| `build_params` | `(question, entities) -> params`. 툴별 파라미터 조립 책임이 모듈에 있다 |
| `tacc_profile`, `guideline` | 컨텍스트 조립 시 사용할 프로파일과 [G] 지침 |
| `resolver` | 선택. 이 모듈이 제공하는 엔터티 해소기 |

모듈 추가/제거는 `router/registry.py`의 `DEFAULT_PROVIDERS`(`"pkg.provider:provide"` 문자열)만
고치면 됩니다. `build_registry(..., providers=[...])`로 주입하면 코어 3종 없이도 구성됩니다.
`ToolName`은 내장 3종의 상수일 뿐이고 레지스트리 키는 일반 문자열이므로 새 모듈은 임의 이름을
쓸 수 있습니다.

### 라우팅 흐름 (`src/router/`)
`RuleRouter.route()`는 등록된 `ModuleSpec`의 `signal` 목록만 `domain/rules.score_question()`에
넘깁니다(모듈별 분기 없음). 점수를 정규화해 1위가 `TAU`(0.55) 이상이고 2위와 `DELTA`(0.15) 이상
벌어지면 **Stage A**(단일 툴), 아니면 **Stage C**(전 툴 실행 후 상태·행 수로 재정렬).
`route()`는 **항상 리스트**를 반환합니다. `Orchestrator.answer()`가 승자 결과를
`domain/tacc.compose_context(result, profile, guideline)`로 K/A/D/G 컨텍스트로 만들어 LLM에
넘기고, LLM 실패 시 `domain/composer.fallback_table()`로 비-LLM 표를 반환합니다.

**장애 격리** — 모듈 하나가 죽어도 라우팅 전체는 살아 있어야 합니다:
`CompositeResolver`(`router/resolvers.py`)가 개별 해소기 예외를 삼켜 `entities=[]`로 진행하고,
`Orchestrator.call_tool()`이 어댑터가 놓친 예외를 `UPSTREAM_ERROR`로 바꿉니다. 실패 결과는
랭킹에서 자연히 뒤로 밀립니다. 이 성질은 `tests/test_router_plugins.py`가 지킵니다 —
모듈을 원격/타 언어로 분리할 때 반드시 통과해야 하는 회귀 테스트입니다.

`rules/router_rules.yaml`은 **오버레이**입니다. 키워드 신호는 각 모듈의 `SIGNAL`이 소유하고,
yaml은 `tau`/`delta`/`weights`만 코드 수정 없이 덮어씁니다.

### 모듈별 핵심 불변식
- **nl2sql** — `domain/guard.py`가 유일한 보안 경계: 단일 SELECT/CTE만, 주석·금지 키워드 차단,
  `ALLOWED_TABLES` 화이트리스트, LIMIT 강제 주입(max 1000). 가드 거절이나 DB 오류 시
  `SqlService`가 `append_correction`으로 **1회만** 재시도합니다. DB 측에서도 `sql/05-roles.sql`의
  `mcp_reader`(read-only, statement_timeout 5s)로 이중 방어합니다.
- **vector** — 벡터 랭킹 + 트라이그램 랭킹을 `domain/rrf.fuse()`로 융합. 임베딩 실패 시 예외 대신
  `degraded="keyword_only"`로 강등, `doc_type` 필터로 0건이면 필터를 풀고 1회 재검색.
- **kg** — `resolver.py`가 exact → alias → trigram(0.45) 순으로 개체 해소, 실패 시
  `entity_not_found` + 후보 목록. `repository.traverse()`의 재귀 CTE가 경로 순환을 막고
  relation/target_type/hop을 파라미터로 제한합니다.

### 운영 설정
튜닝 노브는 `TOP_K`와 `TAU` 두 개뿐이라는 것이 설계 제약입니다. 그 외 환경변수는 접속 정보
(`PG_DSN`, `OLLAMA_URL`, `GENERATE_MODEL`, `EMBED_MODEL`)이며 모두 `infra/settings.py`의
`Settings.from_env()` 한 곳에서만 읽습니다.

### 데이터
`sql/`은 compose가 알파벳 순으로 자동 실행합니다(`02` 관계형 스키마는 데이터셋 zip에서 옴).
`ingest.py`는 청크/노드/엣지 개수와 임베딩 차원(768)을 하드 검증하여 계약 위반 시 중단합니다.

## 코드 스타일

기존 코드는 의도적으로 압축되어 있습니다 — 한 줄 `__init__`, 세미콜론 결합문, 짧은 함수 본문.
수정 시 주변 파일의 밀도를 따르고, `domain/` 안에는 I/O를 넣지 마세요. 사용자 노출 문자열
(unit, reason, note)은 한국어입니다.
