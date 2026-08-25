"""고정 oracle 기반 일반화 평가기.

평가 세트는 실행 전에 freeze_sha256로 봉인한다. 실패 결과를 보고 라우팅 규칙을 고치면 더는
블라인드 측정이 아니므로 새 버전의 세트를 만들어야 한다.
"""
from __future__ import annotations
import argparse, hashlib, json, sys, time
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_CASES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "generalization_blind_v2.json"


def _status(result): return getattr(result.status, "value", str(result.status))
def _cells(result): return [str(cell) for row in result.answer_basis.rows for cell in row]


def score(case, route_tools, result):
    oracle, expected = case["oracle"], case["expected_tools"]
    kind = oracle["kind"]
    if kind == "route_coverage": return set(expected).issubset(route_tools), {"route_tools": route_tools}
    if kind == "no_route": return not route_tools, {"route_tools": route_tools}
    if result is None: return False, {"reason": "expected tool was not executed"}
    status, cells = _status(result), _cells(result)
    if kind == "status":
        ok = status == oracle["value"] and (not oracle.get("requires_candidates") or bool(result.candidates))
        return ok, {"status": status, "candidates": result.candidates}
    if status not in ("ok", "empty"): return False, {"status": status, "notes": result.notes}
    if kind == "contains_number":
        def same(cell):
            try: return float(cell.replace(",", "")) == float(oracle["value"])
            except ValueError: return False
        provenance = getattr(result, "provenance", None)
        return any(same(cell) for cell in cells), {"rows": result.answer_basis.rows, "query": getattr(provenance, "query", "")}
    if kind == "contains_values":
        joined = "\n".join(cells); missing = [value for value in oracle["values"] if value not in joined]
        return not missing, {"missing": missing, "rows": result.answer_basis.rows}
    if kind == "doc_recall":
        columns = result.answer_basis.columns
        got = [str(row[columns.index("doc_id")]) for row in result.answer_basis.rows] if "doc_id" in columns else cells
        missing = [doc for doc in oracle["doc_ids"] if doc not in got]
        return not missing, {"expected_docs": oracle["doc_ids"], "returned_docs": got}
    raise ValueError(f"unknown oracle: {kind}")


def run(cases_path: Path) -> dict:
    from infra.db import PostgresDb
    from infra.llm import OllamaClient
    from infra.settings import Settings
    from router.registry import build_registry, build_router
    raw = cases_path.read_bytes(); cases = json.loads(raw)
    cfg = Settings.from_env()
    registry = build_registry(PostgresDb(cfg.PG_DSN), OllamaClient(cfg.OLLAMA_URL, cfg.GENERATE_MODEL, cfg.EMBED_MODEL), cfg)
    router = build_router(registry, cfg); results = []
    for case in cases:
        began = time.perf_counter(); decisions = router.route(case["question"])
        route_tools = [str(item.tool) for item in decisions]; expected = case["expected_tools"]
        route_ok = (not expected and not route_tools) or (len(expected) == 1 and bool(route_tools) and route_tools[0] == expected[0]) or (len(expected) > 1 and set(expected).issubset(route_tools))
        result = None
        if len(expected) == 1:
            entities = router.resolver.find_all(case["question"]); spec = registry.spec(expected[0])
            result = registry.tool(expected[0]).run(**spec.build_params(case["question"], entities))
        oracle_ok, evidence = score(case, route_tools, result)
        row = {"id": case["id"], "category": case["category"], "question": case["question"],
               "route_tools": route_tools, "route_ok": route_ok, "oracle_ok": oracle_ok,
               "passed": route_ok and oracle_ok, "elapsed_ms": round((time.perf_counter()-began)*1000),
               "tool_status": _status(result) if result else None, "evidence": evidence}
        results.append(row); print(json.dumps(row, ensure_ascii=False), flush=True)
    categories = defaultdict(Counter)
    for row in results:
        categories[row["category"]].update(total=1, passed=row["passed"], route=row["route_ok"], oracle=row["oracle_ok"])
    return {"suite": cases_path.name, "freeze_sha256": hashlib.sha256(raw).hexdigest(), "total": len(results),
            "passed": sum(r["passed"] for r in results), "route_passed": sum(r["route_ok"] for r in results),
            "oracle_passed": sum(r["oracle_ok"] for r in results),
            "by_category": {key: dict(value) for key, value in categories.items()}, "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--cases", type=Path, default=DEFAULT_CASES); parser.add_argument("--out", type=Path)
    args = parser.parse_args(); report = run(args.cases)
    if args.out: args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUMMARY " + json.dumps({k: report[k] for k in ("suite","freeze_sha256","total","passed","route_passed","oracle_passed","by_category")}, ensure_ascii=False), flush=True)
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__": sys.exit(main())
