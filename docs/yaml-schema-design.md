# YAML 剧本 Schema 设计文档

> 适用版本：**v0.1** · 对应文件：[`schema/screenplay.schema.json`](../schema/screenplay.schema.json) · 样例：[`schema/example.yaml`](../schema/example.yaml)

本文档说明小说→剧本 YAML 输出的结构，以及**每一个关键字段为什么这样设计**。读者既包括 AI Pipeline 的实现者，也包括把 YAML 拿去手动打磨的剧本作者。

---

## 1. 总体设计目标

小说改编剧本的工作流，有四个一以贯之的痛点：

1. **结构性**——小说是流式文字，剧本是离散的"场景—节拍"。Schema 必须强制把流式叙述切成可操作的最小单元。
2. **可追溯**——AI 生成的剧本必须能"指回"原著对应位置，作者打磨时随时能对照原文。
3. **可编辑**——YAML 优于 JSON，是因为剧本作者要在文本编辑器里手工改字段。字段名、嵌套层级、字段顺序都按"人读优先"设计。
4. **可校验**——AI 输出会幻觉。Schema 必须能在反序列化阶段直接拒绝结构不合规的输出，而不是把垃圾喂给下游 UI。

围绕这四点，本 Schema 做出以下三个不太常规的设计决策（也是本作品差异化的关键），见 §3。

---

## 2. 整体结构

```
Screenplay
├── schema_version          # 字符串字面量 "0.1"
├── meta                    # 元信息（标题、原著、基调、生成时间…）
├── characters[]            # 角色表（含别名/原型/语言风格/弧光）
├── locations[]             # 地点表
├── scenes[]                # ★ 场景表（核心）
│   ├── id, heading, source, synopsis, characters_present, notes
│   └── beats[]             # ★★ 节拍序列（核心中的核心）
│       └── type, character_id, parenthetical, content, subtext
└── notes[]                 # 剧本级备注
```

为什么用这个层级，下面逐字段拆解。

---

## 3. 三个差异化设计决策

### 3.1 决策一：用 **"节拍序列"** 代替"对白脚本"

**做法**：每个场景的内容不是"一连串台词 + 偶尔穿插动作描写"，而是**一个 `beats[]` 数组**，每个 beat 有显式的 `type ∈ {action, dialogue, voiceover, transition}`。

**为什么不沿用 Fountain 等行业格式？**
Fountain 是纯文本格式，对人友好，但对程序不友好——动作行和对话块靠"前后空行 + 缩进"区分。AI 输出极易把动作误写成对白、把括号注误写成正文。把"节拍类型"显式建模为枚举，让 AI 必须做出明确选择，结构化失败可被 Schema 立即捕获。

**为什么不直接用 `dialogues[] + actions[]` 两条平行数组？**
平行数组无法表达**顺序**，而剧本节拍的顺序至关重要：动作→台词→反应动作→台词构成一个 beat 单元，互换顺序意义就变了。`beats[]` 数组以**顺序为一等公民**，每条节拍按播放时间排列。

**Schema 约束**：
- `beats` 至少 1 项（空场景没意义）
- 条件校验：当 `type ∈ {dialogue, voiceover}` 时，`character_id` 必填——避免出现"没人在说的台词"。

### 3.2 决策二：每条节拍带 **`subtext`（潜台词）字段**

**做法**：在 `beat` 上加一个可选字段 `subtext`，存储"角色没说出口的真实意图"。

**为什么这是 AI 真正能加价值的地方？**
小说作者改编自己作品时，最难写的不是台词本身，而是**让台词在剧本里有"潜台词"**：原著的心理独白没法搬到银幕，必须通过表演、潜台词、对照动作来传达。

让 AI 写出"明面台词 + 潜台词"的二元结构，等于让作者拿到一个**带导演注释的草稿**，可以直接：
- 据此修订台词，让明面话更"间接"，潜台词更"刺骨"
- 据此给演员留出表演空间（眼神、停顿、重音）
- 据此判断"这场戏到底有没有戏"——没有潜台词的对白通常是废戏

**为什么不放在场景级 notes 而要放在 beat 级？**
潜台词是**逐句**变化的：同一场景里 A 说话时的潜台词和 B 说话时的潜台词通常完全相反。只有放在 beat 级，AI 才会被迫给每句话单独想潜台词，而不是给整场敷衍一句。

### 3.3 决策三：每个场景带 **`source`（可追溯性）字段**

**做法**：每个 scene 都可以带一个 `source` 对象，记录该场景对应原著的 `chapter_index`、`chapter_title`、`paragraph_range`。

**为什么这是改编工具的必备字段？**
作者打磨剧本时的实际工作流是："看这场戏改得不对——原著到底怎么写的？" 没有 source 字段时，作者要在 PDF 里搜关键词；有了 source，前端可以一键定位到原著章节甚至具体段落。这是把"AI 生成"和"作者打磨"真正连接起来的关键。

**为什么是段落区间 `[start, end]` 而不是单段索引？**
小说一段话经常拆成多个剧本场景，剧本一场戏也可能跨多个小说段落（尤其当原文是连续叙述时）。区间能两边都覆盖。

---

## 4. 字段级说明

### 4.1 `meta`

| 字段 | 必填 | 说明 |
|---|---|---|
| `title` | ✅ | 剧本标题。允许与原著不同（改编后通常会改） |
| `source_novel` | ✅ | 原著名，强制留下"出处" |
| `source_author` | | 原著作者，用于版权署名 |
| `genre` | | 类型；AI 据此决定改编基调 |
| `logline` | | 一句话故事核心。建议长度 ≤ 30 字 |
| `tone` | | 整体基调（阴郁/讽刺/温暖…）；用于场景重写时的风格约束 |
| `language` | | 默认 `zh-CN`，预留多语言扩展 |
| `generated_at` | | ISO 8601 时间戳，便于追踪是哪次生成 |

**设计取舍**：`logline` 和 `tone` 是"软"字段，AI 可以猜不准，但**让 AI 必须给出**会强迫它做整体性判断，从而提升场景级输出的一致性。

### 4.2 `characters[]`

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✅ | 形如 `c01`、`c02`，被全文档其他位置引用 |
| `name` | ✅ | 本名/最正式称谓 |
| `aliases[]` | | 别名/绰号，用于跨章节合并指代（"狂人"=主角=`c01`） |
| `role` | | `protagonist`/`antagonist`/`supporting`/`minor` |
| `archetype` | | 原型（觉醒者、守门人、导师…），用于场景重写时维持人物一致 |
| `description` | | 外形/性格简介 |
| `voice_traits` | | **语言风格特征**——AI 重写时的关键约束 |
| `arc` | | 一句话角色弧光 |

**为什么强制 id？**
原著里同一个角色可能有 5 种称谓（本名、字号、官职、绰号、代词）。如果 beats 里直接用名字字符串，AI 容易把同一人写成两个角色。强制 id + aliases 把"名字归一化"问题前置解决。

**为什么有 `voice_traits` 字段？**
场景重写（PR11）是本作品的核心交互之一。让 AI 重写时如果不告诉它"这个角色平时说话短促、爱用反问"，它会重写成一个无差别的"中性 AI 语调"。`voice_traits` 是给 AI 的硬约束。

### 4.3 `locations[]`

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✅ | 形如 `l01`，被 `scenes[].heading.location_id` 引用 |
| `name` | ✅ | 地点名 |
| `description` | | 物理环境/氛围 |

**为什么单独建表，而不是把地点字符串内联在 heading 里？**
地点会跨场景复用。单独建表 + id 引用让"卧房"这个地点的描述只写一次。前端也能据此把同一地点的所有场景聚合呈现。

### 4.4 `scenes[]`

每个场景对象的字段：

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✅ | `S001`、`S002`，零填充 3-4 位，便于排序 |
| `heading` | ✅ | 场景头，对应剧本格式 `INT./EXT. 地点 - 时间` |
| `source` | | **可追溯性**：对应原著的 chapter + paragraph 区间 |
| `synopsis` | | 一句话场景梗概 |
| `characters_present[]` | | 在场角色 id 列表 |
| `beats[]` | ✅ | **核心**：节拍序列 |
| `notes[]` | | 场景级备注 |

#### `heading` 子结构

```yaml
heading:
  int_ext: INT          # 枚举：INT / EXT / INT/EXT
  location_id: l01      # 引用 locations[].id
  time_of_day: NIGHT    # 枚举：DAWN/MORNING/DAY/AFTERNOON/EVENING/NIGHT/LATER/CONTINUOUS
```

**为什么 `time_of_day` 用枚举而不是自由字符串？**
行业剧本格式只承认有限的时间标记。枚举杜绝 AI 写出"傍晚六点半"这种破坏行业可读性的输出。`LATER`/`CONTINUOUS` 是承接上一场用的特殊标记，需要保留。

### 4.5 `beats[]` —— Schema 的灵魂

每个 beat：

```yaml
- type: dialogue         # 枚举：action / dialogue / voiceover / transition
  character_id: c01      # dialogue/voiceover 必填
  parenthetical: (低声)   # 表演提示
  content: 这个月夜……    # 正文：动作描写或台词
  subtext: 他终于醒了    # ★ 潜台词
```

| `type` | `character_id` | 典型 `content` | 用途 |
|---|---|---|---|
| `action` | 一般 null | "主角推门而出，廊下三五人立刻噤声" | 动作描写 / 环境变化 |
| `dialogue` | **必填** | "你想吃我，还想叫别人也帮着吃我。" | 出场角色的台词 |
| `voiceover` | **必填** | "今天晚上，很好的月光。" | 画外音 / 内心独白外放 |
| `transition` | null | "渐隐至黑。" | 转场 |

**为什么把 `parenthetical` 和 `subtext` 分开？**
- `parenthetical` 是**给演员看的**，需要写进最终剧本（如"(冷笑)"）
- `subtext` 是**给作者/导演看的**，最终拍摄时不会出现在台词页上

两者性质不同。混在一起会让 AI 不知道该写哪种，最终两个都写糟。

---

## 5. 校验策略

校验在两层执行：

1. **JSON Schema 层**（`backend/core/validator.py`，PR8 落地）
   - 类型、必填、枚举、正则、conditional required
   - 任何 AI 输出过不了这一关都直接拒绝重试
2. **业务一致性层**（PR8 同步落地，纯 Python）
   - `beats[].character_id` 必须出现在 `characters[]` 中
   - `scenes[].heading.location_id` 必须出现在 `locations[]` 中
   - `scenes[].characters_present` 必须是 `characters[]` 的子集

第二层不放进 JSON Schema 是因为跨字段引用约束写在 JSON Schema 里非常难读，留作 Python 后处理。

---

## 6. 演进策略

`schema_version` 字段固定为字符串字面量。下一版（v0.2）计划新增字段，预留路径：

- `scenes[].tags[]` —— 用户自由打标签（"高潮"、"插叙"…）
- `scenes[].emotional_beat` —— 整场戏的情感节拍（铺垫/转折/释放…）
- `characters[].relationships[]` —— 人物关系图，用于跨章节一致性检查
- 顶层 `acts[]` —— 三幕/五幕结构标注，便于结构分析

向后兼容原则：**v0.x 之间只加字段不删字段**，旧 YAML 始终可被新版本读入。

---

## 7. 与行业格式的关系

本 Schema 不是为了替代 Fountain / Final Draft，而是为了做**中间表示（IR）**：

```
小说 ──(AI Pipeline)──▶ YAML (本 Schema) ──┬──▶ Fountain (.fountain)
                                          ├──▶ Final Draft (.fdx)
                                          └──▶ PDF / DOCX 标准剧本格式
```

YAML 作为 IR 的优势：可被程序/AI 反复读写、可被作者用任何文本编辑器编辑、可纳入版本控制。导出到行业格式时再用 PR12 之后的 exporter 转换。

---

## 附：最小合法 YAML 示例

```yaml
schema_version: "0.1"
meta:
  title: 月光
  source_novel: 狂人日记
characters:
  - id: c01
    name: 我
locations:
  - id: l01
    name: 卧房
scenes:
  - id: S001
    heading: { int_ext: INT, location_id: l01, time_of_day: NIGHT }
    beats:
      - type: action
        content: 月光透窗而入。
      - type: voiceover
        character_id: c01
        content: 今天晚上，很好的月光。
        subtext: 三十年来第一次"清醒"。
```

完整示例见 [`schema/example.yaml`](../schema/example.yaml)。
