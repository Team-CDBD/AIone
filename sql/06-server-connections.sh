#!/bin/bash
# 화면에서 고르는 접속 프로필 저장소. 05-roles.sh 다음에 실행된다(엔트리포인트는 알파벳 순).
#
# 앱이 평소에 쓰는 mcp_reader는 read-only라 프로필을 저장할 수 없다. 그렇다고 mcp_reader의
# read-only를 풀면 nl2sql의 2차 방어선이 사라진다 — 그래서 이 테이블 전용 계정을 따로 만든다.
set -euo pipefail
: "${MCP_CONFIG_PASSWORD:?compose가 .env의 MCP_CONFIG_PASSWORD를 넘겨야 한다}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v pw="$MCP_CONFIG_PASSWORD" <<'SQL'
CREATE TABLE IF NOT EXISTS server_connections (
  id             serial PRIMARY KEY,
  name           text NOT NULL UNIQUE,
  pg_host        text NOT NULL,
  pg_port        integer NOT NULL DEFAULT 5432 CHECK (pg_port BETWEEN 1 AND 65535),
  pg_database    text NOT NULL,
  pg_user        text NOT NULL,
  pg_password    text,
  ollama_url     text NOT NULL DEFAULT '',
  generate_model text NOT NULL DEFAULT 'gemma4:e4b',
  embed_model    text NOT NULL DEFAULT 'nomic-embed-text:latest',
  top_k          integer NOT NULL DEFAULT 5 CHECK (top_k BETWEEN 1 AND 20),
  tau            double precision NOT NULL DEFAULT 0.55 CHECK (tau > 0 AND tau < 1),
  is_active      boolean NOT NULL DEFAULT false,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);
-- 활성 프로필은 최대 하나. 애플리케이션 규칙이 아니라 스키마 제약으로 못 박는다.
CREATE UNIQUE INDEX IF NOT EXISTS server_connections_one_active
  ON server_connections ((is_active)) WHERE is_active;

DO $$ BEGIN CREATE ROLE mcp_config LOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
ALTER ROLE mcp_config LOGIN PASSWORD :'pw';
GRANT CONNECT ON DATABASE companyx TO mcp_config;
GRANT USAGE ON SCHEMA public TO mcp_config;
-- 이 테이블 하나에만 권한을 준다. 데이터셋 테이블에는 접근할 수 없다.
GRANT SELECT, INSERT, UPDATE, DELETE ON server_connections TO mcp_config;
GRANT USAGE, SELECT ON SEQUENCE server_connections_id_seq TO mcp_config;
ALTER ROLE mcp_config SET statement_timeout='5s';

-- 05-roles.sh의 ALTER DEFAULT PRIVILEGES가 새 테이블에도 SELECT를 주기 때문에,
-- 비밀번호 컬럼이 있는 이 테이블은 명시적으로 회수한다. nl2sql이 쓰는 계정이 mcp_reader다.
REVOKE ALL ON server_connections FROM mcp_reader;
REVOKE ALL ON server_connections FROM PUBLIC;
SQL
