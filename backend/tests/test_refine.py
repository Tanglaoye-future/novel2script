"""场景级 refine 测试。"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.core.llm import FakeProvider, LLMError
from backend.core.pipeline import refine_scene


def _sample_screenplay():
    return {
        "schema_version": "0.1",
        "meta": {"title": "T", "source_novel": "N"},
        "characters": [
            {"id": "c01", "name": "我", "voice_traits": "句短"},
            {"id": "c02", "name": "大哥", "voice_traits": "温言压制"},
        ],
        "locations": [{"id": "l01", "name": "卧房"}],
        "scenes": [
            {
                "id": "S001",
                "heading": {"int_ext": "INT", "location_id": "l01", "time_of_day": "NIGHT"},
                "source": {"chapter_index": 1, "chapter_title": "一", "paragraph_range": [0, 3]},
                "characters_present": ["c01"],
                "beats": [
                    {"type": "dialogue", "character_id": "c01", "content": "原台词。", "subtext": "x"}
                ],
            }
        ],
    }


def test_refine_preserves_id_and_source():
    sp = _sample_screenplay()
    scene = sp["scenes"][0]
    fake = FakeProvider(
        responses=[
            json.dumps(
                {
                    "id": "XXX_should_be_overwritten",
                    "heading": scene["heading"],
                    "characters_present": ["c01"],
                    "beats": [
                        {"type": "dialogue", "character_id": "c01", "content": "新台词。", "subtext": "y"}
                    ],
                }
            )
        ]
    )
    new_scene = refine_scene(scene, "让台词更短", screenplay=sp, provider=fake)
    assert new_scene["id"] == "S001"  # 强制保留
    assert new_scene["source"] == scene["source"]  # 强制保留
    assert new_scene["beats"][0]["content"] == "新台词。"


def test_refine_rejects_empty_instruction():
    sp = _sample_screenplay()
    with pytest.raises(ValueError):
        refine_scene(sp["scenes"][0], "  ", screenplay=sp, provider=FakeProvider())


def test_refine_passes_voice_traits_to_prompt():
    sp = _sample_screenplay()
    fake = FakeProvider(responses=[json.dumps({"id": "S001", "heading": sp["scenes"][0]["heading"], "beats": [{"type": "action", "content": "x"}]})])
    refine_scene(sp["scenes"][0], "tighter", screenplay=sp, provider=fake)
    system, user = fake.history[0]
    # voice_traits 必须出现在 user prompt 里
    assert "句短" in user


def test_refine_endpoint_404_for_unknown_scene(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    from backend.api.main import app
    from backend.api import convert as convert_module
    monkeypatch.setattr(convert_module, "get_provider", lambda name=None: FakeProvider(responses=["{}"]))
    client = TestClient(app)
    resp = client.post("/refine", json={"screenplay": _sample_screenplay(), "scene_id": "S999", "instruction": "x"})
    assert resp.status_code == 404


def test_refine_endpoint_happy_path(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    from backend.api.main import app
    from backend.api import convert as convert_module
    sp = _sample_screenplay()
    refined = json.dumps(
        {
            "id": "ignored",
            "heading": sp["scenes"][0]["heading"],
            "characters_present": ["c01"],
            "beats": [{"type": "action", "content": "重写动作"}],
        }
    )
    monkeypatch.setattr(convert_module, "get_provider", lambda name=None: FakeProvider(responses=[refined]))
    client = TestClient(app)
    resp = client.post("/refine", json={"screenplay": sp, "scene_id": "S001", "instruction": "tighter"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scene"]["id"] == "S001"
    assert body["scene"]["beats"][0]["content"] == "重写动作"


def test_refine_raises_on_invalid_json_response():
    sp = _sample_screenplay()
    fake = FakeProvider(responses=["not json at all"])
    with pytest.raises(LLMError):
        refine_scene(sp["scenes"][0], "x", screenplay=sp, provider=fake)
