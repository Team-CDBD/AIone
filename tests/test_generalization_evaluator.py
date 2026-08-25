import json
from pathlib import Path

from tools.evaluate_generalization import score


class Status:
    value = "ok"


class Basis:
    columns = ["doc_id", "value"]
    rows = [["DOC-012", 8]]


class Result:
    status = Status()
    answer_basis = Basis()
    candidates = []
    notes = []


def test_블라인드_세트_ID와_카테고리는_중복되지_않는다():
    path = Path(__file__).parent / "fixtures" / "generalization_blind_v2.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    assert len(cases) >= 18 and len({case["id"] for case in cases}) == len(cases)
    assert {case["category"] for case in cases} == {"paraphrase", "colloquial", "multi_intent", "unknown_entity", "out_of_scope"}


def test_값과_문서_oracle을_실제_행으로_채점한다():
    ok, _ = score({"oracle":{"kind":"contains_number","value":8},"expected_tools":["nl2sql"]}, ["nl2sql"], Result())
    assert ok
    ok, _ = score({"oracle":{"kind":"doc_recall","doc_ids":["DOC-012"]},"expected_tools":["vector_search"]}, ["vector_search"], Result())
    assert ok


def test_다중의도는_기대_도구_전체를_요구한다():
    case = {"oracle":{"kind":"route_coverage"},"expected_tools":["knowledge_graph","nl2sql"]}
    assert score(case, ["knowledge_graph","nl2sql"], None)[0]
    assert not score(case, ["knowledge_graph"], None)[0]
