from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Literal, Mapping

from contracts.module import ModuleSpec
from contracts.resolver import EntityResolver, Resolution
from .domain.rules import ScoredRoute, score_question
from .domain.scope import out_of_scope
from .resolvers import CompositeResolver

AMBIGUOUS_PROFILE = "fallback_ambiguous"
# 한 문장이 두 가지를 동시에 요구하는 표지. 강한 신호 하나로 단정하면 나머지 절의 답을 잃는다.
COMPOUND = re.compile(
    r"(?:그리고|및|,)\s*\S+|(?:하고|찾고|보고)\s"
    r"|(?:와|과|도).{0,32}(?:함께|같이|각각|둘\s*다|동시에|도\s*(?:알려|확인|필요|찾))"
)


@dataclass(frozen=True)
class RouteDecision:
    tool: str; params: dict[str, Any]; confidence: float; stage: Literal["A", "B", "C"]
    runner_up: tuple[str, float] | None; tacc_profile: str; entities: list[Resolution]; guideline: str = ""


class RuleRouter:
    """등록된 ModuleSpec 집합에만 의존한다. 모듈을 추가/교체/원격화해도 이 클래스는 바뀌지 않는다."""
    DELTA = .15
    # 점수는 합으로 정규화되므로 경쟁 모듈이 조용하기만 하면 스친 키워드 하나도 점유율 1.0이 된다.
    # 단독 키워드 1회(weight 3.0)보다 큰 원점수를 요구해 '조용해서 1위'가 Stage A로 확정되는 것을 막는다.
    MIN_EVIDENCE = 3.5

    def __init__(self, specs: Mapping[str, ModuleSpec], resolver: EntityResolver | None = None,
                 tau: float = .55, delta: float | None = None, min_evidence: float | None = None):
        self.specs = dict(specs)
        self.resolver = resolver if resolver is not None else CompositeResolver(
            [spec.resolver for spec in self.specs.values() if spec.resolver is not None])
        self.tau, self.delta = tau, self.DELTA if delta is None else delta
        self.min_evidence = self.MIN_EVIDENCE if min_evidence is None else min_evidence

    def route(self, question: str) -> list[RouteDecision]:
        if not self.specs: return []
        # 점수를 내기 전에 판단한다 — 상대 점수만으로는 답할 수 없는 질문도 항상 1위가 생긴다.
        # 판정 근거는 등록된 모듈이 신고한 키워드다. 날씨 모듈을 꽂으면 날씨는 범위 안이 된다.
        if out_of_scope(question, self._claimed_terms()): return []
        try: entities = self.resolver.find_all(question)
        except Exception: entities = []
        scores = score_question(question, bool(entities), signals=[spec.signal for spec in self.specs.values()])
        if not scores: return []
        best, second = scores[0], scores[1] if len(scores) > 1 else None
        runner_up = (second.tool, second.score) if second else None
        decisive = (best.evidence >= self.min_evidence
                    and (second is None or (best.score >= self.tau and best.score - second.score >= self.delta)))
        # 복합 절인데 다른 모듈도 근거를 갖고 있으면 단정하지 않는다.
        if decisive and COMPOUND.search(question) and sum(1 for item in scores if item.evidence > 0) > 1:
            decisive = False
        stage: Literal["A", "C"] = "A" if decisive else "C"
        selected = scores[:1] if decisive else scores
        return [self._decision(item, question, stage, runner_up, entities) for item in selected]

    def _claimed_terms(self) -> tuple[str, ...]:
        return tuple(term for spec in self.specs.values() for term in spec.signal.keywords)

    def _decision(self, scored: ScoredRoute, question: str, stage: Literal["A", "C"], runner_up, entities) -> RouteDecision:
        spec = self.specs[scored.tool]
        try: params = spec.build_params(question, entities)
        except Exception: params = {}
        profile = spec.tacc_profile if stage != "C" else AMBIGUOUS_PROFILE
        return RouteDecision(spec.name, params, scored.score, stage, runner_up, profile, entities, spec.guideline)
