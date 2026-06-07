"""Streamlit 前端：小说 → 剧本可视化转换工作台。

启动：streamlit run app.py
"""
from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

import streamlit as st
import yaml

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from backend.core.llm import LLMError, get_provider
from backend.core.pipeline import ConvertOptions, convert_novel, refine_scene
from backend.core.validator import auto_repair, validate_screenplay


# ---------------------------------------------------------------------------
# 全局配置
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Novel → Screenplay",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# 侧栏：元信息 + Provider 状态
# ---------------------------------------------------------------------------

def render_sidebar() -> dict:
    st.sidebar.header("📖 剧本元信息")
    title = st.sidebar.text_input("剧本标题", value=st.session_state.get("title", ""))
    source_novel = st.sidebar.text_input("原著小说名", value=st.session_state.get("source_novel", ""))
    source_author = st.sidebar.text_input("原著作者（可选）", value=st.session_state.get("source_author", ""))

    with st.sidebar.expander("更多元信息（可选）", expanded=False):
        genre = st.text_input("类型 genre", value="")
        logline = st.text_area("一句话 logline", value="", height=80)
        tone = st.text_input("基调 tone", value="")

    st.sidebar.markdown("---")
    st.sidebar.header("🔌 LLM 状态")
    has_qiniu = bool(os.getenv("QINIU_API_KEY"))
    has_ds = bool(os.getenv("DEEPSEEK_API_KEY"))
    default_idx = 0
    provider_options = []
    if has_qiniu:
        provider_options.append("qiniu (七牛云)")
    else:
        provider_options.append("qiniu (需配置 key)")
        default_idx = 2 if not has_ds else 1
    if has_ds:
        provider_options.append("deepseek")
    else:
        provider_options.append("deepseek (需配置 key)")
    provider_options.append("fake (离线 demo)")
    provider_name = st.sidebar.selectbox("Provider", options=provider_options, index=default_idx)
    real_provider = provider_name.split()[0]  # "qiniu" | "deepseek" | "fake"

    if real_provider == "qiniu":
        if has_qiniu:
            st.sidebar.success("七牛云 QINIU_API_KEY 已配置")
        else:
            st.sidebar.warning("未检测到 QINIU_API_KEY。请在 .env 中配置后重启。")
    elif real_provider == "deepseek":
        if has_ds:
            st.sidebar.success("DEEPSEEK_API_KEY 已配置")
        else:
            st.sidebar.warning("未检测到 DEEPSEEK_API_KEY。请在 .env 中配置后重启。")
    else:
        st.sidebar.info("Fake provider 仅返回占位 JSON，用于无 key 演示流程。")

    st.sidebar.markdown("---")
    st.sidebar.caption("七牛云 1024 创作大赛 · 题目三")
    st.sidebar.caption("[GitHub](https://github.com/Tanglaoye-future/novel2script)")

    return {
        "title": title,
        "source_novel": source_novel,
        "source_author": source_author or None,
        "genre": genre or None,
        "logline": logline or None,
        "tone": tone or None,
        "provider": real_provider,
    }


# ---------------------------------------------------------------------------
# 输入区
# ---------------------------------------------------------------------------

def render_input_section() -> str:
    st.subheader("① 输入小说原文")
    tab_paste, tab_upload, tab_examples = st.tabs(["✍️ 粘贴", "📁 上传 .txt", "📚 示例"])

    text = ""
    with tab_paste:
        text = st.text_area(
            "粘贴小说原文（建议 3 章以上）",
            value=st.session_state.get("novel_text", ""),
            height=320,
            key="novel_text_area",
            placeholder="第一章 …\n\n正文…\n\n第二章 …\n\n…",
        )
        if text:
            chapters_est = text.count("第")  # rough heuristic
            st.caption(
                f"已输入 {len(text):,} 字符"
                f"（估计 {max(1, chapters_est)} 章，约 {len(text) * 2 // 1000:,}k tokens）"
            )
            if len(text) > 100_000:
                st.warning("文本较长（>10 万字符），转换可能需要数分钟。建议先截取前 5 章测试。")

    with tab_upload:
        upload = st.file_uploader("上传 UTF-8 文本文件", type=["txt", "md"], key="upload_widget")
        if upload is not None:
            text = upload.read().decode("utf-8", errors="ignore")
            st.success(f"已读入 {len(text)} 字符")
            st.text_area("内容预览（只读）", value=text[:500] + ("..." if len(text) > 500 else ""),
                         height=180, disabled=True)

    with tab_examples:
        examples_dir = Path(__file__).parent / "examples" / "input"
        if examples_dir.exists():
            files = sorted(examples_dir.glob("*.txt"))
            if files:
                names = [f.name for f in files]
                pick = st.selectbox("选择内置示例", options=names)
                if st.button("载入示例", type="secondary"):
                    text = (examples_dir / pick).read_text(encoding="utf-8")
                    st.session_state.novel_text = text
                    st.rerun()
            else:
                st.info("examples/input/ 下暂无示例文件。")
        else:
            st.info("尚未生成内置示例。")

    return text


# ---------------------------------------------------------------------------
# 结果区
# ---------------------------------------------------------------------------

def render_validation(report: dict) -> None:
    if report["ok"]:
        st.success(f"✅ 校验通过（{len(report['warnings'])} 个提示）")
    else:
        st.error(f"❌ 校验未通过：{len(report['errors'])} 个错误")
        with st.expander("查看错误详情", expanded=True):
            for e in report["errors"]:
                st.code(e, language="text")
    if report["warnings"]:
        with st.expander(f"提示 ({len(report['warnings'])})", expanded=False):
            for w in report["warnings"]:
                st.caption(w)


def render_scenes(screenplay: dict) -> None:
    scenes = screenplay.get("scenes", [])
    if not scenes:
        st.info("暂无场景。")
        return

    char_map = {c["id"]: c["name"] for c in screenplay.get("characters", [])}
    loc_map = {l["id"]: l["name"] for l in screenplay.get("locations", [])}

    for scene in scenes:
        heading = scene.get("heading", {})
        loc_name = loc_map.get(heading.get("location_id"), "?")
        title = f"{scene.get('id')} · {heading.get('int_ext', '')}. {loc_name} - {heading.get('time_of_day', '')}"
        with st.expander(title, expanded=False):
            if scene.get("synopsis"):
                st.markdown(f"**梗概**：{scene['synopsis']}")
            cps = scene.get("characters_present") or []
            if cps:
                st.markdown("**在场角色**：" + "、".join(char_map.get(c, c) for c in cps))
            st.markdown("---")
            for beat in scene.get("beats", []):
                _render_beat(beat, char_map)
            if scene.get("source"):
                st.caption(f"📌 原著定位：第 {scene['source'].get('chapter_index')} 章 / 段落 {scene['source'].get('paragraph_range')}")
            _render_refine_widget(scene, screenplay)


def _render_refine_widget(scene: dict, screenplay: dict) -> None:
    """场景级 AI 重写按钮：差异化亮点。"""
    sid = scene["id"]
    with st.container():
        st.markdown("---")
        st.markdown("🪄 **AI 重写这场戏**")
        instruction = st.text_input(
            "重写方向（例如：让对白更克制 / 加强压迫感 / 把动作改少）",
            key=f"refine_input_{sid}",
            placeholder="按回车提交…",
        )
        cols = st.columns([1, 1, 6])
        with cols[0]:
            do_refine = st.button("✨ 重写", key=f"refine_btn_{sid}", type="secondary")
        with cols[1]:
            if st.session_state.get(f"refine_backup_{sid}"):
                if st.button("↩️ 撤销", key=f"undo_btn_{sid}"):
                    _undo_refine(sid)
                    st.rerun()

        if do_refine and instruction.strip():
            _run_refine(scene, instruction, screenplay)


def _run_refine(scene: dict, instruction: str, screenplay: dict) -> None:
    sid = scene["id"]
    provider_name = "qiniu" if os.getenv("QINIU_API_KEY") else ("deepseek" if os.getenv("DEEPSEEK_API_KEY") else "fake")
    try:
        provider = get_provider(provider_name)
    except LLMError as exc:
        st.error(f"LLM 初始化失败：{exc}")
        return

    try:
        with st.spinner(f"重写 {sid}…"):
            new_scene = refine_scene(scene, instruction, screenplay=screenplay, provider=provider)
    except (LLMError, ValueError) as exc:
        st.error(f"重写失败：{exc}")
        return

    # 备份原 scene 以便撤销
    st.session_state[f"refine_backup_{sid}"] = scene.copy()
    # 原地替换 screenplay 里的对应场景
    for i, s in enumerate(st.session_state.screenplay["scenes"]):
        if s["id"] == sid:
            st.session_state.screenplay["scenes"][i] = new_scene
            break
    # 重新跑校验
    report = validate_screenplay(st.session_state.screenplay)
    st.session_state.validation = {"ok": report.ok, "errors": report.errors, "warnings": report.warnings}
    st.success(f"{sid} 已重写。展开场景查看新版本。")
    st.rerun()


def _undo_refine(sid: str) -> None:
    backup = st.session_state.pop(f"refine_backup_{sid}", None)
    if backup is None:
        return
    for i, s in enumerate(st.session_state.screenplay["scenes"]):
        if s["id"] == sid:
            st.session_state.screenplay["scenes"][i] = backup
            break
    report = validate_screenplay(st.session_state.screenplay)
    st.session_state.validation = {"ok": report.ok, "errors": report.errors, "warnings": report.warnings}


def _render_beat(beat: dict, char_map: dict[str, str]) -> None:
    btype = beat.get("type")
    content = beat.get("content", "")
    subtext = beat.get("subtext")
    parenthetical = beat.get("parenthetical")

    if btype == "action":
        st.markdown(f"_{content}_")
    elif btype == "dialogue":
        who = char_map.get(beat.get("character_id"), beat.get("character_id", "?"))
        line = f"**{who}** "
        if parenthetical:
            line += f"_{parenthetical}_ "
        line += f": {content}"
        st.markdown(line)
        if subtext:
            st.caption(f"💭 潜台词：{subtext}")
    elif btype == "voiceover":
        who = char_map.get(beat.get("character_id"), beat.get("character_id", "?"))
        st.markdown(f"**{who}（V.O.）**：{content}")
        if subtext:
            st.caption(f"💭 潜台词：{subtext}")
    elif btype == "transition":
        st.markdown(f"`>>> {content}`")


def render_yaml_panel(screenplay: dict) -> None:
    yaml_str = yaml.safe_dump(screenplay, allow_unicode=True, sort_keys=False, width=120)
    st.code(yaml_str, language="yaml")
    st.download_button(
        "📥 下载 YAML",
        data=BytesIO(yaml_str.encode("utf-8")),
        file_name=f"{screenplay['meta']['title']}.yaml",
        mime="application/x-yaml",
    )


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main() -> None:
    st.title("🎬 Novel → Screenplay")
    st.caption("把小说一键转换为结构化 YAML 剧本，供作者快速获得可编辑、可打磨的初稿。")

    meta = render_sidebar()
    text = render_input_section()

    st.subheader("② 启动转换")
    col_a, col_b = st.columns([1, 4])
    with col_a:
        run = st.button("🚀 开始转换", type="primary", disabled=not (text and meta["title"] and meta["source_novel"]))
    with col_b:
        if not meta["title"] or not meta["source_novel"]:
            st.caption("请先在侧栏填写剧本标题与原著名")
        elif not text:
            st.caption("请先输入或上传小说文本")

    if run:
        _run_conversion(text, meta)

    if "screenplay" in st.session_state:
        st.subheader("③ 转换结果")
        render_validation(st.session_state.validation)
        # reset button
        cols_reset = st.columns([1, 8])
        with cols_reset[0]:
            if st.button("🗑️ 清除结果", type="secondary", key="reset_btn"):
                for k in ("screenplay", "validation", "novel_text"):
                    st.session_state.pop(k, None)
                st.rerun()
        tab_scenes, tab_yaml = st.tabs(["🎭 场景视图", "📄 YAML 源码"])
        with tab_scenes:
            render_scenes(st.session_state.screenplay)
        with tab_yaml:
            render_yaml_panel(st.session_state.screenplay)


def _run_conversion(text: str, meta: dict) -> None:
    try:
        provider = get_provider(meta["provider"])
    except LLMError as exc:
        st.error(f"LLM Provider 初始化失败：{exc}")
        return

    options = ConvertOptions(
        title=meta["title"],
        source_novel=meta["source_novel"],
        source_author=meta["source_author"],
        genre=meta["genre"],
        logline=meta["logline"],
        tone=meta["tone"],
    )

    progress_bar = st.progress(0.0, text="解析章节…")

    def on_progress(stage: str, cur: int, total: int) -> None:
        if total == 0:
            return
        if stage == "parsed_chapters":
            progress_bar.progress(0.05, text=f"解析完成，共 {total} 章")
        elif stage == "converting_chapter":
            progress_bar.progress(cur / total, text=f"正在转换第 {cur}/{total} 章…")

    try:
        with st.spinner("调用大模型中，单章可能需要 20-60 秒…"):
            screenplay = convert_novel(text, options, provider=provider, progress=on_progress)
    except (LLMError, ValueError) as exc:
        st.error(f"转换失败：{exc}")
        return

    screenplay = auto_repair(screenplay)
    report = validate_screenplay(screenplay)
    st.session_state.screenplay = screenplay
    st.session_state.validation = {
        "ok": report.ok,
        "errors": report.errors,
        "warnings": report.warnings,
    }
    progress_bar.progress(1.0, text=f"✅ 完成：{len(screenplay['scenes'])} 个场景")


if __name__ == "__main__":
    main()
