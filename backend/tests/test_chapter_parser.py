"""章节切分器单元测试。"""
from __future__ import annotations

from backend.core.chapter_parser import Chapter, parse_chapters


def test_chinese_chapter_headings():
    text = """第一章 月光

今天晚上，很好的月光。

我不见他，已是三十多年。

第二章 眼色

早上小心出门。

赵贵翁的眼色便怪。

第三章 何先生

何先生为我把脉。
"""
    chapters = parse_chapters(text)
    assert len(chapters) == 3
    assert chapters[0].index == 1
    assert "第一章 月光" in chapters[0].title
    assert chapters[0].paragraphs[0].startswith("今天晚上")
    assert len(chapters[0].paragraphs) == 2
    assert chapters[2].title == "第三章 何先生"


def test_chinese_numeric_chapter_with_no_space():
    text = """第1章 月光
今天晚上，很好的月光。

第2章 眼色
小心出门。

第3章 何先生
把脉。
"""
    chapters = parse_chapters(text)
    assert len(chapters) == 3
    assert chapters[1].title == "第2章 眼色"


def test_english_chapter_headings():
    text = """Chapter 1: The Moon

The moonlight was bright tonight.

Chapter 2: The Glance

I left early.

Chapter 3: The Doctor

Dr. He came.
"""
    chapters = parse_chapters(text)
    assert len(chapters) == 3
    assert chapters[0].title.startswith("Chapter 1")


def test_special_chapter_names():
    text = """楔子

很久以前。

第一章 开端

故事开始了。

尾声

故事结束了。
"""
    chapters = parse_chapters(text)
    assert len(chapters) == 3
    assert chapters[0].title == "楔子"
    assert chapters[2].title == "尾声"


def test_no_headings_returns_single_chapter():
    text = """第一段。

第二段。"""
    chapters = parse_chapters(text)
    assert len(chapters) == 1
    assert chapters[0].title == "正文"
    assert len(chapters[0].paragraphs) == 2


def test_empty_input():
    assert parse_chapters("") == []
    assert parse_chapters("   \n\n  ") == []


def test_prelude_before_first_chapter_kept_as_juanshou():
    text = """这是序，作者的话。

可能有几段。

第一章 真正开始

正文。
"""
    chapters = parse_chapters(text)
    assert len(chapters) == 2
    assert chapters[0].title == "卷首"
    assert chapters[1].title == "第一章 真正开始"


def test_chapter_char_count_and_body():
    text = "第一章 标题\n\nABC\n\nDEF\n"
    chapters = parse_chapters(text)
    assert chapters[0].char_count == 6
    assert chapters[0].body == "ABC\n\nDEF"


def test_long_line_not_treated_as_heading():
    # 一段以"第一"开头的长正文不该被误判为章节标题
    text = "第一段是讲述某个故事的开头，主角走在路上想着今天的事情，他从未想过会遇到这样的情况，可一切就这样发生了。\n\n第二段。"
    chapters = parse_chapters(text)
    assert len(chapters) == 1
    assert chapters[0].title == "正文"
