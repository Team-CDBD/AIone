"""접속 프로필의 순수 규칙 — I/O 없음.

화면에서 고른 서버로 갈아끼울 때 필요한 것은 세 가지다: 값이 말이 되는지(validate),
접속 문자열로 어떻게 조립되는지(pg_dsn), 그리고 밖으로 내보낼 때 무엇을 가리는지(masked).
비밀번호는 이 모듈 밖으로 절대 원문으로 나가지 않는다 — masked()가 유일한 노출 경로다.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from urllib.parse import quote

# 프로필이 덮어쓸 수 있는 항목만 여기 둔다. 그 외 Settings 필드는 환경변수가 계속 소유한다.
EDITABLE = ("name", "pg_host", "pg_port", "pg_database", "pg_user", "pg_password",
            "ollama_url", "generate_model", "embed_model", "top_k", "tau")


class ProfileInvalid(ValueError):
    """사용자 입력이 프로필로 성립하지 않는다. 화면에 그대로 보여줄 수 있는 한국어 사유를 담는다."""


@dataclass(frozen=True)
class ConnectionProfile:
    name: str
    pg_host: str
    pg_database: str
    pg_user: str
    pg_port: int = 5432
    ollama_url: str = ""
    generate_model: str = "gemma4:e4b"
    embed_model: str = "nomic-embed-text:latest"
    top_k: int = 5
    tau: float = 0.55
    id: int | None = None
    is_active: bool = False
    has_password: bool = False

    def pg_dsn(self, password: str = "") -> str:
        """비밀번호는 저장된 값을 호출자가 넘긴다 — 프로필 객체는 원문을 들고 다니지 않는다."""
        auth = quote(self.pg_user, safe="")
        if password: auth += ":" + quote(password, safe="")
        return f"postgresql://{auth}@{self.pg_host}:{self.pg_port}/{quote(self.pg_database, safe='')}"

    def masked(self) -> dict:
        """API 응답용. 비밀번호는 값 대신 '설정됨' 여부만 나간다."""
        return {"id": self.id, "name": self.name, "pg_host": self.pg_host, "pg_port": self.pg_port,
                "pg_database": self.pg_database, "pg_user": self.pg_user, "has_password": self.has_password,
                "ollama_url": self.ollama_url, "generate_model": self.generate_model,
                "embed_model": self.embed_model, "top_k": self.top_k, "tau": self.tau,
                "is_active": self.is_active, "pg_dsn": self.pg_dsn()}

    def with_id(self, new_id: int) -> "ConnectionProfile": return replace(self, id=new_id)


def _text(payload: dict, key: str, *, required: bool = False, default: str = "", limit: int = 200) -> str:
    value = payload.get(key, default)
    value = "" if value is None else str(value).strip()
    if required and not value: raise ProfileInvalid(f"{key}은(는) 비워 둘 수 없습니다")
    if len(value) > limit: raise ProfileInvalid(f"{key}이(가) 너무 깁니다 (최대 {limit}자)")
    return value


def _or_default(value, default):
    """비어 있으면 기본값. `or`를 쓰면 0이 '미입력'으로 삼켜져 범위 검사를 지나쳐 버린다."""
    return default if value is None or (isinstance(value, str) and not value.strip()) else value


def validate(payload: dict) -> dict:
    """화면에서 온 dict → 저장 가능한 dict. 실패는 ProfileInvalid로만 나간다."""
    out = {
        "name": _text(payload, "name", required=True, limit=80),
        "pg_host": _text(payload, "pg_host", required=True),
        "pg_database": _text(payload, "pg_database", required=True),
        "pg_user": _text(payload, "pg_user", required=True),
        "ollama_url": _text(payload, "ollama_url", limit=300),
        "generate_model": _text(payload, "generate_model", default="gemma4:e4b"),
        "embed_model": _text(payload, "embed_model", default="nomic-embed-text:latest"),
    }
    try: out["pg_port"] = int(_or_default(payload.get("pg_port"), 5432))
    except (TypeError, ValueError): raise ProfileInvalid("pg_port는 정수여야 합니다") from None
    if not 1 <= out["pg_port"] <= 65535: raise ProfileInvalid("pg_port는 1~65535 범위여야 합니다")
    try: out["top_k"] = int(_or_default(payload.get("top_k"), 5))
    except (TypeError, ValueError): raise ProfileInvalid("top_k는 정수여야 합니다") from None
    if not 1 <= out["top_k"] <= 20: raise ProfileInvalid("top_k는 1~20 범위여야 합니다")
    try: out["tau"] = float(_or_default(payload.get("tau"), 0.55))
    except (TypeError, ValueError): raise ProfileInvalid("tau는 숫자여야 합니다") from None
    if not 0 < out["tau"] < 1: raise ProfileInvalid("tau는 0과 1 사이여야 합니다")
    if out["ollama_url"] and not out["ollama_url"].startswith(("http://", "https://")):
        raise ProfileInvalid("ollama_url은 http:// 또는 https:// 로 시작해야 합니다")
    password = payload.get("pg_password")
    # 빈 문자열/None은 '변경 없음'이다 — 수정 화면이 비밀번호를 되받아 보여주지 않기 때문이다.
    out["pg_password"] = None if password in (None, "") else str(password)
    return out


def from_row(row: dict) -> ConnectionProfile:
    """DB 행 → 프로필. 비밀번호 컬럼은 존재 여부만 읽고 값은 버린다."""
    return ConnectionProfile(
        id=row.get("id"), name=row["name"], pg_host=row["pg_host"], pg_port=int(row.get("pg_port") or 5432),
        pg_database=row["pg_database"], pg_user=row["pg_user"], has_password=bool(row.get("pg_password")),
        ollama_url=row.get("ollama_url") or "", generate_model=row.get("generate_model") or "gemma4:e4b",
        embed_model=row.get("embed_model") or "nomic-embed-text:latest",
        top_k=int(row.get("top_k") or 5), tau=float(row.get("tau") if row.get("tau") is not None else 0.55),
        is_active=bool(row.get("is_active")),
    )
