# AIone

시스템 설계서의 네 모듈을 계약 우선·레이어드 아키텍처로 구현한 Python 프로젝트입니다.

- `vector`: 문서 청킹, 문맥 보강, RRF 하이브리드 검색
- `nl2sql`: 스키마 기반 SQL 생성, 읽기 전용 Guard, 실행
- `kg`: 온톨로지, 엔터티 해소, 제한된 그래프 탐색
- `router`: 규칙 기반 라우팅, TACC 컨텍스트 구성, 오케스트레이션

## 처음 세팅

```bash
./scripts/setup.sh          # .env 생성 → 사전 점검 → 기동 → 적재 → 검증
```

`.env`를 손으로 만들지 마세요. 스크립트가 **DB 비밀번호를 무작위로 생성**하고
**도달 가능한 Ollama 주소를 탐지**해 채웁니다(`.env`는 커밋 대상이 아닙니다).
단계별로 실행할 수도 있습니다.

```bash
./scripts/setup.sh env      # .env만 생성
./scripts/setup.sh check    # Docker/Ollama/모델/데이터셋 사전 점검
./scripts/setup.sh models   # 필요한 Ollama 모델 내려받기
./scripts/setup.sh up       # 컨테이너 기동
./scripts/setup.sh ingest   # 데이터셋 적재(임베딩 포함)
./scripts/setup.sh verify   # 적재 결과·MCP stdio·웹 화면 확인
```

사전 조건은 Docker Compose v2와 **별도로 떠 있는 Ollama**입니다 — compose는 Ollama를 띄우지 않습니다.

## 인터페이스

| 경로 | 진입점 | 용도 |
|---|---|---|
| MCP stdio | `python -m adapters.mcp_sdk_server` | MCP 클라이언트 (기본 CMD) |
| 웹 화면 | `python -m adapters.http_server` | 브라우저 — `http://localhost:8080` |
| AirMCP stdio | `node mcp-air/dist/index.js` | TypeScript 경로 |

세 경로 모두 같은 registry/router를 쓰고 전송 방식만 다릅니다.
웹 화면은 자연어 질의 탭(라우팅 근거·근거 행 표시)과 도구 콘솔 탭(파라미터 직접 호출)을 제공합니다.

## 개발

```bash
python -m pip install -e '.[test]'
pytest
```

운영 조정값은 `TOP_K`와 `TAU` 두 개뿐입니다. 접속 정보(`PG_DSN`, `OLLAMA_URL`,
`POSTGRES_PASSWORD`, `MCP_READER_PASSWORD`)와 프로필 암호화 키(`PROFILE_ENCRYPTION_KEY`)는 모두 `.env`에서 오며 **코드와 저장소에는
자격증명을 두지 않습니다** — `tests/test_deploy_config.py`가 이를 지킵니다.

접속 프로필의 PostgreSQL 비밀번호는 `PROFILE_ENCRYPTION_KEY`로 암호화해 DB에 저장합니다.
기존 `.env`는 `./scripts/setup.sh env`를 한 번 실행하면 키가 추가되고, 웹 서비스가 다음에 뜰 때
기존 평문 행을 자동으로 암호문으로 전환합니다. 키를 잃거나 임의로 교체하면 저장된 비밀번호를
복호화할 수 없으므로 DB 백업과 별도로 안전하게 보관해야 합니다.

고정 oracle 일반화 평가는 다음처럼 실행합니다. 출력의 `freeze_sha256`가 평가 세트 버전을 봉인합니다.
실패를 보고 규칙을 조정했다면 같은 파일의 결과를 블라인드 수치로 재사용하지 말고 새 세트 버전을 만드세요.

```bash
docker compose run --rm mcp python tools/evaluate_generalization.py \
  --out /tmp/generalization.json
```

## 라이선스

이 저장소에서 직접 작성한 코드는 **Apache License 2.0**을 따릅니다 — 전문은 루트의
[`LICENSE`](LICENSE)에 있습니다. 편입한 제3자 자산의 출처와 라이선스는
[`THIRD_PARTY_NOTICES`](THIRD_PARTY_NOTICES)에 따로 기재합니다.
