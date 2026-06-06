"""LLM Provider 抽象接口。

设计目标：
- 上层 Pipeline 只依赖此接口，可以无痛切 DeepSeek/Kimi/通义/Qwen 等
- 区分 `generate` 与 `generate_json`：JSON 模式利用各家 SDK 的 structured output 能力
- Provider 自带轻量重试，调用方不需要包 try/except 循环
"""
from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class LLMUsage:
    """单次调用的 token 用量，便于成本统计。"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    text: str
    usage: LLMUsage
    model: str


class LLMProvider(abc.ABC):
    """所有 LLM Provider 必须实现的接口。"""

    name: str = "base"

    @abc.abstractmethod
    def generate(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """生成自由文本。"""

    @abc.abstractmethod
    def generate_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """生成 JSON。返回的 text 字段保证是合法 JSON 字符串（已剥离 ```json 包裹）。"""


class LLMError(RuntimeError):
    """Provider 调用失败，已耗尽重试。"""
