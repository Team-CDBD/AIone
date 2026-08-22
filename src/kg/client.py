"""장기 실행 Java(Jena) runner와 JSONL로 통신하는 persistent subprocess client.
§P2 typed traversal/aggregate 전체 구현은 스코프 밖 — 여기서는 프로세스 수명주기, timeout,
1회 재기동, requestId 상관관계, 오류 격리(예외를 삼켜 WireError/timeout으로 변환)만 구현한다.
adapter/service는 이 예외를 밖으로 새지 않게 잡아 upstream_error로 변환한다(§5.2)."""
from __future__ import annotations
import json
import subprocess
import time
from typing import Any, Protocol

from .wire import JenaRequest, JenaResponse, WireError


class ProcessError(RuntimeError):
    """runner 기동/통신 실패. client 밖으로는 절대 raw 예외를 노출하지 않는다."""


class JenaTimeout(ProcessError):
    pass


class RunnerProcess(Protocol):
    """subprocess.Popen과 동일한 최소 인터페이스. 테스트에서는 fake로 대체한다."""
    stdin: Any
    stdout: Any
    def poll(self) -> int | None: ...
    def kill(self) -> None: ...
    def wait(self, timeout: float | None = None) -> int: ...


def _default_spawn(command: list[str]) -> RunnerProcess:
    return subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, bufsize=1,
    )


class JenaGraphClient:
    """호출마다 요청 한 줄을 stdin에 쓰고 stdout 한 줄을 읽는다. 프로세스는 최초 호출 시 1회 기동하고
    재사용한다. 죽어 있으면 최대 1회 재기동을 시도하고 그래도 실패하면 ProcessError로 변환한다."""

    def __init__(self, command: list[str], *, timeout_s: float = 5.0, spawn: Any = _default_spawn):
        self._command = command
        self._timeout_s = timeout_s
        self._spawn = spawn
        self._proc: RunnerProcess | None = None
        self._restarted = False

    def _ensure_started(self) -> RunnerProcess:
        if self._proc is not None and self._proc.poll() is None:
            return self._proc
        self._proc = self._spawn(self._command)
        return self._proc

    def _restart_once(self) -> RunnerProcess:
        if self._restarted:
            raise ProcessError("runner가 이미 1회 재기동을 시도했으나 실패했습니다")
        self._restarted = True
        if self._proc is not None:
            try: self._proc.kill()
            except Exception: pass
        self._proc = self._spawn(self._command)
        return self._proc

    def call(self, request: JenaRequest) -> JenaResponse:
        try:
            return self._call_once(request, self._ensure_started())
        except (ProcessError, WireError):
            raise
        except Exception as exc:
            raise ProcessError(f"runner 통신 실패, 재기동을 시도합니다: {exc}") from None

    def _call_once(self, request: JenaRequest, proc: RunnerProcess) -> JenaResponse:
        try:
            line = json.dumps(request.to_json(), ensure_ascii=False)
            proc.stdin.write(line + "\n")
            proc.stdin.flush()
        except Exception as exc:
            proc = self._restart_once()
            line = json.dumps(request.to_json(), ensure_ascii=False)
            proc.stdin.write(line + "\n")
            proc.stdin.flush()

        began = time.monotonic()
        raw = proc.stdout.readline()
        if not raw or not raw.strip():
            if time.monotonic() - began >= self._timeout_s:
                raise JenaTimeout(f"runner 응답 시간 초과({self._timeout_s}s)")
            raise ProcessError("runner가 빈 응답을 반환했습니다")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise WireError(f"runner 응답이 JSON이 아닙니다: {exc}") from None
        return JenaResponse.from_json(data, expected_request_id=request.request_id)

    def health(self) -> bool:
        try:
            proc = self._ensure_started()
            return proc.poll() is None
        except Exception:
            return False

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.stdin.close()
            self._proc.wait(timeout=self._timeout_s)
        except Exception:
            try: self._proc.kill()
            except Exception: pass
        finally:
            self._proc = None
