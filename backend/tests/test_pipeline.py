"""Pipeline 集成测试：用 FakeProvider 验证多章合并、id 去重、scene 编号。"""
from __future__ import annotations

import json

from backend.core.llm import FakeProvider
from backend.core.pipeline import ConvertOptions, _format_scene_id, _merge_by_id, convert_novel


def _ch_response(*, new_chars, new_locs, scenes):
    return json.dumps(
        {"new_characters": new_chars, "new_locations": new_locs, "scenes": scenes},
        ensure_ascii=False,
    )


def test_format_scene_id():
    assert _format_scene_id(1) == "S001"
    assert _format_scene_id(42) == "S042"
    assert _format_scene_id(123) == "S123"


def test_merge_by_id_dedupes():
    existing = [{"id": "c01", "name": "A"}]
    new = [{"id": "c01", "name": "A'"}, {"id": "c02", "name": "B"}]
    merged = _merge_by_id(existing, new)
    assert [m["id"] for m in merged] == ["c01", "c02"]
    assert merged[0]["name"] == "A", "冲突时应保留 existing"


def test_pipeline_three_chapters_dedupes_and_renumbers_scenes():
    text = """第一章 月光

夜深了。

第二章 眼色

街上。

第三章 何先生

诊室。
"""
    fake = FakeProvider(
        responses=[
            _ch_response(
                new_chars=[{"id": "c01", "name": "我"}],
                new_locs=[{"id": "l01", "name": "卧房"}],
                scenes=[
                    {
                        "id": "S001",
                        "heading": {"int_ext": "INT", "location_id": "l01", "time_of_day": "NIGHT"},
                        "beats": [{"type": "action", "content": "月光透窗"}],
                        "characters_present": ["c01"],
                    }
                ],
            ),
            # 第二章：复用 c01，新增 l02
            _ch_response(
                new_chars=[],
                new_locs=[{"id": "l02", "name": "街道"}],
                scenes=[
                    {
                        "id": "S001",  # LLM 错误地从 S001 重新开始；pipeline 必须重排
                        "heading": {"int_ext": "EXT", "location_id": "l02", "time_of_day": "MORNING"},
                        "beats": [{"type": "action", "content": "出门"}],
                    },
                    {
                        "id": "S002",
                        "heading": {"int_ext": "EXT", "location_id": "l02", "time_of_day": "DAY"},
                        "beats": [{"type": "action", "content": "回望"}],
                    },
                ],
            ),
            # 第三章：尝试重复 c01（应被去重）
            _ch_response(
                new_chars=[{"id": "c01", "name": "我（重复）"}, {"id": "c03", "name": "何先生"}],
                new_locs=[{"id": "l03", "name": "诊室"}],
                scenes=[
                    {
                        "id": "S010",  # LLM 乱编 id
                        "heading": {"int_ext": "INT", "location_id": "l03", "time_of_day": "EVENING"},
                        "beats": [
                            {"type": "dialogue", "character_id": "c03", "content": "把脉。", "subtext": "试肉。"}
                        ],
                        "characters_present": ["c01", "c03"],
                    }
                ],
            ),
        ]
    )

    options = ConvertOptions(title="月光", source_novel="狂人日记")
    result = convert_novel(text, options, provider=fake)

    # scene 重编号检查
    scene_ids = [s["id"] for s in result["scenes"]]
    assert scene_ids == ["S001", "S002", "S003", "S004"]

    # character 去重检查
    char_ids = [c["id"] for c in result["characters"]]
    assert char_ids == ["c01", "c03"]  # 重复的 c01 被保留 existing 版本
    assert result["characters"][0]["name"] == "我"

    # location 顺序拼接
    loc_ids = [l["id"] for l in result["locations"]]
    assert loc_ids == ["l01", "l02", "l03"]

    # source 字段被回填
    for scene in result["scenes"]:
        assert "source" in scene
        assert "chapter_index" in scene["source"]


def test_pipeline_progress_callback_called_per_chapter():
    text = "第一章 A\n\n内容。\n\n第二章 B\n\n内容。\n"
    fake = FakeProvider(responses=[_ch_response(new_chars=[], new_locs=[], scenes=[])])
    progress_events: list[tuple[str, int, int]] = []

    convert_novel(
        text,
        ConvertOptions(title="t", source_novel="s"),
        provider=fake,
        progress=lambda stage, cur, total: progress_events.append((stage, cur, total)),
    )

    stages = [e[0] for e in progress_events]
    assert "parsed_chapters" in stages
    assert stages.count("converting_chapter") == 2


def test_pipeline_rejects_empty_text():
    import pytest
    fake = FakeProvider()
    with pytest.raises(ValueError):
        convert_novel("", ConvertOptions(title="t", source_novel="s"), provider=fake)
