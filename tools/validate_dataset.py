#!/usr/bin/env python3
"""Validate the immutable CompanyX archive and its corrected question contract."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE = ROOT / "data/companyx-dataset-v1.0.zip"
DEFAULT_QUESTIONS = ROOT / "tests/fixtures/companyx_questions_v1.1.json"
ENTITY_RE = re.compile(r"(?<![A-Za-z0-9_-])(?:Client|Product)-[A-Z0-9]+(?=$|[^A-Za-z0-9_-])", re.I)
TOOLS = {"nl2sql", "vector_search", "knowledge_graph"}
EXPECTED = {"questions": 30, "nodes": 133, "edges": 354, "chunks": 202}


def validate(archive: Path, questions_path: Path) -> dict[str, object]:
    errors: list[str] = []
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive) as source:
        bad_crc = source.testzip()
        if bad_crc: errors.append(f"ZIP CRC 오류: {bad_crc}")
        nodes = json.loads(source.read("graph/nodes.json"))
        edges = json.loads(source.read("graph/edges.json"))
        index = json.loads(source.read("documents/index.json"))
        names = {str(node.get("name", "")).lower() for node in nodes}
        chunks = sum(source.read(f"documents/{item['filename']}").decode().count("\n## ") + 1 for item in index)
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    ids = [item.get("id") for item in questions]
    if len(questions) != EXPECTED["questions"]: errors.append(f"질문 수: {len(questions)}")
    if len(ids) != len(set(ids)) or any(not item for item in ids): errors.append("질문 id가 비었거나 중복되었습니다")
    for item in questions:
        if item.get("expected_tool") not in TOOLS: errors.append(f"{item.get('id')}: expected_tool 오류")
        if not isinstance(item.get("expected"), dict) or not item["expected"]: errors.append(f"{item.get('id')}: expected 누락")
        if item.get("expected_tool") == "knowledge_graph":
            for entity in ENTITY_RE.findall(str(item.get("question", ""))):
                if entity.lower() not in names: errors.append(f"{item.get('id')}: 그래프 엔티티 없음: {entity}")
    actual = {"questions": len(questions), "nodes": len(nodes), "edges": len(edges), "chunks": chunks}
    for key, expected in EXPECTED.items():
        if actual[key] != expected: errors.append(f"{key}: 기대 {expected}, 실제 {actual[key]}")
    return {"ok": not errors, "archive": str(archive), "sha256": digest, "counts": actual, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", nargs="?", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    args = parser.parse_args()
    result = validate(args.archive, args.questions)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__": sys.exit(main())
