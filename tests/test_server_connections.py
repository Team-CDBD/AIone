"""화면에서 고르는 접속 프로필 — 저장·검증·전환.

핵심 불변식 두 가지를 지킨다: 비밀번호는 어떤 응답에도 실려 나가지 않는다, 그리고
붙지 못하는 서버는 활성이 되지 않는다(이전 연결이 그대로 살아 있어야 한다).
"""
import pytest

from serverconf.domain import ProfileInvalid, from_row, validate
from serverconf.repository import ConnectionRepository
from serverconf.service import ConnectionService, ProfileNotFound
from serverconf.secrets import PREFIX, PasswordCipher, SecretKeyInvalid
from infra.settings import Settings

BASE = {"name": "운영", "pg_host": "db.local", "pg_database": "companyx", "pg_user": "mcp_reader",
        "pg_password": "s3cret", "ollama_url": "http://ollama:11434"}


# --- 도메인 -----------------------------------------------------------------
def test_필수값이_비면_사유를_한국어로_돌려준다():
    with pytest.raises(ProfileInvalid) as exc: validate({**BASE, "pg_host": "  "})
    assert "pg_host" in str(exc.value)


@pytest.mark.parametrize("field,value", [("pg_port", 0), ("top_k", 99), ("tau", 1.5), ("ollama_url", "ollama:11434")])
def test_범위를_벗어난_값은_거절한다(field, value):
    with pytest.raises(ProfileInvalid): validate({**BASE, field: value})


def test_빈_비밀번호는_변경_없음이다():
    """수정 화면은 비밀번호를 되받아 보여주지 않는다 — 빈 칸이 '지우기'가 되면 안 된다."""
    assert validate({**BASE, "pg_password": ""})["pg_password"] is None
    assert validate(BASE)["pg_password"] == "s3cret"


def test_masked에는_비밀번호가_없다():
    profile = from_row({**BASE, "id": 1, "pg_port": 5432})
    body = profile.masked()
    assert "s3cret" not in repr(body)
    assert body["has_password"] is True and "pg_password" not in body
    assert "s3cret" not in body["pg_dsn"]


def test_dsn은_특수문자를_이스케이프한다():
    assert from_row({**BASE, "pg_user": "us er"}).pg_dsn("p@ss/1") == \
        "postgresql://us%20er:p%40ss%2F1@db.local:5432/companyx"


def test_비밀번호_암호문은_평문을_포함하지_않고_복호화된다():
    from cryptography.fernet import Fernet
    cipher = PasswordCipher(Fernet.generate_key().decode())
    stored = cipher.encrypt("s3cret")
    assert stored.startswith(PREFIX) and "s3cret" not in stored
    assert cipher.decrypt(stored) == "s3cret"


def test_잘못된_키로는_암호문을_복호화할_수_없다():
    from cryptography.fernet import Fernet
    encrypted = PasswordCipher(Fernet.generate_key().decode()).encrypt("s3cret")
    with pytest.raises(SecretKeyInvalid): PasswordCipher(Fernet.generate_key().decode()).decrypt(encrypted)


def test_기존_평문은_마이그레이션_전까지_읽을_수_있다():
    from cryptography.fernet import Fernet
    cipher = PasswordCipher(Fernet.generate_key().decode())
    assert cipher.decrypt("legacy-password") == "legacy-password"
    assert cipher.needs_migration("legacy-password") and not cipher.needs_migration(cipher.encrypt("legacy-password"))


# --- 리포지토리 --------------------------------------------------------------
class RecordingDb:
    def __init__(self, rows=()): self.rows, self.calls = list(rows), []
    def fetch_dicts(self, sql, params=()): self.calls.append((sql, tuple(params))); return list(self.rows)
    def fetch(self, sql, params=()): return [tuple(r.values()) for r in self.fetch_dicts(sql, params)]


def test_수정은_빈_비밀번호를_기존값으로_유지한다():
    db = RecordingDb([{**BASE, "id": 3, "pg_port": 5432}])
    ConnectionRepository(db).update(3, validate({**BASE, "pg_password": ""}))
    sql, params = db.calls[0]
    assert "COALESCE(%s, pg_password)" in sql and None in params


def test_활성화는_해제를_먼저_하고_지정을_나중에_한다():
    """한 문장에 몰면 부분 유니크 인덱스가 중간 상태를 잡아 duplicate key로 터진다.

    원격 실환경에서 실제로 터졌던 경로다 — 두 행이 동시에 is_active=true가 되는 순간이 생겼다.
    """
    db = RecordingDb([{**BASE, "id": 3, "pg_port": 5432, "is_active": True}])
    ConnectionRepository(db).activate(3)
    assert len(db.calls) == 2
    assert "is_active=false" in db.calls[0][0] and "is_active=true" in db.calls[1][0]


def test_리포지토리는_새_비밀번호를_암호화해_DB에_보낸다():
    from cryptography.fernet import Fernet
    cipher = PasswordCipher(Fernet.generate_key().decode())
    db = RecordingDb([{**BASE, "id": 3, "pg_port": 5432, "pg_password": cipher.encrypt("s3cret")}])
    row = ConnectionRepository(db, cipher).create(validate(BASE))
    stored = db.calls[0][1][5]
    assert stored.startswith(PREFIX) and "s3cret" not in stored
    assert row["pg_password"] == "s3cret"


def test_기존_평문_마이그레이션은_한_번만_암호화한다():
    from cryptography.fernet import Fernet
    cipher = PasswordCipher(Fernet.generate_key().decode())
    db = RecordingDb([{"id": 3, "pg_password": "legacy"}])
    assert ConnectionRepository(db, cipher).migrate_plaintext_passwords() == 1
    sql, params = db.calls[1]
    assert "UPDATE server_connections" in sql and params[0].startswith(PREFIX)
    assert "legacy" not in params[0]


def test_마이그레이션_검사는_기존_암호문과_키가_맞는지도_확인한다():
    from cryptography.fernet import Fernet
    encrypted = PasswordCipher(Fernet.generate_key().decode()).encrypt("secret")
    db = RecordingDb([{"id": 3, "pg_password": encrypted}])
    with pytest.raises(SecretKeyInvalid):
        ConnectionRepository(db, PasswordCipher(Fernet.generate_key().decode())).migrate_plaintext_passwords()


# --- 서비스 ------------------------------------------------------------------
class MemoryRepo:
    def __init__(self): self.rows, self.next_id = {}, 1
    def list(self): return [dict(r) for r in self.rows.values()]
    def get(self, i): return dict(self.rows[i]) if i in self.rows else None
    def active(self): return next((dict(r) for r in self.rows.values() if r["is_active"]), None)
    def create(self, values):
        row = {**values, "id": self.next_id, "is_active": False}; self.rows[self.next_id] = row
        self.next_id += 1; return dict(row)
    def update(self, i, values):
        if i not in self.rows: return None
        password = values.get("pg_password") or self.rows[i].get("pg_password")
        self.rows[i].update({**values, "pg_password": password}); return dict(self.rows[i])
    def delete(self, i): return self.rows.pop(i, None) is not None
    def activate(self, i):
        if i not in self.rows: return None
        for row in self.rows.values(): row["is_active"] = False
        self.rows[i]["is_active"] = True; return dict(self.rows[i])
    def deactivate_all(self):
        for row in self.rows.values(): row["is_active"] = False


def fake_probe(profile, password):
    """실환경 probe를 흉내 낸다 — 못 붙는 호스트는 실패로 돌려준다."""
    ok = "unreachable" not in profile.pg_host
    return {"ok": ok, "checks": {"postgres": {"ok": ok, "detail": "" if ok else "이름을 찾을 수 없습니다"}}}


@pytest.fixture
def service(): return ConnectionService(MemoryRepo(), probe=fake_probe)


def test_settings_for는_프로필_항목만_덮어쓴다(service):
    created = service.create({**BASE, "top_k": 7, "tau": 0.6})
    base = Settings(PG_DSN="env-dsn", OLLAMA_URL="http://env:11434", KG_ENGINE="shadow", CONFIG_PG_DSN="config-dsn")
    cfg = service.settings_for(created.id, base)
    assert cfg.PG_DSN == "postgresql://mcp_reader:s3cret@db.local:5432/companyx"
    assert cfg.TOP_K == 7 and cfg.TAU == 0.6 and cfg.OLLAMA_URL == "http://ollama:11434"
    # 프로필이 소유하지 않는 항목은 환경변수가 계속 소유한다. 프로필 저장소도 제자리에 남는다.
    assert cfg.KG_ENGINE == "shadow" and cfg.CONFIG_PG_DSN == "config-dsn"


def test_ollama_주소가_비면_환경변수_값을_그대로_쓴다(service):
    created = service.create({**BASE, "ollama_url": ""})
    assert service.settings_for(created.id, Settings(OLLAMA_URL="http://env:11434")).OLLAMA_URL == "http://env:11434"


def test_없는_프로필은_ProfileNotFound다(service):
    for call in (lambda: service.get(99), lambda: service.delete(99), lambda: service.activate(99),
                 lambda: service.settings_for(99, Settings())):
        with pytest.raises(ProfileNotFound): call()


def test_활성은_항상_하나다(service):
    first, second = service.create(BASE), service.create({**BASE, "name": "개발"})
    service.activate(first.id); service.activate(second.id)
    assert [p.is_active for p in service.list()].count(True) == 1
    assert service.active().id == second.id
