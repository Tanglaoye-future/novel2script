# 小说转剧本 AI 工具 (Novel → Screenplay)

将 3 章以上的小说文本一键转换为结构化 YAML 剧本，供作者快速获得可编辑、可打磨的剧本初稿。

> 七牛云 1024 创作大赛 · 题目三 参赛作品

## ✨ 功能

- 📖 自动识别小说章节
- 🎬 章节 → 场景（含场景头、动作、对白、潜台词）
- 📋 结构化 YAML 输出（严格通过 JSON Schema 校验）
- 🔁 场景级 AI 重写润色
- 📥 一键下载 YAML / 复制到剪贴板

## 🎥 Demo 视频

> 视频链接：_待录制后补充_

## 🏗️ 架构概览

```
┌──────────────┐   小说文本    ┌──────────────────┐
│  Streamlit   │ ───────────▶ │  FastAPI Core    │
│   UI (app.py)│              │                  │
└──────────────┘              │  ┌────────────┐  │
       ▲                      │  │ Chapter    │  │
       │   YAML 剧本           │  │ Parser     │  │
       └──────────────────────│  └─────┬──────┘  │
                              │        ▼          │
                              │  ┌────────────┐  │
                              │  │ Pipeline   │──┼──▶ DeepSeek
                              │  └─────┬──────┘  │     LLM
                              │        ▼          │
                              │  ┌────────────┐  │
                              │  │ Schema     │  │
                              │  │ Validator  │  │
                              │  └────────────┘  │
                              └──────────────────┘
```

详见 [docs/architecture.md](docs/architecture.md) 与 [docs/yaml-schema-design.md](docs/yaml-schema-design.md)。

## 🚀 快速开始

```bash
# 1. 安装依赖
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# 2. 配置 API key
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 3. 启动 Streamlit UI
streamlit run app.py

# 或使用 CLI
python -m backend.cli convert examples/input/kuangrenriji.txt -o output.yaml
```

## 📦 依赖说明

本项目使用了以下第三方库（均通过 pip 公开渠道安装，遵循各自开源协议）：

| 库 | 用途 | 协议 |
|---|---|---|
| streamlit | 前端 UI | Apache-2.0 |
| fastapi | 后端 API | MIT |
| pydantic | 数据校验 | MIT |
| pyyaml | YAML 序列化 | MIT |
| jsonschema | Schema 校验 | MIT |
| openai | DeepSeek API 调用（OpenAI 兼容） | Apache-2.0 |
| python-dotenv | 环境变量加载 | BSD |

**原创部分**：YAML Schema 设计、章节解析逻辑、转换 Pipeline、Prompt 工程、Streamlit 交互层均为本项目原创实现。

## 📁 目录结构

```
.
├── app.py                  # Streamlit UI 入口
├── backend/
│   ├── core/               # 核心转换逻辑
│   │   ├── chapter_parser.py
│   │   ├── pipeline.py
│   │   ├── models.py
│   │   ├── validator.py
│   │   └── llm/            # LLM Provider 适配层
│   ├── api/                # FastAPI 路由
│   └── tests/
├── schema/
│   ├── screenplay.schema.json
│   └── example.yaml
├── examples/
│   ├── input/              # 公版小说原文
│   └── output/             # 生成的 YAML 剧本
└── docs/
    ├── yaml-schema-design.md
    └── architecture.md
```

## 📜 License

MIT
