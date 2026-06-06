"""DeepSeek Provider 实现。

DeepSeek 提供 OpenAI 兼容协议，因此复用 openai SDK，仅修改 base_url。
文档：https://platform.deepseek.com/api-docs/
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from .base import LLMError, LLMProvider, LLMResponse, LLMUsage


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


class DeepSeekProvider(LLMProvider):
    """DeepSeek-Chat / DeepSeek-Reasoner 的 OpenAI 兼容封装。"""

    name = "deepseek"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        *,
        max_retries: int = 2,
        request_timeout: float = 120.0,
    ) -> None:
        api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise LLMError(
                "DEEPSEEK_API_KEY 未配置。请在 .env 或环境变量里设置。"
            )

        # 延迟导入 openai，使得没有 key 时也可以 import 本模块（测试用）
        from openai import OpenAI

        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url or os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL),
            timeout=request_timeout,
        )
        self._model = model or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
        self._max_retries = max_retries

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def generate(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        return self._chat(system, user, temperature=temperature, max_tokens=max_tokens, json_mode=False)

    def generate_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.3,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        resp = self._chat(system, user, temperature=temperature, max_tokens=max_tokens, json_mode=True)
        # 兜底：剥除可能的 ```json ... ``` markdown 包裹
        resp.text = _strip_json_fences(resp.text)
        # 再 round-trip 一次确保合法 JSON
        try:
            json.loads(resp.text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"DeepSeek 返回的不是合法 JSON: {exc}\n---\n{resp.text[:500]}") from exc
        return resp

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float,
        max_tokens: int | None,
        json_mode: bool,
    ) -> LLMResponse:
        params: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if json_mode:
            params["response_format"] = {"type": "json_object"}

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                completion = self._client.chat.completions.create(**params)
                break
            except Exception as exc:  # noqa: BLE001 - 上游异常类型复杂，由 SDK 决定
                last_exc = exc
                if attempt >= self._max_retries:
                    raise LLMError(f"DeepSeek 调用失败（{self._max_retries + 1} 次尝试均失败）：{exc}") from exc
                time.sleep(1.5 ** attempt)
        else:  # pragma: no cover
            raise LLMError(f"DeepSeek 调用失败：{last_exc}")

        choice = completion.choices[0]
        usage_obj = completion.usage
        usage = LLMUsage(
            prompt_tokens=getattr(usage_obj, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage_obj, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage_obj, "total_tokens", 0) or 0,
        )
        return LLMResponse(
            text=(choice.message.content or "").strip(),
            usage=usage,
            model=self._model,
        )


_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_json_fences(text: str) -> str:
    """如果模型仍然返回 ```json ... ``` 包裹，剥掉。"""
    text = text.strip()
    if text.startswith("```"):
        text = _JSON_FENCE_RE.sub("", text).strip()
    return text
