"""转换 Pipeline：小说原文 → 结构化剧本字典。

流程：
  1. chapter_parser 切章
  2. 逐章调用 LLM，每章产出 { new_characters, new_locations, scenes }
  3. 跨章合并：dedupe by id，scenes 顺序拼接
  4. 输出符合 schema/screenplay.schema.json 的 dict

合并策略：
  - characters/locations 按 id 去重；id 冲突时保留先出现的
  - 提供逐章 existing_* 上下文，鼓励 LLM 复用 id 而不是每章都重新分配
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

from .chapter_parser import Chapter, parse_chapters
from .llm import LLMError, LLMProvider, get_provider
from .prompts import (
    CHAPTER_TO_SCENES_SYSTEM,
    SCENE_REFINE_SYSTEM,
    build_chapter_user_prompt,
    build_refine_user_prompt,
)

log = logging.getLogger(__name__)


@dataclass
class ConvertOptions:
    title: str
    source_novel: str
    source_author: str | None = None
    genre: str | None = None
    logline: str | None = None
    tone: str | None = None
    language: str = "zh-CN"


def convert_novel(
    text: str,
    options: ConvertOptions,
    *,
    provider: LLMProvider | None = None,
    progress: Callable[[str, int, int], None] | None = None,
) -> dict:
    """整本转换入口。返回符合 schema 的 dict。

    progress(stage, current, total) 可选回调，供 UI 显示进度。
    """
    provider = provider or get_provider()
    chapters = parse_chapters(text)
    if not chapters:
        raise ValueError("输入文本为空或解析后无任何章节。")

    if progress:
        progress("parsed_chapters", len(chapters), len(chapters))

    characters: list[dict] = []
    locations: list[dict] = []
    scenes: list[dict] = []
    scene_counter = 1

    for i, chapter in enumerate(chapters, start=1):
        if progress:
            progress("converting_chapter", i, len(chapters))
        chunk = _convert_chapter(
            provider=provider,
            chapter=chapter,
            options=options,
            existing_characters=characters,
            existing_locations=locations,
            scene_id_start=_format_scene_id(scene_counter),
        )
        characters = _merge_by_id(characters, chunk.get("new_characters", []))
        locations = _merge_by_id(locations, chunk.get("new_locations", []))
        for scene in chunk.get("scenes", []):
            # 强制重排 scene id，避免 LLM 没遵守 scene_id_start
            scene["id"] = _format_scene_id(scene_counter)
            scene_counter += 1
            scenes.append(scene)

    return {
        "schema_version": "0.1",
        "meta": {
            "title": options.title,
            "source_novel": options.source_novel,
            "source_author": options.source_author,
            "genre": options.genre,
            "logline": options.logline,
            "tone": options.tone,
            "language": options.language,
            "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        },
        "characters": characters or [{"id": "c01", "name": options.title}],
        "locations": locations,
        "scenes": scenes,
        "notes": [],
    }


def _convert_chapter(
    *,
    provider: LLMProvider,
    chapter: Chapter,
    options: ConvertOptions,
    existing_characters: list[dict],
    existing_locations: list[dict],
    scene_id_start: str,
) -> dict:
    """单章调用 LLM 并解析返回。"""
    user_prompt = build_chapter_user_prompt(
        meta={
            "title": options.title,
            "source_novel": options.source_novel,
            "genre": options.genre,
            "logline": options.logline,
            "tone": options.tone,
        },
        chapter_index=chapter.index,
        chapter_title=chapter.title,
        chapter_text=chapter.body,
        existing_characters=existing_characters,
        existing_locations=existing_locations,
        scene_id_start=scene_id_start,
    )
    resp = provider.generate_json(CHAPTER_TO_SCENES_SYSTEM, user_prompt, temperature=0.4)
    try:
        chunk = json.loads(resp.text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"第 {chapter.index} 章返回的 JSON 不合法：{exc}") from exc

    # 补全：如果 LLM 漏掉了 source 字段，按章节信息回填
    for scene in chunk.get("scenes", []):
        scene.setdefault(
            "source",
            {
                "chapter_index": chapter.index,
                "chapter_title": chapter.title,
                "paragraph_range": [0, max(0, len(chapter.paragraphs) - 1)],
            },
        )
        scene.setdefault("notes", [])
    return chunk


def refine_scene(
    scene: dict,
    instruction: str,
    *,
    screenplay: dict,
    provider: LLMProvider | None = None,
) -> dict:
    """对单个场景做 AI 重写。

    保留 id 与 source 字段不变，由 LLM 调整 beats / synopsis 让戏更紧凑。
    screenplay 用于抽取角色的 voice_traits，作为重写约束注入 prompt。
    """
    if not instruction or not instruction.strip():
        raise ValueError("refine 指令不能为空。")
    provider = provider or get_provider()

    char_voice_hints = {
        c["id"]: c.get("voice_traits") or ""
        for c in screenplay.get("characters", [])
        if c["id"] in set(scene.get("characters_present", []))
    }

    user_prompt = build_refine_user_prompt(scene, instruction, char_voice_hints)
    resp = provider.generate_json(SCENE_REFINE_SYSTEM, user_prompt, temperature=0.6)
    try:
        new_scene = json.loads(resp.text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"refine 返回的 JSON 不合法：{exc}") from exc

    # 强制保留 id 与 source（防止 LLM 改写关键字段）
    new_scene["id"] = scene["id"]
    if scene.get("source"):
        new_scene["source"] = scene["source"]
    return new_scene


def _format_scene_id(n: int) -> str:
    return f"S{n:03d}"


def _merge_by_id(existing: list[dict], new: list[dict]) -> list[dict]:
    """以 id 为键合并；冲突时保留 existing。"""
    seen = {item["id"] for item in existing if "id" in item}
    merged = list(existing)
    for item in new:
        if "id" not in item or item["id"] in seen:
            continue
        merged.append(item)
        seen.add(item["id"])
    return merged
