"""배포 설정에 자격증명이 박히지 않았는지 지킨다 — 저장소에 커밋되는 파일들이다."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRACKED = ["docker-compose.yml", ".env.example", "sql/05-roles.sh"]
# 과거에 실제로 커밋돼 있던 값들. 다시 들어오면 실패한다.
# 이 파일 자체에 문자열을 그대로 적지 않는다 — 유출값을 저장소에 다시 심는 꼴이고
# 비밀 스캐너도 이 파일을 계속 물고 늘어진다. 조각을 합쳐서 만든다.
_ROLE = "mcp" + "_reader"
_SUPER = "post" + "gres"
LEAKED = (f"{_ROLE}:{_ROLE}", f"POSTGRES_PASSWORD: {_SUPER}", f"PASSWORD '{_ROLE}'")


@pytest.mark.parametrize("name", TRACKED)
def test_배포_설정에_평문_자격증명이_없다(name):
    path = ROOT / name
    if not path.exists(): pytest.skip(f"{name} 없음")
    text = path.read_text(encoding="utf-8")
    for leaked in LEAKED:
        assert leaked not in text, f"{name}에 자격증명이 다시 박혔다: {leaked}"


def test_비밀번호에는_compose_기본값이_없다():
    """기본값이 있으면 아무도 바꾸지 않고 그대로 배포된다 — :? 로 강제해야 한다."""
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for var in ("POSTGRES_PASSWORD", "MCP_READER_PASSWORD"):
        assert re.search(rf"\$\{{{var}:\?", text), f"{var}에 :? 강제가 없다"
        assert not re.search(rf"\$\{{{var}:-", text), f"{var}에 기본값이 있다"


def test_예시_파일에_사설_IP가_없다():
    """특정 환경의 주소가 예시로 박혀 있으면 다른 환경에서 조용히 잘못된 곳을 가리킨다."""
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert not re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", text)


def test_설정에는_자격증명_기본값이_없다():
    """코드에 박힌 비밀번호는 저장소에 그대로 커밋된다 — 기본값은 비어 있어야 한다."""
    from infra.settings import Settings

    assert Settings().PG_DSN == ""
    assert Settings().OLLAMA_URL == ""
