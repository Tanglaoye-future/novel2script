"""validator 单元测试：覆盖两层校验与 auto_repair。"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from backend.core.validator import auto_repair, validate_screenplay


ROOT = Path(__file__).resolve().parents[2]


def _minimal_valid_data():
    return {
        "schema_version": "0.1",
        "meta": {"title": "T", "source_novel": "N"},
        "characters": [{"id": "c01", "name": "A"}],
        "locations": [{"id": "l01", "name": "Room"}],
        "scenes": [
            {
                "id": "S001",
                "heading": {"int_ext": "INT", "location_id": "l01", "time_of_day": "NIGHT"},
                "characters_present": ["c01"],
                "beats": [
                    {"type": "action", "content": "Walks in."},
                    {"type": "dialogue", "character_id": "c01", "content": "Hi.", "subtext": "..."},
                ],
            }
        ],
    }


def test_example_yaml_validates_clean():
    data = yaml.safe_load((ROOT / "schema" / "example.yaml").read_text(encoding="utf-8"))
    report = validate_screenplay(data)
    assert report.ok, f"example.yaml 应当通过校验，但收到错误：{report.errors}"


def test_minimal_valid_passes():
    report = validate_screenplay(_minimal_valid_data())
    assert report.ok


def test_schema_layer_catches_missing_field():
    data = _minimal_valid_data()
    del data["meta"]["title"]
    report = validate_screenplay(data)
    assert not report.ok
    assert any("title" in e for e in report.errors)


def test_schema_layer_catches_bad_enum():
    data = _minimal_valid_data()
    data["scenes"][0]["heading"]["time_of_day"] = "MIDNIGHT"
    report = validate_screenplay(data)
    assert not report.ok
    assert any("time_of_day" in e or "MIDNIGHT" in e for e in report.errors)


def test_consistency_layer_catches_unknown_character_id():
    data = _minimal_valid_data()
    data["scenes"][0]["beats"].append(
        {"type": "dialogue", "character_id": "c99", "content": "Who?", "subtext": "?"}
    )
    report = validate_screenplay(data)
    assert not report.ok
    assert any("c99" in e and "[ref]" in e for e in report.errors)


def test_consistency_layer_catches_unknown_location_id():
    data = _minimal_valid_data()
    data["scenes"][0]["heading"]["location_id"] = "l99"
    report = validate_screenplay(data)
    assert not report.ok
    assert any("l99" in e for e in report.errors)


def test_warning_for_speaker_not_in_characters_present():
    data = _minimal_valid_data()
    data["scenes"][0]["characters_present"] = []  # 清空在场
    report = validate_screenplay(data)
    # 角色合法但不在场——只给 warning，不算错误
    assert report.ok
    assert any("characters_present" in w for w in report.warnings)


def test_auto_repair_fills_characters_present():
    data = _minimal_valid_data()
    data["scenes"][0]["characters_present"] = []
    repaired = auto_repair(data)
    assert "c01" in repaired["scenes"][0]["characters_present"]


def test_auto_repair_fills_schema_version():
    data = _minimal_valid_data()
    del data["schema_version"]
    repaired = auto_repair(data)
    assert repaired["schema_version"] == "0.1"


def test_auto_repair_does_not_mutate_input():
    data = _minimal_valid_data()
    data["scenes"][0]["characters_present"] = []
    snapshot = json.dumps(data)
    auto_repair(data)
    assert json.dumps(data) == snapshot, "auto_repair 不应修改输入"
