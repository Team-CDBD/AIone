from __future__ import annotations
from typing import Any, Sequence

from contracts.module import ModuleSpec, SignalSpec
from contracts.resolver import Resolution
from contracts.tool import ToolName
from .adapter import Nl2SqlTool
from .repository import SqlRepository
from .service import SqlService

SIGNAL = SignalSpec(
    tool=ToolName.NL2SQL,
    weight=3.0,
    keywords=("총","합계","평균","개수","건수","집계","몇 개","얼마","상위","순서로","가장 높은","가장 많은","진행 중인","매출","계약","연봉","티켓"),
    pattern=r"20\d{2}년|\d분기|20\d{2}-Q\d|(?:직원.*목록.*연봉|목록.*직원.*연봉)",
    pattern_bonus=3.0,
    pattern_label="기간",
)
GUIDELINE = "조회 결과와 단위를 함께 답하세요."
MAX_ROWS = 100


def build_params(question: str, entities: Sequence[Resolution]) -> dict[str, Any]:
    return {"question": question, "max_rows": MAX_ROWS}


def provide(db: Any, llm: Any, cfg: Any) -> ModuleSpec:
    return ModuleSpec(
        tool=Nl2SqlTool(SqlService(SqlRepository(db), llm)),
        signal=SIGNAL, build_params=build_params,
        tacc_profile="structured_aggregate", guideline=GUIDELINE,
    )
