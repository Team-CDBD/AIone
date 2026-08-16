from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Literal, Mapping

from contracts.module import ModuleSpec
from contracts.resolver import EntityResolver, Resolution
from .domain.rules import ScoredRoute, score_question
from .resolvers import CompositeResolver

AMBIGUOUS_PROFILE = "fallback_ambiguous"


@dataclass(frozen=True)
class RouteDecision:
    tool: str; params: dict[str, Any]; confidence: float; stage: Literal["A", "B", "C"]
    runner_up: tuple[str, float] | None; tacc_profile: str; entities: list[Resolution]; guideline: str = ""


class RuleRouter:
    """등록된 ModuleSpec 집합에만 의존한다. 모듈을 추가/교체/원격화해도 이 클래스는 바뀌지 않는다."""
    DELTA = .15

    def __init__(self, specs: Mapping[str, ModuleSpec], resolver: EntityResolver | None = None,
                 tau: float = .55, delta: float | None = None):
        self.specs = dict(specs)
        self.resolver = resolver if resolver is not None else CompositeResolver(
            [spec.resolver for spec in self.specs.values() if spec.resolver is not None])
        self.tau, self.delta = tau, self.DELTA if delta is None else delta

    def route(self, question: str) -> list[RouteDecision]:
        if not self.specs: return []
        try: entities = self.resolver.find_all(question)
        except Exception: entities = []
        scores = score_question(question, bool(entities), signals=[spec.signal for spec in self.specs.values()])
        if not scores: return []
        best, second = scores[0], scores[1] if len(scores) > 1 else None
        runner_up = (second.tool, second.score) if second else None
        decisive = second is None or (best.score >= self.tau and best.score - second.score >= self.delta)
        stage: Literal["A", "C"] = "A" if decisive else "C"
        selected = scores[:1] if decisive else scores
        return [self._decision(item, question, stage, runner_up, entities) for item in selected]

    def _decision(self, scored: ScoredRoute, question: str, stage: Literal["A", "C"], runner_up, entities) -> RouteDecision:
        spec = self.specs[scored.tool]
        try: params = spec.build_params(question, entities)
        except Exception: params = {}
        profile = spec.tacc_profile if stage != "C" else AMBIGUOUS_PROFILE
        return RouteDecision(spec.name, params, scored.score, stage, runner_up, profile, entities, spec.guideline)
