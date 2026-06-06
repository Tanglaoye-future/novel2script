"""章节切分器：把整本小说文本切成 [Chapter] 列表。

策略：基于行首启发式正则识别章节标题。覆盖常见中英文格式：
- 第一章 / 第1章 / 第一回 / 第一节 / 第一篇
- Chapter 1 / Chapter I / CHAPTER 1
- 一、 / 1. / 1) / 1、（仅在前后被空行包围时）
- 楔子 / 序章 / 引子 / 尾声 / 后记 等特殊章节
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# 中文数字字符集（含繁体常见字）
_CN_NUM = r"零一二三四五六七八九十百千两〇○"

# 章节标题模式：从最具体到最宽松
_CHAPTER_PATTERNS: list[re.Pattern[str]] = [
    # 第X章 / 第X回 / 第X节 / 第X篇 / 第X卷 + 可选标题
    re.compile(rf"^\s*第\s*[{_CN_NUM}0-9]+\s*[章回节篇卷折]\b.*$"),
    # Chapter X / CHAPTER X / Chap. X
    re.compile(r"^\s*(?:Chapter|CHAPTER|Chap\.?)\s+[\dIVXLCDM]+\b.*$"),
    # 特殊章节名：楔子、序章、序、序言、引子、尾声、后记、终章、番外
    re.compile(r"^\s*(?:楔子|序章|序言|序|引子|尾声|后记|终章|番外|附录)\s*$"),
    # 中文数字 + 顿号/、 单独成行（如「一、」「二、」）
    re.compile(rf"^\s*[{_CN_NUM}]+\s*[、.．]\s*\S.*$"),
]


@dataclass
class Chapter:
    """一章小说。

    index: 1-based 章节序号
    title: 章节标题原文（可能为空，例如「楔子」）
    paragraphs: 章节正文按段落切分（已去除空行）
    """
    index: int
    title: str
    paragraphs: list[str] = field(default_factory=list)

    @property
    def body(self) -> str:
        """返回拼接后的章节正文（不含标题）。"""
        return "\n\n".join(self.paragraphs)

    @property
    def char_count(self) -> int:
        return sum(len(p) for p in self.paragraphs)


def _is_chapter_heading(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > 80:  # 章节标题极少超过 80 字符
        return False
    return any(p.match(line) for p in _CHAPTER_PATTERNS)


def _split_paragraphs(block: str) -> list[str]:
    """按空行切段，并清除每段首尾空白。"""
    paras = re.split(r"\n\s*\n", block.strip())
    return [p.strip() for p in paras if p.strip()]


def parse_chapters(text: str) -> list[Chapter]:
    """把整本小说切成章节。

    如果检测不到任何章节标题，整本作为单章返回（title 为 "正文"）。
    """
    if not text or not text.strip():
        return []

    lines = text.splitlines()
    # 找出所有章节标题行的行号
    heading_indices = [i for i, line in enumerate(lines) if _is_chapter_heading(line)]

    if not heading_indices:
        return [Chapter(index=1, title="正文", paragraphs=_split_paragraphs(text))]

    chapters: list[Chapter] = []

    # 第一个章节标题之前可能有"卷首/前言"——若内容非空则作为序章保留
    first_idx = heading_indices[0]
    if first_idx > 0:
        prelude = "\n".join(lines[:first_idx]).strip()
        if prelude:
            chapters.append(
                Chapter(index=len(chapters) + 1, title="卷首", paragraphs=_split_paragraphs(prelude))
            )

    # 切出每一章
    for i, start in enumerate(heading_indices):
        end = heading_indices[i + 1] if i + 1 < len(heading_indices) else len(lines)
        title = lines[start].strip()
        body = "\n".join(lines[start + 1 : end]).strip()
        chapters.append(
            Chapter(
                index=len(chapters) + 1,
                title=title,
                paragraphs=_split_paragraphs(body),
            )
        )

    return chapters
