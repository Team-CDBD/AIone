#!/usr/bin/env bash
# 인프라 프로비저닝. 자격증명은 여기서 생성해 .env에만 두고 저장소에는 넣지 않는다.
#
#   ./scripts/setup.sh                 전체 (환경파일 → 점검 → 기동 → 적재 → 검증)
#   ./scripts/setup.sh env             .env만 생성
#   ./scripts/setup.sh check           Ollama/Docker/데이터셋 사전 점검만
#   ./scripts/setup.sh models          필요한 Ollama 모델만 내려받기
#   ./scripts/setup.sh up              컨테이너 기동
#   ./scripts/setup.sh ingest          데이터셋 적재
#   ./scripts/setup.sh verify          기동 후 상태 확인
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ENV_FILE=".env"
DATASET="data/companyx-dataset-v1.0.zip"
say() { printf '\033[1;34m▸\033[0m %s\n' "$*"; }
ok()  { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

secret() {  # 비밀번호 생성. openssl이 없으면 /dev/urandom으로 떨어진다.
  if command -v openssl >/dev/null 2>&1; then openssl rand -hex 16
  else LC_ALL=C tr -dc 'a-f0-9' </dev/urandom | head -c 32; fi
}

detect_ollama() {  # compose 안에서는 호스트를 이름으로 못 찾는다 — 실제 도달 가능한 주소를 고른다.
  local candidates=("${OLLAMA_URL:-}" "http://localhost:11434" "http://host.docker.internal:11434")
  # 기본 게이트웨이(도커 데스크톱·대부분의 리눅스에서 호스트).
  local gw; gw="$(ip route 2>/dev/null | awk '/^default/{print $3; exit}')" || true
  [ -n "${gw:-}" ] && candidates+=("http://${gw}:11434")
  # VM(VMware/VirtualBox NAT)에서는 호스트가 게이트웨이가 아니라 서브넷의 .1인 경우가 흔하다.
  # `ip route`의 default 줄에는 src가 없을 수 있어 route get으로 실제 출발지 주소를 얻는다.
  local self; self="$(ip -4 route get 1.1.1.1 2>/dev/null | sed -n 's/.* src \([0-9.]*\).*/\1/p')" || true
  [ -n "${self:-}" ] && candidates+=("http://${self%.*}.1:11434")
  for url in "${candidates[@]}"; do
    [ -z "$url" ] && continue
    if curl -fsS -m 3 "${url}/api/version" >/dev/null 2>&1; then echo "$url"; return 0; fi
  done
  return 1
}

cmd_env() {
  if [ -f "$ENV_FILE" ]; then
    ok "$ENV_FILE 이미 존재 — 건드리지 않는다"
  else
    say "$ENV_FILE 생성 (비밀번호 자동 생성)"
    local url; url="$(detect_ollama || true)"
    [ -z "$url" ] && { url="http://localhost:11434"; say "Ollama를 못 찾았다 — $ENV_FILE의 OLLAMA_URL을 직접 고쳐라"; }
    cat > "$ENV_FILE" <<EOF
# scripts/setup.sh가 생성했다. 커밋하지 않는다(.gitignore 대상).
OLLAMA_URL=${url}
GENERATE_MODEL=${GENERATE_MODEL:-gemma4:e4b}
EMBED_MODEL=${EMBED_MODEL:-nomic-embed-text:latest}
TOP_K=5
TAU=0.55
WEB_PORT=8080

POSTGRES_DB=companyx
POSTGRES_USER=postgres
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_PASSWORD=$(secret)
MCP_READER_PASSWORD=$(secret)

BUILD_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
EOF
    chmod 600 "$ENV_FILE"
    ok "$ENV_FILE 생성 완료 (권한 600, Ollama=${url})"
  fi
}

cmd_check() {
  command -v docker >/dev/null || die "docker 없음"
  docker compose version >/dev/null 2>&1 || die "docker compose v2 없음"
  ok "docker $(docker --version | awk '{print $3}' | tr -d ,)"
  [ -f "$DATASET" ] && ok "데이터셋 $DATASET" || say "데이터셋 없음: $DATASET (적재 단계에서 필요)"
  # shellcheck disable=SC1090
  [ -f "$ENV_FILE" ] && set -a && . "./$ENV_FILE" && set +a
  # .env의 OLLAMA_URL이라도 실제로 응답하는지 확인한다 — 적어두기만 하고 안 떠 있는 경우가 흔하다.
  local url version
  if ! version="$(curl -fsS -m 5 "${OLLAMA_URL:-}/api/version" 2>/dev/null)"; then
    url="$(detect_ollama || true)"
    [ -z "$url" ] && die "Ollama에 도달할 수 없다(.env OLLAMA_URL=${OLLAMA_URL:-미설정}). 먼저 띄우고 주소를 맞춰라"
    say "'.env'의 OLLAMA_URL이 응답하지 않는다 — 도달 가능한 주소를 찾았다: ${url}"
    version="$(curl -fsS -m 5 "${url}/api/version")"
  else
    url="${OLLAMA_URL}"
  fi
  ok "Ollama $(sed 's/[{}"]//g' <<<"$version")  @ ${url}"
  local have; have="$(curl -fsS -m 10 "${url}/api/tags" | tr ',' '\n' | sed -n 's/.*"name":"\([^"]*\)".*/\1/p')"
  for model in "${GENERATE_MODEL:-gemma4:e4b}" "${EMBED_MODEL:-nomic-embed-text:latest}"; do
    if grep -qxF "$model" <<<"$have"; then ok "모델 $model"
    else say "모델 없음: $model  → ./scripts/setup.sh models"; fi
  done
}

cmd_models() {
  # shellcheck disable=SC1090
  set -a && . "./$ENV_FILE" && set +a
  local url="${OLLAMA_URL:?}"
  for model in "${GENERATE_MODEL}" "${EMBED_MODEL}"; do
    say "pull $model"
    curl -fsS -m 3600 -X POST "${url}/api/pull" -H 'Content-Type: application/json' \
         -d "{\"model\":\"${model}\",\"stream\":false}" >/dev/null || die "pull 실패: $model"
    ok "$model"
  done
}

cmd_up()     { say "컨테이너 기동"; docker compose up -d --build; ok "기동 완료"; }
cmd_ingest() {
  [ -f "$DATASET" ] || die "데이터셋 없음: $DATASET"
  say "데이터셋 적재 (임베딩 포함 — 수 분 걸린다)"
  docker compose run --rm mcp python -m ingest "$DATASET"
  ok "적재 완료"
}
cmd_verify() {
  # shellcheck disable=SC1090
  set -a && . "./$ENV_FILE" && set +a
  say "적재 결과"
  docker compose exec -T postgres psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-companyx}" -t -c \
    "select 'chunks='||(select count(*) from document_chunks)
          ||' nodes='||(select count(*) from kg_nodes)
          ||' edges='||(select count(*) from kg_edges)
          ||' null_embedding='||(select count(*) from document_chunks where embedding is null);"
  say "MCP stdio"
  docker compose run --rm -T mcp python tests/mcp_e2e.py
  if docker compose ps --services --filter status=running | grep -qx web; then
    say "웹 화면"
    curl -fsS -m 10 "http://localhost:${WEB_PORT:-8080}/api/health" && echo
    ok "http://localhost:${WEB_PORT:-8080}"
  fi
}

case "${1:-all}" in
  env) cmd_env ;;
  check) cmd_check ;;
  models) cmd_models ;;
  up) cmd_up ;;
  ingest) cmd_ingest ;;
  verify) cmd_verify ;;
  all) cmd_env; cmd_check; cmd_up; cmd_ingest; cmd_verify
       ok "완료 — 웹 화면: http://localhost:$(grep -E '^WEB_PORT=' "$ENV_FILE" | cut -d= -f2)" ;;
  *) die "알 수 없는 명령: $1 (env|check|models|up|ingest|verify|all)" ;;
esac
