"""七牛云 LLM Provider 实现。

七牛云 AI 推理服务提供 OpenAI 兼容协议（endpoint: api.qnaigc.com/v1）。
文档：https://developer.qiniu.com/aitokenapi

支持模型：
- qiniu-qva-7b         轻量快速
- qiniu-qva-14b        均衡
- qiniu-qva-72b        最强推理
- qwen3-235b-a22b      通义千问 3（七牛托管）
- doubao-lite-32k      豆包轻量
- kimi-k2-instruct     Kimi K2
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from .base import LLMError, LLMProvider, LLMResponse, LLMUsage


DEFAULT_BASE_URL = "https://api.qnaigc.com/v1"
DEFAULT_MODEL = "qwen3-235b-a22b"


class QiniuProvider(LLMProvider):
    """七牛云 AI 推理服务的 OpenAI 兼容封装。"""

    name = "qiniu"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        *,
        max_retries: int = 2,
        request_timeout: float = 120.0,
    ) -> None:
        api_key = api_key or os.getenv("QINIU_API_KEY")
        if not api_key:
            raise LLMError(
                "QINIU_API_KEY 未配置。请在 .env 或环境变量里设置。\n"
                "获取方式：https://developer.qiniu.com/aitokenapi"
            )

        from openai import OpenAI

        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url or os.getenv("QINIU_BASE_URL", DEFAULT_BASE_URL),
            timeout=request_timeout,
        )
        self._model = model or os.getenv("QINIU_MODEL", DEFAULT_MODEL)
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
        resp.text = _strip_json_fences(resp.text)
        try:
            json.loads(resp.text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"七牛云 LLM 返回的不是合法 JSON: {exc}\n---\n{resp.text[:500]}") from exc
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
            except Exception as exc:
                last_exc = exc
                if attempt >= self._max_retries:
                    raise LLMError(f"七牛云 LLM 调用失败（{self._max_retries + 1} 次尝试均失败）：{exc}") from exc
                time.sleep(1.5 ** attempt)
        else:  # pragma: no cover
            raise LLMError(f"七牛云 LLM 调用失败：{last_exc}")

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
    text = text.strip()
    if text.startswith("```"):
        text = _JSON_FENCE_RE.sub("", text).strip()
    return text
