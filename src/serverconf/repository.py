"""접속 프로필 저장소. SQL 문자열만 갖고 contracts.infra.Db 프로토콜에만 의존한다.

쓰기는 전부 RETURNING을 붙여 fetch_dicts 한 번으로 끝낸다 — PostgresDb가 autocommit이므로
프로토콜을 넓히지 않고도 INSERT/UPDATE/DELETE를 태울 수 있다.
"""
from __future__ import annotations
from typing import Any

TABLE = "server_connections"
COLUMNS = ("id", "name", "pg_host", "pg_port", "pg_database", "pg_user", "pg_password",
           "ollama_url", "generate_model", "embed_model", "top_k", "tau", "is_active")
_SELECT = f"SELECT {', '.join(COLUMNS)} FROM {TABLE}"


class ConnectionRepository:
    def __init__(self, db): self.db = db

    def list(self) -> list[dict[str, Any]]:
        return self.db.fetch_dicts(f"{_SELECT} ORDER BY is_active DESC, name")

    def get(self, profile_id: int) -> dict[str, Any] | None:
        rows = self.db.fetch_dicts(f"{_SELECT} WHERE id = %s", (profile_id,))
        return rows[0] if rows else None

    def active(self) -> dict[str, Any] | None:
        rows = self.db.fetch_dicts(f"{_SELECT} WHERE is_active LIMIT 1")
        return rows[0] if rows else None

    def create(self, values: dict[str, Any]) -> dict[str, Any]:
        return self.db.fetch_dicts(
            f"""INSERT INTO {TABLE}
            (name,pg_host,pg_port,pg_database,pg_user,pg_password,ollama_url,generate_model,embed_model,top_k,tau)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING {', '.join(COLUMNS)}""",
            (values["name"], values["pg_host"], values["pg_port"], values["pg_database"], values["pg_user"],
             values.get("pg_password"), values["ollama_url"], values["generate_model"], values["embed_model"],
             values["top_k"], values["tau"]),
        )[0]

    def update(self, profile_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        # pg_password가 None이면 '변경 없음' — COALESCE로 기존 값을 그대로 둔다.
        rows = self.db.fetch_dicts(
            f"""UPDATE {TABLE} SET name=%s, pg_host=%s, pg_port=%s, pg_database=%s, pg_user=%s,
            pg_password=COALESCE(%s, pg_password), ollama_url=%s, generate_model=%s, embed_model=%s,
            top_k=%s, tau=%s, updated_at=now() WHERE id=%s RETURNING {', '.join(COLUMNS)}""",
            (values["name"], values["pg_host"], values["pg_port"], values["pg_database"], values["pg_user"],
             values.get("pg_password"), values["ollama_url"], values["generate_model"], values["embed_model"],
             values["top_k"], values["tau"], profile_id),
        )
        return rows[0] if rows else None

    def delete(self, profile_id: int) -> bool:
        return bool(self.db.fetch_dicts(f"DELETE FROM {TABLE} WHERE id=%s RETURNING id", (profile_id,)))

    def activate(self, profile_id: int) -> dict[str, Any] | None:
        """해제 → 지정 순서로 두 문장. 한 문장에 넣으면 안 된다.

        server_connections_one_active(부분 유니크 인덱스)는 문장 중간의 값도 검사하므로,
        해제와 지정을 한 문장(데이터 변경 CTE 포함)에 넣으면 두 행이 동시에 true가 되는
        순간에 duplicate key로 터진다 — 실제로 원격 검증에서 터졌다.
        순서가 이렇게 되어 있으므로 '두 개가 활성'인 상태는 생기지 않는다.
        """
        self.db.fetch_dicts(
            f"UPDATE {TABLE} SET is_active=false, updated_at=now() WHERE is_active AND id<>%s RETURNING id",
            (profile_id,),
        )
        rows = self.db.fetch_dicts(
            f"UPDATE {TABLE} SET is_active=true, updated_at=now() WHERE id=%s RETURNING {', '.join(COLUMNS)}",
            (profile_id,),
        )
        return rows[0] if rows else None

    def deactivate_all(self) -> None:
        self.db.fetch_dicts(f"UPDATE {TABLE} SET is_active=false, updated_at=now() WHERE is_active RETURNING id")
