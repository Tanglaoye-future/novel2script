"""LLM Provider 测试：覆盖 fake provider、factory、错误处理。"""
from __future__ import annotations

import json

import pytest

from backend.core.llm import FakeProvider, LLMError, get_provider
from backend.core.llm.deepseek import _strip_json_fences


def test_factory_returns_fake():
    provider = get_provider("fake", responses=["hello"])
    assert provider.name == "fake"
    assert provider.generate("sys", "user").text == "hello"


def test_factory_unknown_provider_raises():
    with pytest.raises(LLMError):
        get_provider("nonexistent")


def test_fake_provider_records_history():
    provider = FakeProvider(responses=['{"k": 1}', '{"k": 2}'])
    r1 = provider.generate_json("sys", "u1")
    r2 = provider.generate_json("sys", "u2")
    assert json.loads(r1.text)["k"] == 1
    assert json.loads(r2.text)["k"] == 2
    assert provider.history == [("sys", "u1"), ("sys", "u2")]


def test_fake_provider_loops_last_response():
    provider = FakeProvider(responses=["only"])
    assert provider.generate("s", "u").text == "only"
    assert provider.generate("s", "u").text == "only"


def test_strip_json_fences_handles_markdown_wrapping():
    raw = """```json
{"a": 1}
```"""
    assert _strip_json_fences(raw) == '{"a": 1}'


def test_strip_json_fences_idempotent_on_plain_json():
    assert _strip_json_fences('{"a": 1}') == '{"a": 1}'


def test_deepseek_requires_api_key(monkeypatch):
    """没设置 DEEPSEEK_API_KEY 时构造应该明确报错。"""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    from backend.core.llm.deepseek import DeepSeekProvider
    with pytest.raises(LLMError, match="DEEPSEEK_API_KEY"):
        DeepSeekProvider()
