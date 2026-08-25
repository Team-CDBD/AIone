"""접속 프로필 저장소. SQL 문자열만 갖고 contracts.infra.Db 프로토콜에만 의존한다.

쓰기는 전부 RETURNING을 붙여 fetch_dicts 한 번으로 끝낸다 — PostgresDb가 autocommit이므로
프로토콜을 넓히지 않고도 INSERT/UPDATE/DELETE를 태울 수 있다.
"""
from __future__ import annotations
from typing import Any
from .secrets import PasswordCipher

TABLE = "server_connections"
COLUMNS = ("id", "name", "pg_host", "pg_port", "pg_database", "pg_user", "pg_password",
           "ollama_url", "generate_model", "embed_model", "top_k", "tau", "is_active")
_SELECT = f"SELECT {', '.join(COLUMNS)} FROM {TABLE}"


class ConnectionRepository:
    def __init__(self, db, cipher: PasswordCipher | None = None): self.db, self.cipher = db, cipher

    def _out(self, row: dict[str, Any]) -> dict[str, Any]:
        row = dict(row)
        if self.cipher: row["pg_password"] = self.cipher.decrypt(row.get("pg_password"))
        return row

    def _password(self, value: str | None) -> str | None:
        return self.cipher.encrypt(value) if self.cipher else value

    def list(self) -> list[dict[str, Any]]:
        return [self._out(row) for row in self.db.fetch_dicts(f"{_SELECT} ORDER BY is_active DESC, name")]

    def get(self, profile_id: int) -> dict[str, Any] | None:
        rows = self.db.fetch_dicts(f"{_SELECT} WHERE id = %s", (profile_id,))
        return self._out(rows[0]) if rows else None

    def active(self) -> dict[str, Any] | None:
        rows = self.db.fetch_dicts(f"{_SELECT} WHERE is_active LIMIT 1")
        return self._out(rows[0]) if rows else None

    def create(self, values: dict[str, Any]) -> dict[str, Any]:
        row = self.db.fetch_dicts(
            f"""INSERT INTO {TABLE}
            (name,pg_host,pg_port,pg_database,pg_user,pg_password,ollama_url,generate_model,embed_model,top_k,tau)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING {', '.join(COLUMNS)}""",
            (values["name"], values["pg_host"], values["pg_port"], values["pg_database"], values["pg_user"],
             self._password(values.get("pg_password")), values["ollama_url"], values["generate_model"], values["embed_model"],
             values["top_k"], values["tau"]),
        )[0]
        return self._out(row)

    def update(self, profile_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        # pg_password가 None이면 '변경 없음' — COALESCE로 기존 값을 그대로 둔다.
        rows = self.db.fetch_dicts(
            f"""UPDATE {TABLE} SET name=%s, pg_host=%s, pg_port=%s, pg_database=%s, pg_user=%s,
            pg_password=COALESCE(%s, pg_password), ollama_url=%s, generate_model=%s, embed_model=%s,
            top_k=%s, tau=%s, updated_at=now() WHERE id=%s RETURNING {', '.join(COLUMNS)}""",
            (values["name"], values["pg_host"], values["pg_port"], values["pg_database"], values["pg_user"],
             self._password(values.get("pg_password")), values["ollama_url"], values["generate_model"], values["embed_model"],
             values["top_k"], values["tau"], profile_id),
        )
        return self._out(rows[0]) if rows else None

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
        return self._out(rows[0]) if rows else None

    def deactivate_all(self) -> None:
        self.db.fetch_dicts(f"UPDATE {TABLE} SET is_active=false, updated_at=now() WHERE is_active RETURNING id")

    def migrate_plaintext_passwords(self) -> int:
        """기존 평문을 같은 키의 암호문으로 제자리 회전한다. 반복 실행해도 이미 암호화된 행은 건드리지 않는다."""
        if not self.cipher: return 0
        rows = self.db.fetch_dicts(f"SELECT id, pg_password FROM {TABLE} WHERE pg_password IS NOT NULL")
        changed = 0
        for row in rows:
            if self.cipher.needs_migration(row.get("pg_password")):
                self.db.fetch_dicts(
                    f"UPDATE {TABLE} SET pg_password=%s, updated_at=now() WHERE id=%s RETURNING id",
                    (self.cipher.encrypt(row["pg_password"]), row["id"]),
                )
                changed += 1
            else:
                # 기동 때 키를 검증한다. 잘못된 키로 store=true가 된 뒤 첫 요청에서 500이 나면 안 된다.
                self.cipher.decrypt(row.get("pg_password"))
        return changed
