# 系统架构

> **Novel2Script** · 小说 → 结构化 YAML 剧本转换工具

---

## 整体数据流

```
┌──────────────────────────────────────────────────────────────────┐
│                         Streamlit UI (app.py)                     │
│                                                                   │
│  ① 粘贴/上传小说    ② 填剧本元信息    ③ 点击「开始转换」          │
│             │                │                  │                 │
│             ▼                ▼                  ▼                 │
│  ┌──────────────────── ConvertOptions ──────────────────────┐    │
│  │  title / source_novel / genre / logline / tone           │    │
│  └──────────────────────────────────────────────────────────┘    │
│                              │                                    │
│                     convert_novel(text, options)                  │
│                              │                                    │
└──────────────────────────────┼────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    backend/core/pipeline.py                       │
│                                                                   │
│  ┌─────────────┐     ┌──────────────────────┐                    │
│  │ ① 章节切分    │────▶│ ② 逐章 LLM 调用       │                    │
│  │ chapter_parser│     │   每章: {new_chars,    │                    │
│  │ → Chapter[]  │     │    new_locs, scenes}   │                    │
│  └─────────────┘     └──────────┬───────────┘                    │
│                                 │                                 │
│                  ┌──────────────▼──────────────┐                  │
│                  │ ③ 跨章合并 (merge_by_id)      │                  │
│                  │  scene id 全局重排            │                  │
│                  │  source 字段缺失兜底回填      │                  │
│                  └──────────────┬──────────────┘                  │
│                                 │                                 │
│                  ┌──────────────▼──────────────┐                  │
│                  │ ④ 输出 dict → ⑤ → ⑥         │                  │
│                  └─────────────────────────────┘                  │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                   backend/core/validator.py                       │
│                                                                   │
│  ⑤ auto_repair:  补齐 characters_present / schema_version         │
│  ⑥ validate:     JSON Schema 层 + 跨字段引用一致性层              │
│                   → ValidationReport {ok, errors, warnings}       │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                        Streamlit UI (结果展示)                     │
│                                                                   │
│  ⑦ 🎭 场景卡片:    按 beat.type 渲染，潜台词灰字标注               │
│  ⑧ 📄 YAML 源码:  高亮 + 一键下载                                 │
│  ⑨ 🪄 场景重写:    单 scene → LLM refine → 覆盖 → 可撤销          │
└──────────────────────────────────────────────────────────────────┘
```

## 模块职责

### `backend/core/chapter_parser.py`

- **输入**：原始文本字符串
- **输出**：`Chapter[]`（index、title、paragraphs、body、char_count）
- **算法**：行首启发式正则（4 类中文/英文章节标题模式）
- **容错**：检测不到标题时整本作为 1 章返回；标题前有文字时归为"卷首"
- **测试覆盖率**：9 条用例

### `backend/core/llm/`

```
base.py        LLMProvider (ABC)   + LLMResponse / LLMUsage 数据类
deepseek.py    DeepSeekProvider    OpenAI 兼容 SDK + JSON 模式
fake.py        FakeProvider        预编程响应，供 CI / 无 key 演示
__init__.py    get_provider()      工厂，按环境变量 LLM_PROVIDER 路由
```

- **设计决策**：不直接依赖 deepseek 特定 SDK，而是复用 OpenAI 兼容协议。未来加 Kimi/通义只需复制 80 行模版代码 + 改 base_url
- **重试**：1.5^n 秒指数退避，默认 2 次（总超时 ~120s），兼容 429 / 偶发网络抖动

### `backend/core/prompt.py`

- `CHAPTER_TO_SCENES_SYSTEM`：详细 system prompt，约束拆场景、beat type、subtext、id 策略
- `build_chapter_user_prompt()`：把 existing_characters/locations 打包进上下文
- `SCENE_REFINE_SYSTEM` / `build_refine_user_prompt()`：场景级重写 prompt（注入角色 voice_traits）

### `backend/core/pipeline.py`

- `convert_novel()`：主流程入口，串联 chapter_parser → 逐章 LLM → 合并 → validator
- `refine_scene()`：单场景原地重写，保留 id/source，注入角色 voice_traits 约束
- `ConvertOptions`：从 Streamlit / CLI / API 三种调用方式中都复用同一个参数 dataclass

### `backend/core/validator.py`

- **两层校验**：JSON Schema（结构/类型）+ Python 业务一致性（跨字段引用）

### `backend/api/`

- `main.py`：FastAPI 入口，CORS 全开
- `convert.py`：`POST /convert` + `POST /refine` 两个端点

### `app.py`

- 单文件 Streamlit 工作台，不拆文件是因为 Streamlit 本身就是脚本式渲染，拆模块带来的复杂度大于复用收益

## 三条调用路径

| 入口 | 适用场景 | 命令 |
|---|---|---|
| Streamlit | 交互式使用、demo 演示 | `streamlit run app.py` |
| HTTP API | 集成到其他工具 | `POST /convert` |
| CLI | 批量转换、CI | `novel2script convert in.txt -o out.yaml` |

三条路径穿同一套 `convert_novel()`核心，所有 LLM 调用、Prompt、校验逻辑完全共享。

## 关键设计决策

1. **YAML 作为中间表示（IR）而非终点**：输出是机器可读 + 人可编辑的 dict，后续可导出为 Fountain / PDF / DOCX。详见 `docs/yaml-schema-design.md`
2. **章节级并行不安全，主动未做**：LLM 跨章生成角色 id 时会冲突。逐章串行 + existing_* 上下文注入是当前最可靠的策略
3. **FakeProvider 不是测试桩，是演示功能**：在没有 API key 的环境（评委首次打开 repo），用户点「开始转换」不会崩——拿一组占位 JSON 走完全流程，先看到 UI 长什么样
4. **Streamlit 而非 React**：1.5 天开发窗口，Streamlit 把 UI 开发时间从 8h 压缩到 2h，释放的时间用在 Schema 设计质量和 Prompt 迭代上
