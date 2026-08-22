import time
from contracts.tool import AnswerBasis, Provenance, ToolName, ToolResult, ToolStatus, empty_result
from .service import GraphService
class KnowledgeGraphTool:
    name=ToolName.KNOWLEDGE_GRAPH
    def __init__(self,service:GraphService): self.service=service
    def input_schema(self)->dict:
        relations={"enum":["BELONGS_TO","HEAD_IS","USES","MANAGES_ACCOUNT","HAS_PROJECT","LEADS","REPORTED_ISSUE"]}
        node_types={"enum":["client","product","employee","project","department"]}
        return {"type":"object","properties":{"scope":{"enum":["entity","global"]},"start_entity":{"type":"string","minLength":1},"relations":{"type":"array","items":relations},"target_types":{"type":"array","items":node_types},"max_hops":{"type":"integer","minimum":1,"maximum":2},"aggregate":{"type":["string","null"]},"relation":relations,"target_type":node_types,"neighbor_filter":{"type":"object","additionalProperties":{"type":"string"}},"limit":{"type":"integer","minimum":1,"maximum":100}},"additionalProperties":False}
    def health(self)->bool:return True
    def run(self,**params)->ToolResult:
        if params.get("scope")=="global": return self._global(params)
        start=params.get("start_entity")
        if not isinstance(start,str) or not start.strip(): return empty_result(self.name,ToolStatus.ENTITY_NOT_FOUND,unit="그래프 경로",note="시작 개체가 비어 있습니다",candidates=["Client-A","Product-A1","영업팀"])
        began=time.perf_counter()
        try:
            out=self.service.traverse(start,params.get("relations") or [],params.get("target_types") or [],params.get("max_hops") or 2,params.get("aggregate"))
            columns=list(out.rows[0]) if out.rows else []
            rows=[[row.get(c) for c in columns] for row in out.rows]
            return ToolResult(self.name,out.status,AnswerBasis(columns,rows,len(rows),out.unit),Provenance(out.query,[str(row[0]) for row in rows if row],int((time.perf_counter()-began)*1000)),notes=[out.reason] if out.reason else [],candidates=out.candidates)
        except Exception as exc:return empty_result(self.name,ToolStatus.UPSTREAM_ERROR,unit="그래프 경로",note=str(exc))
    def _global(self,params:dict)->ToolResult:
        began=time.perf_counter()
        try:
            out=self.service.aggregate(params.get("relation") or "",params.get("target_type") or "",params.get("aggregate"),params.get("neighbor_filter"),int(params.get("limit") or 10))
            columns=list(out.rows[0]) if out.rows else []
            rows=[[row.get(c) for c in columns] for row in out.rows]
            return ToolResult(self.name,out.status,AnswerBasis(columns,rows,len(rows),out.unit),Provenance(out.query,[str(row[0]) for row in rows if row],int((time.perf_counter()-began)*1000)),notes=[out.reason] if out.reason else [])
        except Exception as exc:return empty_result(self.name,ToolStatus.UPSTREAM_ERROR,unit="그래프 경로",note=str(exc))
