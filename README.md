# 小说转剧本 AI 工具 (Novel → Screenplay)

将 3 章以上的小说文本一键转换为结构化 YAML 剧本，供作者快速获得可编辑、可打磨的剧本初稿。

> **七牛云 1024 创作大赛 · 题目三** 参赛作品  
> 仓库：[GitHub](https://github.com/Tanglaoye-future/novel2script)  
> Demo：[Bilibili](https://www.bilibili.com/video/BV14BEb6yE2p/)

---

## ✨ 功能

| 功能 | 说明 |
|---|---|
| 📖 自动识别章节 | 正则 + 启发式，支持中文/英文/特殊章节名 |
| 🎬 章节 → 场景 | **七牛云 AI (Qwen3-235B)** 将小说逐章转换为结构化剧本 |
| 🎭 节拍序列 (beats) | action / dialogue / voiceover / transition 四类，含潜台词字段 |
| 📋 YAML + JSON Schema | 严格校验输出结构，非法输出自动拒绝 |
| 🔁 场景级 AI 重写 | 单场景一键润色，配撤销。不改别的场景 |
| 🪄 潜台词生成 | 每句对白带 subtext 字段——改编最难手写的部分 |
| 📌 可追溯 | 每个场景标注原著作/段落，作者可跳回原文打磨 |
| 📥 一键下载 | YAML 文件导出 |

---

## 🎥 Demo 视频

[![Demo 视频](https://img.shields.io/badge/Bilibili-演示视频-00A1D6?logo=bilibili)](https://www.bilibili.com/video/BV14BEb6yE2p/)

> 完整演示：小说输入 → 章节解析 → AI 转换 → 场景卡片浏览 → 场景级重写 → YAML 下载。

---

## 🚀 快速开始

```bash
# 1. 克隆 + 安装
git clone https://github.com/Tanglaoye-future/novel2script.git
cd novel2script
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. 配置 API key（七牛云 AI 推理服务，默认）
cp .env.example .env
# 编辑 .env，填入 QINIU_API_KEY=sk-...
# 注册入口：https://developer.qiniu.com/aitokenapi

# 3. 启动（三选一）
# 方式 A：Streamlit 交互 UI（推荐）
streamlit run app.py

# 方式 B：CLI 批量转换
novel2script convert examples/input/the_lighthouse_keeper.txt \
  -o output.yaml --title "守灯人" --source-novel "守灯人"

# 方式 C：HTTP API + 前端查看
uvicorn backend.api.main:app --reload --port 8000
# 然后访问 http://localhost:8000/docs
```

### 无 Key 也能看

在 Streamlit 侧栏 Provider 菜单里选「fake (离线 demo)」，不配 API key 也能跑完完整流程——用占位 JSON 演示 UI 交互、场景卡片、下载功能。

---

## 🏗️ 系统架构

参见 [docs/architecture.md](docs/architecture.md)（含数据流图、模块职责、关键设计决策）。

核心链路：

```
小说文本 → chapter_parser → Chapter[] → Pipeline(逐章LLM) → 合并 → validator → YAML
```

详见 [docs/yaml-schema-design.md](docs/yaml-schema-design.md) 了解 Schema 的字段定义和三个差异化设计决策（节拍序列、潜台词字段、可追溯性）。

---

## 🧪 测试

```bash
# 运行全部测试（无需 API key —— 用 FakeProvider）
.venv/bin/python -m pytest

# 只跑 Schema 层
.venv/bin/python -m pytest backend/tests/test_schema.py -v

# 只跑 Pipeline（端到端模拟）
.venv/bin/python -m pytest backend/tests/test_pipeline.py -v
```

45 个测试，覆盖：
- Schema 结构与反例
- 章节解析（中文/英文/特殊章节/空输入/长文界误判）
- LLM Provider 工厂 + FakeProvider 回放
- Pipeline 三章端到端（多章 id 合并、scene 重编号、source 回填）
- Validator 两层校验 + auto_repair
- /convert + /refine HTTP 端点 + 422/404 边界
- 场景级 refine（id/source 保留、voice_traits 注入、撤销）

---

## 📦 依赖

本项目使用了以下第三方库（均通过 pip 公开渠道安装，遵循各自开源协议）：

| 库 | 用途 | 协议 |
|---|---|---|
| streamlit | 前端 UI | Apache-2.0 |
| fastapi + uvicorn | HTTP API | MIT |
| pydantic | 数据模型/校验 | MIT |
| pyyaml | YAML 序列化 | MIT |
| jsonschema | JSON Schema 校验 | MIT |
| openai | 七牛云 AI / DeepSeek API 调用（OpenAI 兼容协议） | Apache-2.0 |
| python-dotenv | 环境变量加载 | BSD |
| pytest | 测试框架（dev 依赖） | MIT |

**原创部分**：YAML Schema 设计（`schema/screenplay.schema.json`）、章节解析逻辑（`backend/core/chapter_parser.py`）、转换 Pipeline（`backend/core/pipeline.py`）、Prompt 工程（`backend/core/prompts.py`）、Validator + auto_repair（`backend/core/validator.py`）、Streamlit 交互层（`app.py`）、LLM Provider 抽象适配层（`backend/core/llm/`）均为本项目原创实现。

---

## 📁 项目结构

```
.
├── app.py                        # Streamlit UI 工作台
├── backend/
│   ├── cli.py                    # CLI 入口 (novel2script convert ...)
│   ├── api/
│   │   ├── main.py               # FastAPI 入口
│   │   └── convert.py            # POST /convert + POST /refine
│   ├── core/
│   │   ├── chapter_parser.py     # 章节切分
│   │   ├── pipeline.py           # 核心转换流程
│   │   ├── prompts.py            # LLM Prompt 模板集
│   │   ├── validator.py          # 两层校验 + auto_repair
│   │   └── llm/                  # Provider 适配层
│   │       ├── base.py           #   抽象接口
│   │       ├── deepseek.py       #   DeepSeek (备用)
│   │       ├── qiniu.py          #   七牛云 AI (默认)
│   │       └── fake.py           #   离线占位
│   └── tests/                    # 45 条自动测试
├── schema/
│   ├── screenplay.schema.json    # JSON Schema v0.1
│   └── example.yaml              # 手工撰写参照示例
├── examples/
│   ├── input/                    # 原创 CC0 小说原文
│   ├── output/                   # 参照 + AI 生成产物
│   └── README.md                 # 版权声明
├── docs/
│   ├── yaml-schema-design.md     # Schema 设计文档（题目硬要求）
│   └── architecture.md           # 系统架构文档
└── pyproject.toml                # 项目元信息 + 依赖
```

---

## 📜 License

MIT © 2026 Frank Tang

本工具输出的 YAML 剧本版权归输出该 YAML 的用户所有。工具自身不含任何预置的受版权保护的小说文本（`examples/input/the_lighthouse_keeper.txt` 为 CC0 原创短篇）。
