"""Schema 自检测试：保证 schema/example.yaml 始终是 schema 的合法实例。"""
from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schema" / "screenplay.schema.json"
EXAMPLE_PATH = ROOT / "schema" / "example.yaml"


def test_schema_is_valid_jsonschema():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)


def test_example_yaml_matches_schema():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    data = yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(data)


def test_dialogue_beat_requires_character_id():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bad = {
        "schema_version": "0.1",
        "meta": {"title": "x", "source_novel": "x"},
        "characters": [{"id": "c01", "name": "x"}],
        "scenes": [
            {
                "id": "S001",
                "heading": {"int_ext": "INT", "location_id": "l01", "time_of_day": "DAY"},
                "beats": [{"type": "dialogue", "content": "hi"}],
            }
        ],
    }
    errors = list(Draft202012Validator(schema).iter_errors(bad))
    assert errors, "dialogue beat without character_id should fail"
