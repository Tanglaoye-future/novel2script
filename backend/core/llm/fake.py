"""FakeProvider：CI / 离线测试用，返回预定的响应。

允许下游模块在没有 API key 的环境下跑单测，并验证 Pipeline 对响应的解析逻辑。
"""
from __future__ import annotations

from collections.abc import Iterable

from .base import LLMProvider, LLMResponse, LLMUsage


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, responses: Iterable[str] | None = None) -> None:
        """responses 按顺序返回；用完则循环最后一个。"""
        self._responses = list(responses) if responses else ["{}"]
        self._calls = 0
        self.history: list[tuple[str, str]] = []  # (system, user)

    def _next(self) -> str:
        idx = min(self._calls, len(self._responses) - 1)
        self._calls += 1
        return self._responses[idx]

    def generate(self, system: str, user: str, *, temperature: float = 0.7, max_tokens: int | None = None) -> LLMResponse:
        self.history.append((system, user))
        text = self._next()
        return LLMResponse(text=text, usage=LLMUsage(0, 0, 0), model="fake")

    def generate_json(self, system: str, user: str, *, temperature: float = 0.3, max_tokens: int | None = None) -> LLMResponse:
        return self.generate(system, user, temperature=temperature, max_tokens=max_tokens)
