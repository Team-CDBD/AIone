"""2026-08-25 합성 홀드아웃에서 드러난 일반화 결함의 회귀 방어.

개발셋 30문항은 30/30이었지만 새 표현 20문항에서는 종단 55%였다. 여기 있는 것은
그때 실패한 경로들이며, 개발셋만 보고는 잡히지 않는다.
"""
import pytest

from contracts.resolver import Resolution
from router.domain.scope import out_of_scope


class StubRepo:
    """이름 일치는 정확히, 부분 문자열 탐지는 DB와 같은 규칙으로 흉내낸다."""
    NODES = {"client_26": ("Client-Z", "client"), "client_1": ("Client-A", "client"),
             "dept_5": ("데이터플랫폼팀", "department")}

    def exact_by_name(self, value):
        for node_id, (name, kind) in self.NODES.items():
            if name.lower() == value: return {"node_id": node_id, "name": name, "node_type": kind}
        return None
    exact_by_compact_name = exact_by_name
    def by_id(self, node_id): return None
    @staticmethod
    def _trigrams(value):
        """pg_trgm과 같은 방식으로 센다 — 문자 집합이 아니라 3-gram이어야
        'client-zzz'와 'client-z'가 구별된다."""
        padded = f"  {value.lower()} "
        return {padded[i:i + 3] for i in range(len(padded) - 2)}

    def trigram_top(self, value, limit):
        want = self._trigrams(value)
        scored = []
        for node_id, (name, kind) in self.NODES.items():
            have = self._trigrams(name)
            sim = len(want & have) / max(len(want | have), 1)
            scored.append({"node_id": node_id, "name": name, "node_type": kind, "sim": sim})
        return sorted(scored, key=lambda row: -row["sim"])[:limit]
    def names_in_text(self, text):
        return [{"node_id": node_id, "name": name, "node_type": kind}
                for node_id, (name, kind) in self.NODES.items() if name.lower() in text.lower()]


@pytest.fixture
def resolver():
    from kg.resolver import KgEntityResolver
    return KgEntityResolver(StubRepo())


def test_미등록_식별자는_짧은_이름으로_조용히_치환되지_않는다(resolver):
    """GH-U-02. Client-ZZZ를 물었는데 provenance는 client_26(Client-Z)였고 실제 값을 반환했다.

    식별자 해소는 엄격했지만 names_in_text()가 긴 문자열 안의 짧은 이름을 부분 문자열로
    다시 찾아내 ID 보호를 우회했다. 설계서의 환각 방지 100% 요구를 직접 위반한다.
    """
    found = [item for item in resolver.find_all("Client-ZZZ가 사용 중인 제품 목록을 보여줘") if item.node_id]
    assert found == [], f"미등록 식별자가 치환됐다: {[(f.node_id, f.name) for f in found]}"


def test_실제로_존재하는_식별자는_그대로_해소된다(resolver):
    resolved = [item for item in resolver.find_all("Client-A가 사용 중인 제품은?") if item.node_id]
    assert [item.name for item in resolved] == ["Client-A"]


def test_한글로_적은_식별자를_해소한다(resolver):
    """GH-T-01. '클라이언트A가 쓰는 프로덕트'가 entity_not_found였다."""
    resolved = [item for item in resolver.find_all("클라이언트A가 쓰는 프로덕트 뭐뭐 있어?") if item.node_id]
    assert [item.name for item in resolved] == ["Client-A"]


def test_오탈자가_있는_한글_이름을_해소한다(resolver):
    """GH-T-04. '데이터플렛폼팀'(랫→렛)이 entity_not_found였다."""
    resolved = [item for item in resolver.find_all("데이터플렛폼팀 사람들 누구임?") if item.node_id]
    assert "데이터플랫폼팀" in [item.name for item in resolved]


@pytest.mark.parametrize("question", ["내일 서울 날씨와 강수 확률을 알려줘",
                                      "우리 팀 전원에게 회의 초대 이메일을 보내줘"])
def test_범위_밖_질문은_거부한다(question):
    """GH-O-01/02. 둘 다 근거가 약한데 vector_search로 라우팅됐다."""
    verdict = out_of_scope(question)
    assert verdict is not None, question


@pytest.mark.parametrize("question", ["Product-C1 설치 방법이 궁금해", "2025년 3분기 총 매출액은 얼마야?",
                                      "가장 많은 고객을 담당하는 직원은?", "미해결 티켓 목록을 보여줘",
                                      "회의록에서 논의된 일정 지연 이슈를 알려줘"])
def test_정상_질문은_범위_밖으로_보지_않는다(question):
    assert out_of_scope(question) is None, question


def test_모듈이_주제를_신고하면_범위_안이다():
    """라우터가 특정 주제를 아는 게 아니라, 등록된 모듈이 무엇을 다루는지가 판정을 바꾼다."""
    assert out_of_scope("내일 서울 날씨 알려줘") is not None
    assert out_of_scope("내일 서울 날씨 알려줘", claimed=("날씨",)) is None


def test_이름이_겹치는_키워드는_한_번만_센다():
    """'접수'와 '접수된'이 같은 자리를 두 번 세면, 동의어를 넓힌 모듈이 근거 없이 이긴다.

    실제로 KG에 '접수'를 추가하자 GH-B-01(제품마다 접수된 지원 티켓 건수 → NL2SQL)이
    KG로 넘어갔다. 점수 7.0 = 3.5 × 2였다.
    """
    from contracts.module import SignalSpec
    from router.domain.rules import score_question

    signals = [SignalSpec(tool="kg", weight=3.5, keywords=("접수", "접수된")),
               SignalSpec(tool="sql", weight=3.0, keywords=("건수",))]
    scored = {item.tool: item.evidence for item in score_question("접수된 티켓 건수", False, signals=signals)}
    assert scored["kg"] == 3.5, "겹치는 키워드가 두 번 세졌다"
    assert scored["sql"] == 3.0
