from __future__ import annotations
from typing import Sequence

from contracts.resolver import EntityResolver, Resolution

NOT_FOUND = Resolution(None, None, None, 0.0, "not_found")


class CompositeResolver:
    """모듈들이 제공한 해소기를 합친다. 개별 해소기의 실패는 라우팅을 중단시키지 않는다.

    원격(예: 다른 언어로 분리된) 모듈의 해소기가 죽어도 entities=[]로 라우팅이 계속되고,
    해당 모듈은 UPSTREAM_ERROR로 랭킹 뒤로 밀린다.
    """

    def __init__(self, resolvers: Sequence[EntityResolver] = ()):
        self.resolvers = list(resolvers)

    def resolve(self, text: str) -> Resolution:
        best = NOT_FOUND
        for resolver in self.resolvers:
            try: found = resolver.resolve(text)
            except Exception: continue
            if found.node_id is not None and found.confidence > best.confidence: best = found
            elif best.node_id is None and found.candidates: best = found
        return best

    def find_all(self, question: str) -> list[Resolution]:
        seen: dict[str, Resolution] = {}
        for resolver in self.resolvers:
            try: found = resolver.find_all(question)
            except Exception: continue
            for item in found:
                key = item.node_id or item.name or ""
                if item.node_id is not None and (key not in seen or item.confidence > seen[key].confidence):
                    seen[key] = item
        return list(seen.values())
