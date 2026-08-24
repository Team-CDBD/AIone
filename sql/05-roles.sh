#!/bin/bash
# postgres 엔트리포인트가 알파벳 순으로 실행한다. 읽기 전용 계정의 비밀번호는 코드에 두지 않고
# 환경변수로 받는다 — 예전 05-roles.sql에는 'mcp_reader'가 평문으로 박혀 저장소에 커밋돼 있었다.
set -euo pipefail
: "${MCP_READER_PASSWORD:?compose가 .env의 MCP_READER_PASSWORD를 넘겨야 한다}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v pw="$MCP_READER_PASSWORD" <<'SQL'
DO $$ BEGIN CREATE ROLE mcp_reader LOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
ALTER ROLE mcp_reader LOGIN PASSWORD :'pw';
GRANT CONNECT ON DATABASE companyx TO mcp_reader;
GRANT USAGE ON SCHEMA public TO mcp_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO mcp_reader;
ALTER ROLE mcp_reader SET statement_timeout='5s';
ALTER ROLE mcp_reader SET default_transaction_read_only=on;
SQL
