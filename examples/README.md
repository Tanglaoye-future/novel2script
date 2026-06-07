# examples/

本目录存放用于演示与回归测试的小说输入与剧本输出。

## input/

| 文件 | 来源 | 章节数 | 字数 | 说明 |
|---|---|---|---|---|
| `the_lighthouse_keeper.txt` | 本项目原创，CC0 公共领域 | 3 | ≈1500 | 演示主用例。手写以规避公版小说版本差异 |

> ⚠️ 不要往这里放有版权的小说。如需测试大型公版小说（鲁迅、契诃夫、古典小说），请自行下载文本后扔到本目录，再用 `novel2script convert` 转换。

## output/

| 文件 | 输入 | 生成方式 | 说明 |
|---|---|---|---|
| `kuangrenriji_handcrafted.yaml` | 《狂人日记》前 3 章 | 手工撰写 | Schema 字段全覆盖的样例，亦是 `schema/example.yaml` 的副本，用于演示**目标输出形态** |
| `the_lighthouse_keeper.yaml` | `input/the_lighthouse_keeper.txt` | DeepSeek 实跑 (2026-06-07) | 真实 AI 生成产物，4 章→6 场景，0 error 0 warning |

## 重新生成 output

```bash
# 配置 .env 里的 DEEPSEEK_API_KEY 后
.venv/bin/novel2script convert examples/input/the_lighthouse_keeper.txt \
    -o examples/output/the_lighthouse_keeper.yaml \
    --title "守灯人" \
    --source-novel "守灯人" \
    --source-author "Novel2Script 演示原创" \
    --genre "情感剧情" \
    --tone "克制 / 沉静 / 暖意"
```
