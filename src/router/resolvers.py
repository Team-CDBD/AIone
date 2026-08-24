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
        unresolved: list[Resolution] = []
        for resolver in self.resolvers:
            try: found = resolver.find_all(question)
            except Exception: continue
            for item in found:
                if item.node_id is not None:
                    key = item.node_id
                    if key not in seen or item.confidence > seen[key].confidence: seen[key] = item
                # 해소에 실패했어도 '개체를 지목했다'는 사실 자체가 신호다. 이걸 버리면
                # 존재하지 않는 식별자를 물었을 때 개체 기반 모듈이 보너스를 잃고 밀려난다.
                # candidates가 있다는 건 실제로 조회해 보고 실패했다는 뜻이다(해소기 장애와 구분된다).
                elif item.candidates: unresolved.append(item)
        return list(seen.values()) + unresolved
