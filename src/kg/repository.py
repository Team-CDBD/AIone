from typing import Any
from contracts.infra import Db

class KgRepository:
    def __init__(self, db: Db): self.db = db
    def exact_by_name(self, text: str) -> dict[str, Any] | None:
        rows = self.db.fetch_dicts("SELECT node_id, name, node_type FROM kg_nodes WHERE lower(name)=lower(%s) LIMIT 1", (text,)); return rows[0] if rows else None
    def exact_by_compact_name(self, text: str) -> dict[str, Any] | None:
        """공백을 무시한 정확 일치 — '기술 지원팀'과 '기술지원팀'은 같은 노드다."""
        rows = self.db.fetch_dicts(
            "SELECT node_id, name, node_type FROM kg_nodes WHERE replace(lower(name),' ','')=replace(lower(%s),' ','') LIMIT 1", (text,))
        return rows[0] if rows else None
    def by_id(self, node_id: str) -> dict[str, Any] | None:
        rows = self.db.fetch_dicts("SELECT node_id, name, node_type FROM kg_nodes WHERE node_id=%s", (node_id,)); return rows[0] if rows else None
    def trigram_top(self, text: str, k: int = 3) -> list[dict[str, Any]]:
        return self.db.fetch_dicts("SELECT node_id,name,node_type,similarity(name,%s) AS sim FROM kg_nodes ORDER BY sim DESC LIMIT %s", (text,k))
    def names_in_text(self, text: str, k: int = 5) -> list[dict[str, Any]]:
        return self.db.fetch_dicts(
            "SELECT node_id,name,node_type FROM kg_nodes WHERE position(lower(name) in lower(%s)) > 0 ORDER BY length(name) DESC LIMIT %s",
            (text,k),
        )
    def rank_global(self, relation: str, side: str, neighbor_filter: dict[str, str], limit: int) -> list[dict[str, Any]]:
        """관계 전체를 그룹핑 노드 기준으로 집계한다. side는 planner가 온톨로지에서 정한 값만 온다."""
        group, other = ("source_id", "target_id") if side == "source" else ("target_id", "source_id")
        clauses, params = "", [relation]
        for key, value in neighbor_filter.items():
            clauses += " AND m.properties->>%s = %s"; params += [key, value]
        return self.db.fetch_dicts(
            f"""SELECT n.node_id,n.name,n.node_type,count(DISTINCT e.{other}) AS connected
 FROM kg_edges e JOIN kg_nodes n ON n.node_id=e.{group} JOIN kg_nodes m ON m.node_id=e.{other}
 WHERE e.relation_type=%s{clauses}
 GROUP BY n.node_id,n.name,n.node_type ORDER BY connected DESC,n.name LIMIT %s""",
            tuple(params + [limit]),
        )
    def traverse(self, start_id: str, relations: list[str], target_types: list[str], max_hops: int) -> list[dict[str, Any]]:
        return self.db.fetch_dicts("""WITH RECURSIVE walk(node_id,path,depth) AS (
 SELECT %s::text, ARRAY[%s::text], 0 UNION ALL
 SELECT CASE WHEN e.source_id=w.node_id THEN e.target_id ELSE e.source_id END,
 w.path || CASE WHEN e.source_id=w.node_id THEN e.target_id ELSE e.source_id END,w.depth+1
 FROM walk w JOIN kg_edges e ON (e.source_id=w.node_id OR e.target_id=w.node_id)
 WHERE w.depth < %s AND e.relation_type=ANY(%s) AND NOT (CASE WHEN e.source_id=w.node_id THEN e.target_id ELSE e.source_id END)=ANY(w.path))
 SELECT n.node_id,n.name,n.node_type,w.path,w.depth FROM walk w JOIN kg_nodes n USING(node_id)
 WHERE w.depth>0 AND (cardinality(%s::text[]) = 0 OR n.node_type=ANY(%s)) ORDER BY w.depth,n.name""", (start_id,start_id,max_hops,relations,target_types,target_types))
