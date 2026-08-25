"""프로필 CRUD와 '어느 서버에 붙을지'의 결정. 도메인 + 리포지토리 조합 레이어.

비밀번호 원문은 이 레이어 밖으로 나가지 않는다. 밖으로 나가는 것은 masked() 딕셔너리이거나,
접속에 바로 쓰이는 Settings뿐이다.
"""
from __future__ import annotations
from dataclasses import replace

from infra.settings import Settings
from .domain import ConnectionProfile, ProfileInvalid, from_row, validate


class ProfileNotFound(LookupError): pass


class ConnectionService:
    def __init__(self, repo, probe=None):
        self.repo = repo
        self._probe = probe or _default_probe

    # --- 조회 -------------------------------------------------------------
    def list(self) -> list[ConnectionProfile]:
        return [from_row(row) for row in self.repo.list()]

    def get(self, profile_id: int) -> ConnectionProfile:
        row = self.repo.get(int(profile_id))
        if row is None: raise ProfileNotFound(f"프로필 {profile_id}을(를) 찾을 수 없습니다")
        return from_row(row)

    def active(self) -> ConnectionProfile | None:
        row = self.repo.active()
        return from_row(row) if row else None

    # --- 변경 -------------------------------------------------------------
    def create(self, payload: dict) -> ConnectionProfile:
        return from_row(self.repo.create(validate(payload)))

    def update(self, profile_id: int, payload: dict) -> ConnectionProfile:
        row = self.repo.update(int(profile_id), validate(payload))
        if row is None: raise ProfileNotFound(f"프로필 {profile_id}을(를) 찾을 수 없습니다")
        return from_row(row)

    def delete(self, profile_id: int) -> None:
        if not self.repo.delete(int(profile_id)):
            raise ProfileNotFound(f"프로필 {profile_id}을(를) 찾을 수 없습니다")

    def activate(self, profile_id: int) -> ConnectionProfile:
        row = self.repo.activate(int(profile_id))
        if row is None: raise ProfileNotFound(f"프로필 {profile_id}을(를) 찾을 수 없습니다")
        return from_row(row)

    def deactivate(self) -> None:
        """환경변수 설정으로 되돌린다 — 프로필을 지우지 않고 활성만 해제한다."""
        self.repo.deactivate_all()

    # --- 접속 -------------------------------------------------------------
    def settings_for(self, profile_id: int, base: Settings) -> Settings:
        """프로필이 소유한 항목만 base 위에 덮어쓴다. 나머지(KG_ENGINE 등)는 환경변수가 계속 소유한다."""
        row = self.repo.get(int(profile_id))
        if row is None: raise ProfileNotFound(f"프로필 {profile_id}을(를) 찾을 수 없습니다")
        return _settings(from_row(row), row.get("pg_password") or "", base)

    def probe(self, profile_id: int | None = None, payload: dict | None = None) -> dict:
        """저장 전에도(payload) 저장 후에도(id) 접속을 시험할 수 있어야 한다."""
        if profile_id is not None:
            row = self.repo.get(int(profile_id))
            if row is None: raise ProfileNotFound(f"프로필 {profile_id}을(를) 찾을 수 없습니다")
            profile, password = from_row(row), (row.get("pg_password") or "")
        else:
            values = validate(payload or {})
            profile = from_row({**values, "id": None, "is_active": False})
            password = values.get("pg_password") or ""
        return self._probe(profile, password)


def _settings(profile: ConnectionProfile, password: str, base: Settings) -> Settings:
    return replace(
        base, PG_DSN=profile.pg_dsn(password), OLLAMA_URL=profile.ollama_url or base.OLLAMA_URL,
        GENERATE_MODEL=profile.generate_model, EMBED_MODEL=profile.embed_model,
        TOP_K=profile.top_k, TAU=profile.tau,
    )


def _default_probe(profile: ConnectionProfile, password: str) -> dict:
    """접속을 실제로 열어 본다. 실패는 예외가 아니라 항목별 사유로 돌려준다 — 화면이 그대로 보여준다."""
    checks: dict[str, dict] = {}
    try:
        from infra.db import probe_dsn
        probe_dsn(profile.pg_dsn(password))
        checks["postgres"] = {"ok": True, "detail": f"{profile.pg_host}:{profile.pg_port}/{profile.pg_database}"}
    except Exception as exc:
        checks["postgres"] = {"ok": False, "detail": _reason(exc, password)}
    url = profile.ollama_url
    if not url:
        checks["ollama"] = {"ok": None, "detail": "주소 미설정 — 환경변수 값을 그대로 씁니다"}
    else:
        try:
            import httpx
            response = httpx.get(url.rstrip("/") + "/api/version", timeout=5)
            response.raise_for_status()
            checks["ollama"] = {"ok": True, "detail": response.text.strip()[:120]}
        except Exception as exc:
            checks["ollama"] = {"ok": False, "detail": _reason(exc, password)}
    return {"ok": all(c["ok"] is not False for c in checks.values()), "checks": checks}


def _reason(exc: Exception, password: str) -> str:
    """드라이버 예외 메시지에 DSN이 통째로 실려 오는 경우가 있다 — 비밀번호를 지우고 내보낸다."""
    text = f"{type(exc).__name__}: {exc}"
    return text.replace(password, "***") if password else text
