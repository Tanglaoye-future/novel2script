"""LLM Prompt 模板。

集中维护 prompt，便于版本追踪与 A/B。每个 prompt 都附设计注记。
"""
from __future__ import annotations

import json
from textwrap import dedent


# ---------------------------------------------------------------------------
# chapter → scenes
# ---------------------------------------------------------------------------

CHAPTER_TO_SCENES_SYSTEM = dedent(
    """\
    你是资深小说改编剧本顾问，擅长把中文叙事文本拆解为可拍摄的剧本场景。

    严格遵守以下规则：

    1. 你的输出**必须是合法 JSON**，不要包裹 markdown，不要写解释。
    2. 把一章小说切成 **1~5 个场景（scene）**，按时间顺序排列。切分原则：
       - 地点变化 → 必拆
       - 时间跳跃 → 必拆
       - 同地点连续场景但戏剧动作完整改变 → 可拆
    3. 每个场景由 **节拍（beat）序列** 组成，每条节拍 `type` 必为下列之一：
       - "action" 动作/环境描写
       - "dialogue" 角色台词（必带 character_id）
       - "voiceover" 画外音/内心独白（必带 character_id）
       - "transition" 转场（如「渐隐至黑」「画面切」）
    4. 每条 dialogue/voiceover 都要给出 `subtext` 潜台词字段 —— 角色没说出口的真实意图。
       这是改编剧本的灵魂，不要省略。action/transition 的 subtext 可省。
    5. 角色用稳定 `id`（c01/c02/…）。优先复用 `existing_characters` 中已有的 id；只有原文出现新角色时才新增 id。
    6. 地点同理用 `id`（l01/l02/…），优先复用 `existing_locations`。
    7. `time_of_day` 必为这八个值之一："DAWN","MORNING","DAY","AFTERNOON","EVENING","NIGHT","LATER","CONTINUOUS"。
    8. `int_ext` 必为 "INT"（内）/ "EXT"（外）/ "INT/EXT"。

    输出 JSON 结构：
    {
      "new_characters": [
        {"id":"c0X","name":"...","aliases":[],"role":"protagonist|antagonist|supporting|minor",
         "archetype":"...","description":"...","voice_traits":"...","arc":"..."}
      ],
      "new_locations": [
        {"id":"l0X","name":"...","description":"..."}
      ],
      "scenes": [
        {
          "id":"S00X",
          "heading":{"int_ext":"INT","location_id":"l01","time_of_day":"NIGHT"},
          "source":{"chapter_index":N,"chapter_title":"...","paragraph_range":[start,end]},
          "synopsis":"一句话场景梗概",
          "characters_present":["c01","c02"],
          "beats":[
            {"type":"action","content":"...","subtext":null},
            {"type":"dialogue","character_id":"c01","parenthetical":"(冷笑)","content":"...","subtext":"..."}
          ],
          "notes":[]
        }
      ]
    }

    `new_characters` 与 `new_locations` 只放本章新增的，不要重复已经在 existing_* 里的。
    场景 id 用调用方给的 `scene_id_start` 起编号（如 scene_id_start=S005 表示第一场起 S005）。
    """
)


def build_chapter_user_prompt(
    *,
    meta: dict,
    chapter_index: int,
    chapter_title: str,
    chapter_text: str,
    existing_characters: list[dict],
    existing_locations: list[dict],
    scene_id_start: str,
) -> str:
    """构造单章转换的 user prompt。"""
    payload = {
        "meta": meta,
        "chapter_index": chapter_index,
        "chapter_title": chapter_title,
        "scene_id_start": scene_id_start,
        "existing_characters": [
            {"id": c["id"], "name": c["name"], "aliases": c.get("aliases", [])}
            for c in existing_characters
        ],
        "existing_locations": [
            {"id": l["id"], "name": l["name"]} for l in existing_locations
        ],
    }
    return dedent(
        f"""\
        # 改编上下文
        ```json
        {json.dumps(payload, ensure_ascii=False, indent=2)}
        ```

        # 本章原文
        ```
        {chapter_text}
        ```

        请把本章转换为剧本场景，返回符合系统提示中所述结构的 JSON。
        """
    )


# ---------------------------------------------------------------------------
# scene refine（PR11 用）
# ---------------------------------------------------------------------------

SCENE_REFINE_SYSTEM = dedent(
    """\
    你是资深剧本医生。用户会给你一个已生成的场景 JSON，以及他对这场戏的不满或重写方向。
    请输出**同样结构**的场景 JSON，保持 id/source 不变，调整 beats 让戏更紧凑、潜台词更刺骨、台词更符合角色 voice_traits。
    只输出 JSON，不要解释。
    """
)


def build_refine_user_prompt(scene: dict, instruction: str, character_voice_hints: dict[str, str]) -> str:
    return dedent(
        f"""\
        # 角色语言风格参考
        ```json
        {json.dumps(character_voice_hints, ensure_ascii=False, indent=2)}
        ```

        # 待重写场景
        ```json
        {json.dumps(scene, ensure_ascii=False, indent=2)}
        ```

        # 重写方向
        {instruction}
        """
    )
