from __future__ import annotations
from typing import Any, Sequence

from contracts.module import ModuleSpec, SignalSpec
from contracts.resolver import Resolution
from contracts.tool import ToolName
from .adapter import KnowledgeGraphTool
from .repository import KgRepository
from .resolver import KgEntityResolver
from .service import GraphService

SIGNAL = SignalSpec(
    tool=ToolName.KNOWLEDGE_GRAPH,
    weight=3.5,
    keywords=("담당","소속","사용 중인","이끄는","팀장","누구야","관련된","기술 지원 이슈"),
    entity_when="present",
    entity_bonus=2.0,
)
GUIDELINE = "그래프 경로의 방향과 단위를 명시하세요."
# 질문 키워드 → 온톨로지 관계. 라우터가 아니라 kg 모듈이 소유한다.
RELATION_BY_KEYWORD = {"소속":"BELONGS_TO","팀장":"HEAD_IS","사용":"USES","담당":"MANAGES_ACCOUNT","프로젝트":"HAS_PROJECT","이끄":"LEADS","이슈":"REPORTED_ISSUE"}
DEFAULT_RELATIONS = ["USES", "HAS_PROJECT"]
MAX_HOPS = 2


def build_params(question: str, entities: Sequence[Resolution]) -> dict[str, Any]:
    start = next((e.name for e in entities if e.name), question)
    relations = [rel for keyword, rel in RELATION_BY_KEYWORD.items() if keyword in question] or list(DEFAULT_RELATIONS)
    if "Product-" in question and "프로젝트" in question: relations = ["USES", "HAS_PROJECT"]
    if "프로젝트" in question: targets = ["project"]
    elif "고객사" in question or "고객" in question: targets = ["client"]
    elif "제품" in question: targets = ["product"]
    elif "직원" in question or "팀장" in question or "엔지니어" in question: targets = ["employee"]
    else: targets = []
    hops = 2 if len(relations) > 1 else 1
    return {"start_entity": start, "relations": relations, "target_types": targets, "max_hops": hops}


def provide(db: Any, llm: Any, cfg: Any) -> ModuleSpec:
    repo = KgRepository(db)
    resolver = KgEntityResolver(repo)
    engine = getattr(cfg, "KG_ENGINE", "python")
    # engine=="jena"/"shadow"는 이번 라운드 스코프 밖(§P3 실연결 미구현) — client.py는 배선만 되어 있고
    # 항상 Python traversal로 조립한다. 실제 분기는 JenaGraphClient가 typed traversal을 반환하게 되는
    # 다음 라운드에서 GraphService에 연결한다.
    if engine in ("jena", "shadow"):
        pass
    return ModuleSpec(
        tool=KnowledgeGraphTool(GraphService(repo, resolver)),
        signal=SIGNAL, build_params=build_params,
        tacc_profile="relation_traversal", guideline=GUIDELINE,
        resolver=resolver,
    )
