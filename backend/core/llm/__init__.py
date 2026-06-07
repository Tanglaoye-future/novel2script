"""LLM Provider 工厂入口。

使用：
    from backend.core.llm import get_provider
    provider = get_provider()           # 按 .env 配置
    provider = get_provider("deepseek") # 显式指定
"""
from __future__ import annotations

import os

from .base import LLMError, LLMProvider, LLMResponse, LLMUsage
from .fake import FakeProvider

__all__ = [
    "LLMError",
    "LLMProvider",
    "LLMResponse",
    "LLMUsage",
    "FakeProvider",
    "get_provider",
]


def get_provider(name: str | None = None, **kwargs) -> LLMProvider:
    """返回 Provider 实例。

    name 优先级：参数 > 环境变量 LLM_PROVIDER > 默认 'deepseek'
    """
    name = (name or os.getenv("LLM_PROVIDER") or "qiniu").lower()

    if name == "fake":
        return FakeProvider(**kwargs)

    if name == "deepseek":
        from .deepseek import DeepSeekProvider
        return DeepSeekProvider(**kwargs)

    if name == "qiniu":
        from .qiniu import QiniuProvider
        return QiniuProvider(**kwargs)

    raise LLMError(f"未知 LLM provider: {name!r}。已支持: qiniu, deepseek, fake")
