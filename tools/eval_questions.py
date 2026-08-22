"""공식 30문항을 단일 프로세스에서 연속 실행하고 결과를 JSON으로 남긴다.

이미지 안에서 그대로 돌아가는 것이 목적이다(원격 배포본 검증):

    docker compose run --rm mcp python tools/eval_questions.py --out /tmp/eval.json

채점 범위는 라우팅 Top-1과 도구 status/row_count까지다. 값(정답) 채점은 oracle이
확정되지 않아 수행하지 않는다 — 이 스크립트는 값 게이트를 통과했다고 주장하지 않는다.
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

DEFAULT_QUESTIONS = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "companyx_questions_v1.1.json"


def run(questions_path: Path) -> dict:
    from infra.settings import Settings
    from infra.db import PostgresDb
    from infra.llm import OllamaClient
    from router.registry import build_registry, build_router

    cfg = Settings.from_env()
    registry = build_registry(PostgresDb(cfg.PG_DSN),
                              OllamaClient(cfg.OLLAMA_URL, cfg.GENERATE_MODEL, cfg.EMBED_MODEL), cfg)
    router = build_router(registry, cfg)
    questions = json.loads(questions_path.read_text(encoding="utf-8"))

    results, routed = [], 0
    for item in questions:
        decisions = router.route(item["question"])
        top = decisions[0] if decisions else None
        route_ok = bool(top) and top.tool == item["expected_tool"]
        routed += route_ok
        entities = router.resolver.find_all(item["question"])
        params = registry.spec(item["expected_tool"]).build_params(item["question"], entities)
        began = time.perf_counter()
        try:
            result = registry.tool(item["expected_tool"]).run(**params)
            status = getattr(result.status, "value", str(result.status))
            basis = result.answer_basis
            columns, row_count, rows = basis.columns, basis.row_count, basis.rows[:3]
        except Exception as exc:  # 도구가 예외를 흘려도 평가 자체는 계속한다
            status, columns, row_count, rows = f"EXC:{type(exc).__name__}", [], 0, [str(exc)[:200]]
        elapsed = round((time.perf_counter() - began) * 1000)
        results.append({"id": item["id"], "question": item["question"],
                        "expected_tool": item["expected_tool"], "routed_tool": top.tool if top else None,
                        "stage": top.stage if top else None, "route_ok": route_ok, "params": params,
                        "status": status, "columns": columns, "row_count": row_count,
                        "sample_rows": [[str(cell)[:80] for cell in row] for row in rows],
                        "elapsed_ms": elapsed})
        print(f"{item['id']} {'R:OK' if route_ok else 'R:MISS'} {status} rows={row_count} {elapsed}ms", flush=True)

    latencies = sorted(entry["elapsed_ms"] for entry in results)
    statuses: dict[str, int] = {}
    for entry in results: statuses[entry["status"]] = statuses.get(entry["status"], 0) + 1
    return {"total": len(results), "routing_top1": routed,
            "status_counts": statuses,
            "p50_ms": latencies[len(latencies) // 2], "p95_ms": latencies[int(len(latencies) * .95) - 1],
            "timeouts": statuses.get("timeout", 0), "results": results,
            "scored": "routing+status only (값 oracle 미확정)"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = run(args.questions)
    if args.out: args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({key: report[key] for key in
                      ("total", "routing_top1", "status_counts", "p50_ms", "p95_ms")}, ensure_ascii=False))
    return 0 if report["routing_top1"] == report["total"] else 1


if __name__ == "__main__": sys.exit(main())
