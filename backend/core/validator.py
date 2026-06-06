"""剧本数据校验器：两层校验。

第一层：JSON Schema（结构/类型/枚举/正则/conditional required）
第二层：跨字段引用一致性（character_id 必须存在于 characters[] 等）

设计原因见 docs/yaml-schema-design.md §5。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "screenplay.schema.json"


@dataclass
class ValidationReport:
    """校验结果。errors 非空表示失败。warnings 非致命。"""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def __bool__(self) -> bool:  # pragma: no cover - 习惯化语法
        return self.ok


# ---------------------------------------------------------------------------
# Schema 单例
# ---------------------------------------------------------------------------

_schema_cache: dict | None = None


def _load_schema() -> dict:
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _schema_cache


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------


def validate_screenplay(data: dict) -> ValidationReport:
    """主入口：先跑 Schema 层，再跑业务一致性层。"""
    report = ValidationReport()
    _run_schema_layer(data, report)
    if report.ok:
        # Schema 层挂掉时业务层不再跑（避免 KeyError 噪音）
        _run_consistency_layer(data, report)
    return report


# ---------------------------------------------------------------------------
# 第一层：JSON Schema
# ---------------------------------------------------------------------------


def _run_schema_layer(data: dict, report: ValidationReport) -> None:
    schema = _load_schema()
    validator = Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        report.errors.append(f"[schema] {loc}: {err.message}")


# ---------------------------------------------------------------------------
# 第二层：跨字段引用一致性
# ---------------------------------------------------------------------------


def _run_consistency_layer(data: dict, report: ValidationReport) -> None:
    char_ids = {c["id"] for c in data.get("characters", [])}
    loc_ids = {l["id"] for l in data.get("locations", [])}

    for scene_idx, scene in enumerate(data.get("scenes", [])):
        scene_path = f"scenes[{scene_idx}]({scene.get('id', '?')})"

        # heading.location_id 引用检查
        loc_id = scene.get("heading", {}).get("location_id")
        if loc_id and loc_id not in loc_ids:
            report.errors.append(
                f"[ref] {scene_path}.heading.location_id={loc_id!r} 未在 locations[] 中定义"
            )

        # characters_present 子集检查
        for cid in scene.get("characters_present", []):
            if cid not in char_ids:
                report.errors.append(
                    f"[ref] {scene_path}.characters_present 含未定义角色 {cid!r}"
                )

        # beats.character_id 引用检查
        for beat_idx, beat in enumerate(scene.get("beats", [])):
            cid = beat.get("character_id")
            if cid is None:
                continue
            if cid not in char_ids:
                report.errors.append(
                    f"[ref] {scene_path}.beats[{beat_idx}].character_id={cid!r} 未在 characters[] 中定义"
                )
            elif cid not in set(scene.get("characters_present", [])):
                # 说话的人没在场——非致命，但提醒作者
                report.warnings.append(
                    f"[hint] {scene_path}.beats[{beat_idx}]: {cid!r} 在说话但未列入 characters_present"
                )


# ---------------------------------------------------------------------------
# 修复辅助：在错误已知的前提下尝试自动补救
# ---------------------------------------------------------------------------


def auto_repair(data: dict) -> dict:
    """在不破坏 schema 的前提下做轻量修复。

    当前修复策略：
    - 缺失 characters_present 时按 beats 中出现的 character_id 自动补齐
    - 缺失 schema_version 时填入 "0.1"
    """
    data = json.loads(json.dumps(data))  # deep copy without importing copy
    data.setdefault("schema_version", "0.1")
    char_ids = {c["id"] for c in data.get("characters", [])}

    for scene in data.get("scenes", []):
        present = set(scene.get("characters_present") or [])
        for beat in scene.get("beats", []):
            cid = beat.get("character_id")
            if cid and cid in char_ids:
                present.add(cid)
        scene["characters_present"] = sorted(present)

    return data
