from __future__ import annotations
from typing import Any, Sequence

from contracts.module import ModuleSpec, SignalSpec
from contracts.resolver import Resolution
from contracts.tool import ToolName
from .adapter import VectorSearchTool
from .repository import VectorRepository
from .service import SearchService

SIGNAL = SignalSpec(
    tool=ToolName.VECTOR_SEARCH,
    weight=3.0,
    keywords=("방법","알려줘","궁금해","어떻게","내용","보여줘","사례","원인","장애","설치","가이드","회의","제안서","매뉴얼","정책","취약점"),
    entity_when="absent",
    entity_bonus=1.0,
)
GUIDELINE = "검색 본문에만 근거하고 출처를 표시하세요."

DOC_TYPE_TERMS = {
    "incident_report": ("장애", "원인", "취약점", "ssl"),
    "technical_doc": ("설치", "api", "튜닝", "백업", "운영", "방법", "가이드", "정책"),
    "meeting_note": ("미팅", "회의", "논의"),
    "proposal": ("제안", "마이그레이션"),
}

def infer_doc_type(question: str) -> str | None:
    """Return a hard filter only when one intent has an unambiguous signal."""
    lowered = question.lower()
    scores = {kind: sum(term in lowered for term in terms) for kind, terms in DOC_TYPE_TERMS.items()}
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return ranked[0][0] if ranked[0][1] > 0 and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]) else None


def build_params(question: str, entities: Sequence[Resolution]) -> dict[str, Any]:
    params: dict[str, Any] = {"query": question}
    doc_type = infer_doc_type(question)
    if doc_type: params["doc_type"] = doc_type
    return params


def provide(db: Any, llm: Any, cfg: Any) -> ModuleSpec:
    return ModuleSpec(
        tool=VectorSearchTool(SearchService(VectorRepository(db), llm, cfg.TOP_K)),
        signal=SIGNAL, build_params=build_params,
        tacc_profile="document_semantic", guideline=GUIDELINE,
    )
