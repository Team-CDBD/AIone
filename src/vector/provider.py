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


def build_params(question: str, entities: Sequence[Resolution]) -> dict[str, Any]:
    return {"query": question}


def provide(db: Any, llm: Any, cfg: Any) -> ModuleSpec:
    return ModuleSpec(
        tool=VectorSearchTool(SearchService(VectorRepository(db), llm, cfg.TOP_K)),
        signal=SIGNAL, build_params=build_params,
        tacc_profile="document_semantic", guideline=GUIDELINE,
    )
