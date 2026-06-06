"""命令行入口：novel2script convert <input> -o <output>.yaml

适合脚本化批量转换、CI 用。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover
    pass

from backend.core.llm import LLMError, get_provider
from backend.core.pipeline import ConvertOptions, convert_novel
from backend.core.validator import auto_repair, validate_screenplay


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="novel2script",
        description="把小说转换成结构化 YAML 剧本。",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_convert = sub.add_parser("convert", help="转换小说为剧本 YAML")
    p_convert.add_argument("input", type=Path, help="小说原文路径（UTF-8 文本）")
    p_convert.add_argument("-o", "--output", type=Path, required=True, help="输出 YAML 路径")
    p_convert.add_argument("--title", help="剧本标题（默认用输入文件 stem）")
    p_convert.add_argument("--source-novel", help="原著名（默认同 --title）")
    p_convert.add_argument("--source-author", default=None)
    p_convert.add_argument("--genre", default=None)
    p_convert.add_argument("--logline", default=None)
    p_convert.add_argument("--tone", default=None)
    p_convert.add_argument("--provider", default=None, help="LLM provider 名（默认按环境变量）")
    p_convert.add_argument(
        "--allow-warnings",
        action="store_true",
        help="即使存在 warning 也写出文件（默认就是会写，本开关保留为显式语义）",
    )

    args = parser.parse_args(argv)
    if args.cmd == "convert":
        return _cmd_convert(args)
    return 1  # pragma: no cover


def _cmd_convert(args: argparse.Namespace) -> int:
    if not args.input.exists():
        print(f"[错误] 输入文件不存在: {args.input}", file=sys.stderr)
        return 2

    text = args.input.read_text(encoding="utf-8")
    title = args.title or args.input.stem
    source_novel = args.source_novel or title

    try:
        provider = get_provider(args.provider)
    except LLMError as exc:
        print(f"[错误] LLM Provider 初始化失败：{exc}", file=sys.stderr)
        return 3

    options = ConvertOptions(
        title=title,
        source_novel=source_novel,
        source_author=args.source_author,
        genre=args.genre,
        logline=args.logline,
        tone=args.tone,
    )

    def _progress(stage: str, cur: int, total: int) -> None:
        if stage == "parsed_chapters":
            print(f"[1/{total}] 解析章节完成，共 {total} 章")
        elif stage == "converting_chapter":
            print(f"[{cur}/{total}] 正在转换第 {cur} 章...")

    try:
        screenplay = convert_novel(text, options, provider=provider, progress=_progress)
    except (LLMError, ValueError) as exc:
        print(f"[错误] 转换失败：{exc}", file=sys.stderr)
        return 4

    screenplay = auto_repair(screenplay)
    report = validate_screenplay(screenplay)
    if not report.ok:
        print("[警告] 校验未通过：", file=sys.stderr)
        for e in report.errors:
            print(f"  - {e}", file=sys.stderr)
    for w in report.warnings:
        print(f"[提示] {w}", file=sys.stderr)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        yaml.safe_dump(screenplay, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )
    print(f"[完成] 已写出 {args.output}（{len(screenplay['scenes'])} 个场景）")
    return 0 if report.ok else 5


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
