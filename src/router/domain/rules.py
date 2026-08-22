from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Sequence

from contracts.module import SignalSpec


@dataclass(frozen=True)
class ScoredRoute:
    tool: str; score: float; matched: tuple[str, ...]


def score_question(question: str, has_entity: bool = False, *, signals: Sequence[SignalSpec]) -> list[ScoredRoute]:
    """등록된 모듈의 SignalSpec만 보고 점수를 낸다. 특정 모듈을 이름으로 알지 않는다."""
    if not signals: return []
    lowered = question.lower()
    # 한국어는 띄어쓰기가 자유롭다("진행 중" / "진행중"). 공백을 지운 형태로도 맞춰서
    # 같은 뜻의 표기 변형이 라우팅을 바꾸지 않게 한다.
    compact = re.sub(r"\s+", "", lowered)
    raw: dict[str, tuple[float, list[str]]] = {}
    for signal in signals:
        hits = [term for term in signal.keywords
                if term.lower() in lowered or re.sub(r"\s+", "", term.lower()) in compact]
        value = signal.weight * len(hits)
        if signal.pattern and re.search(signal.pattern, question, re.I):
            value += signal.pattern_bonus; hits.append(signal.pattern_label)
        if signal.entity_when and has_entity is (signal.entity_when == "present"):
            value += signal.entity_bonus; hits.append("entity" if signal.entity_when == "present" else "no_entity")
        raw[signal.tool] = (value, hits)
    total = sum(value for value, _ in raw.values()) or 1.0
    return sorted((ScoredRoute(tool, value / total, tuple(hits)) for tool, (value, hits) in raw.items()),
                  key=lambda item: (-item.score, item.tool))
