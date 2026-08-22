import json
from pathlib import Path

import pytest

from kg.resolver import KgEntityResolver
from nl2sql.domain.guard import guard
from nl2sql.domain.normalizer import normalize_korean_enums
from vector.provider import build_params, infer_doc_type
from kg.provider import build_params as build_kg_params
from kg.domain.planner import PlanError, plan_global
from contracts.resolver import Resolution
from router.domain.rules import score_question
from router.registry import default_signals
from tools.validate_dataset import validate
from .fakes import FakeDb


@pytest.mark.parametrize("text, expected", [
    ("Client-A가 사용 중", "Client-A"), ("Product-C1을 사용", "Product-C1"),
    ("client-a는 고객", "client-a"), ("앞의 Product-D1", "Product-D1"),
])
def test_entity_ids_before_korean_particles(text, expected):
    resolver = KgEntityResolver(FakeDb([]))
    matches = [match.group(0) for match in resolver.ENTITY_PATTERN.finditer(text)]
    assert matches == [expected]


@pytest.mark.parametrize("text", ["XClient-A가", "Client-A_more", "Product-C1-bad"])
def test_entity_ids_reject_invalid_boundaries(text):
    assert not KgEntityResolver(FakeDb([])).ENTITY_PATTERN.search(text)


def test_guard_extracts_json_and_single_explanatory_fence():
    assert guard('{"sql":"SELECT id FROM clients"}').ok
    assert guard("아래 쿼리입니다.\n```sql\nSELECT id FROM clients\n```").ok
    assert not guard("```sql\nSELECT id FROM clients\n```\n```sql\nSELECT id FROM products\n```").ok


def test_quarter_and_document_intent_grounding():
    assert "2025-Q3" in normalize_korean_enums("2025년 3분기 매출")
    assert infer_doc_type("최근 서버 장애 사례와 원인") == "incident_report"
    assert infer_doc_type("고객 미팅에서 논의") == "meeting_note"
    assert build_params("API 설치 가이드", [])["doc_type"] == "technical_doc"


def test_product_project_question_builds_two_hop_plan():
    entity = Resolution("product_5", "Product-D1", "product", 1.0, "exact")
    params = build_kg_params("Product-D1 제품과 관련된 프로젝트는?", [entity])
    assert params["relations"] == ["USES", "HAS_PROJECT"]
    assert params["target_types"] == ["project"]
    assert params["max_hops"] == 2


@pytest.mark.parametrize("question, relation, target, aggregate, neighbor_filter", [
    ("기술 지원 이슈가 가장 많은 제품은?", "REPORTED_ISSUE", "product", "count", {}),
    ("가장 많은 고객을 담당하는 직원은?", "MANAGES_ACCOUNT", "employee", "count", {}),
    ("진행 중인 프로젝트를 이끄는 직원 목록", "LEADS", "employee", None, {"status": "in_progress"}),
])
def test_global_questions_build_scoped_aggregate_plan(question, relation, target, aggregate, neighbor_filter):
    """공식 #26/#28/#30 — 시작 개체 없는 전역 집계 경로."""
    params = build_kg_params(question, [])
    assert params["scope"] == "global"
    assert params["relation"] == relation
    assert params["target_type"] == target
    assert params["aggregate"] == aggregate
    assert params["neighbor_filter"] == neighbor_filter


def test_global_plan_rejects_target_that_is_not_an_endpoint():
    with pytest.raises(PlanError): plan_global("LEADS", "client")
    with pytest.raises(PlanError): plan_global("MANAGES_ACCOUNT", "employee", aggregate="sum")


def test_global_plan_groups_on_the_ontology_side():
    assert plan_global("MANAGES_ACCOUNT", "employee").side == "source"
    assert plan_global("REPORTED_ISSUE", "product").side == "target"


def test_entity_question_still_uses_traversal_scope():
    entity = Resolution("client_1", "Client-A", "client", 1.0, "exact")
    assert "scope" not in build_kg_params("Client-A가 사용 중인 제품은?", [entity])


def test_corrected_dataset_contract_is_valid():
    result = validate(Path("data/companyx-dataset-v1.0.zip"), Path("tests/fixtures/companyx_questions_v1.1.json"))
    assert result["ok"], result["errors"]
    assert result["counts"] == {"questions": 30, "nodes": 133, "edges": 354, "chunks": 202}


def test_official_question_contract_routes_top1_30_of_30():
    questions = json.loads(Path("tests/fixtures/companyx_questions_v1.1.json").read_text(encoding="utf-8"))
    for item in questions:
        has_entity = bool(KgEntityResolver.ENTITY_PATTERN.search(item["question"]))
        scored = score_question(item["question"], has_entity, signals=default_signals())
        assert scored[0].tool == item["expected_tool"], item["id"]
