from dataclasses import dataclass, field
from typing import Any
from contracts.resolver import EntityResolver
from contracts.tool import ToolStatus
from .domain.ontology import NodeType, Relation
from .domain.planner import PlanError, aggregate_unit, global_unit, plan, plan_global
from .repository import KgRepository

@dataclass(frozen=True)
class GraphOutcome:
    status: ToolStatus; rows: list[dict[str,Any]]=field(default_factory=list); unit: str="그래프 경로"; query: str=""; candidates: list[str]=field(default_factory=list); reason: str|None=None
class GraphService:
    def __init__(self, repo: KgRepository, resolver: EntityResolver): self.repo,self.resolver=repo,resolver
    def aggregate(self,relation:str,target_type:str,aggregate:str|None=None,neighbor_filter:dict[str,str]|None=None,limit:int=10)->GraphOutcome:
        """시작 개체가 없는 전역 집계 — '가장 많은 …', '진행 중인 …를 이끄는 …' 류를 처리한다."""
        try: planned=plan_global(relation,target_type,aggregate,neighbor_filter,limit)
        except (PlanError,ValueError) as exc: return GraphOutcome(ToolStatus.GUARD_REJECTED,reason=str(exc))
        rows=self.repo.rank_global(planned.relation.value,planned.side,planned.neighbor_filter,planned.limit)
        query=f"scope=global; relation={planned.relation.value}; group={planned.target_type.value}; filter={planned.neighbor_filter or '{}'}; limit={planned.limit}"
        return GraphOutcome(ToolStatus.OK if rows else ToolStatus.EMPTY,rows,global_unit(planned.relation,planned.target_type),query)
    def traverse(self,start_entity:str,relations:list[str],target_types:list[str],max_hops:int,aggregate:str|None=None)->GraphOutcome:
        resolved=self.resolver.resolve(start_entity)
        if resolved.node_id is None: return GraphOutcome(ToolStatus.ENTITY_NOT_FOUND,candidates=resolved.candidates,reason="개체를 찾지 못했습니다")
        try: traversal=plan(resolved.node_id,NodeType(resolved.node_type or "client"),relations,target_types,max_hops,aggregate)
        except (PlanError,ValueError) as exc: return GraphOutcome(ToolStatus.GUARD_REJECTED,reason=str(exc))
        rows=self.repo.traverse(traversal.start_id,[r.value for r in traversal.relations],[t.value for t in traversal.target_types],traversal.max_hops)
        unit=aggregate_unit(traversal.relations[-1] if traversal.relations else None,aggregate)
        # 근사 일치로 다른 개체를 조회했다면 반드시 밝힌다 — 묻지 않은 개체의 답을
        # 확신 있게 돌려주는 것이 조용한 오답의 경로다.
        note=(f"'{start_entity}'와 정확히 일치하는 개체가 없어 '{resolved.name}'(유사도 {resolved.confidence:.2f})로 해석했습니다."
              if resolved.method=="fuzzy" else None)
        return GraphOutcome(ToolStatus.OK if rows else ToolStatus.EMPTY,rows,unit,
                            f"start={resolved.node_id}({resolved.method}); relations={relations}; max_hops={max_hops}",
                            candidates=[resolved.name] if resolved.method=="fuzzy" and resolved.name else [],reason=note)
