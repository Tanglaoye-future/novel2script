"""/convert 端点测试：用 fake provider 跑端到端。"""
from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    # 切到 fake provider，避免触发真实 API
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    from backend.api.main import app

    # 因为 fake provider 默认返回 "{}"，无法构成合法 screenplay，
    # 这里通过 monkeypatch 的方式注入预设响应。
    from backend.core.llm import FakeProvider
    from backend.api import convert as convert_module

    fake_resp = json.dumps(
        {
            "new_characters": [{"id": "c01", "name": "我"}],
            "new_locations": [{"id": "l01", "name": "卧房"}],
            "scenes": [
                {
                    "id": "S001",
                    "heading": {"int_ext": "INT", "location_id": "l01", "time_of_day": "NIGHT"},
                    "beats": [
                        {"type": "action", "content": "月光下醒来。"},
                        {"type": "voiceover", "character_id": "c01", "content": "好月光。", "subtext": "清醒。"},
                    ],
                    "characters_present": ["c01"],
                }
            ],
        },
        ensure_ascii=False,
    )

    def fake_get_provider(name=None, **kw):
        return FakeProvider(responses=[fake_resp])

    monkeypatch.setattr(convert_module, "get_provider", fake_get_provider)
    return TestClient(app)


def test_convert_returns_valid_screenplay(client):
    resp = client.post(
        "/convert",
        json={
            "text": "第一章 月光\n\n夜里我醒来。\n",
            "title": "月光",
            "source_novel": "狂人日记",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["validation"]["ok"] is True
    assert body["screenplay"]["meta"]["title"] == "月光"
    assert len(body["screenplay"]["scenes"]) == 1
    assert body["screenplay"]["scenes"][0]["id"] == "S001"


def test_convert_rejects_empty_text(client):
    resp = client.post(
        "/convert",
        json={"text": "", "title": "x", "source_novel": "x"},
    )
    assert resp.status_code == 422  # Pydantic field validation


def test_convert_rejects_missing_title(client):
    resp = client.post(
        "/convert",
        json={"text": "abc", "source_novel": "x"},
    )
    assert resp.status_code == 422
