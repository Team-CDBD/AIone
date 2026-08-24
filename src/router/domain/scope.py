"""범위 밖 질문 판정. 순수 함수 — I/O 없음.

근거 점수는 상대값이라 '알려줘'나 '회의' 한 단어만 스쳐도 어떤 모듈이든 1위가 된다.
날씨나 메일 발송처럼 이 시스템이 애초에 답할 수 없는 질문은 점수 이전에 걸러야 한다.
"""
from __future__ import annotations
import re
from typing import Sequence

# 이 데이터셋에 없는 실시간·외부 세계 주제.
EXTERNAL = re.compile(r"날씨|기온|강수|미세먼지|환율|주가|증시|뉴스|교통\s*상황|경기\s*결과")
# 조회가 아니라 실행을 요구하는 문장. 이 시스템은 읽기 전용이다.
ACTION = re.compile(
    r"(?:메일|이메일|메시지|문자|알림|초대장?|공지)\s*(?:를|을)?\s*(?:보내|발송|전송)"
    r"|(?:예약|등록|생성|추가|삭제|수정|변경|취소)\s*(?:해|하고|해줘|해\s*주)"
    r"|(?:보내|발송|전송)\s*(?:해줘|해\s*주|줘)")


EXTERNAL_REASON = "이 시스템은 사내 문서·관계형 데이터·지식 그래프만 다룹니다. 외부 실시간 정보는 답할 수 없습니다."
ACTION_REASON = "이 시스템은 조회 전용입니다. 메일 발송이나 데이터 변경 같은 실행 요청은 처리하지 않습니다."


def out_of_scope(question: str, claimed: Sequence[str] = ()) -> tuple[str, str] | None:
    """범위 밖이면 (사유, 걸린 표현)을, 아니면 None.

    `claimed`는 등록된 모듈들이 신고한 키워드다. 어떤 모듈이 그 주제를 자기 것이라고
    신고했다면 범위 밖이 아니다 — 라우터가 특정 주제를 아는 것이 아니라, 등록된 모듈이
    무엇을 다루는지에 따라 판정이 달라져야 한다.
    """
    compact = re.sub(r"\s+", " ", question)
    for pattern, reason in ((EXTERNAL, EXTERNAL_REASON), (ACTION, ACTION_REASON)):
        hit = pattern.search(compact)
        if not hit: continue
        trigger = hit.group(0)
        if any(term and (term in trigger or trigger in term) for term in claimed): continue
        return reason, trigger
    return None
