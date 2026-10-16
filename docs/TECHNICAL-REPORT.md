# agent-rework-lens 技术报告（M5 定稿）

> 本文回答"这套工具为什么这样设计、判定为什么可信、数据为什么安全"。口径与代码单点对齐：阈值见 [`src/agent_rework_lens/config.py`](../src/agent_rework_lens/config.py)，判定语义见 `plan/04-模块详设.md`，决策全表见 `plan/07-交付对标与决策记录.md`。

## 1. 问题与交付形态

AI 编码 agent 有两类高频低效行为：**返工**（同一文件被反复改回）与**重复造轮子**（新写项目里已有的工具函数）。聊天记录无法度量它们——只有本机留存的**版本快照链**与**工具事件日志**能给出结构性事实。

agent-rework-lens 只读扫描本机 Claude Code / Codex 会话日志，输出：

1. **返工判定**（三态：`rework` / `not_rework` / `insufficient_data`）+ 证据锚点；
2. **重复候选**（新写符号 × 项目已有符号的粗匹配，披露制候选信号，非判决）；
3. **Read:Edit 比**（读了多少才动笔）。

交付形态：`arl scan` 人读摘要 + `--report-md` / `--report-html` 落盘报告 + `arl bench` 合成基准评测。

## 2. 数据流与 schema

```text
发现(discovery) → 解析(parsers → SessionIR) → 引擎(engine: rework/metrics/symbols)
      → 编排(pipeline: run_scan → ScanOutcome → build_report_model)
      → 渲染(report: markdown/html) / 对账(benchmark: runner)
```

**SessionIR（唯一契约，K3）**：解析层把两种来源的日志统一成不可变中间表示——`SessionMeta`（source/session_id/cwd/…）+ `ToolUseEvent`（seq/kind/tool_name/file_path/timestamp）+ `TokenUsageEvent` + `ParseNote`。设计取舍：

- frozen dataclass + tuple：天然不可变、可比较、确定性输出（同输入双跑逐字节一致，有测试锁定）；
- **未核对字段不进入计算路径**（K7）：解析器遇到字段形态没核对过的输入 → 跳过并计 `ParseNote`，显式可见，不静默、不猜测。例：MultiEdit 本机 0 次出现 → 出现即按"多段 Edit 序列"降级记 note（D-M1-4）；
- 事件序号 `seq` = 源文件行号（1 起），是全部证据锚点的一半。

**ScanOutcome（编排产出）**：discovery + 逐会话 IR + 版本链 + 返工 findings + 会话指标（含符号候选）+ 报告注记。**ReportModel（渲染输入）**：meta（含 config 运行时阈值口径）+ findings + 候选 + 指标 + notes——渲染器只搬运数据。

## 3. 判定口径（为什么可信）

### 3.1 返工三态（K4：版本链只实读不反推）

| 判定 | 条件 |
|---|---|
| `rework` | 同一文件版本快照 ≥ `REWORK_MIN_VERSIONS`，或单会话 Edit ≥ `REWORK_MIN_EDITS`（阈值 config.py 单点） |
| `insufficient_data` | 两条不成立且**有 Edit 而版本链缺失**（备份应存在而找不到——不猜测，不反推） |
| `not_rework` | 两条不成立且链存在；纯 Write 新建（首写不备份，无链属正常） |

版本数证据：`file-history` 目录实读链 + 会话快照 `backupFileName` 关联，按 hash stem 对齐，以目录现存为准（快照记录版本可高于目录现存 → 不取大）。Codex 源无 file-history（实测字段形态）→ 版本数恒缺失，以 apply_patch 写事件计数为主，**不判 insufficient_data**（不编造字段）。

### 3.2 粗匹配（披露制，K5）

归一化 5 步（转小写 / `-`→`_` / 去首尾 `_` / 剔除前后缀 token / 拼接）后两级匹配：精确相等 → `normalized_exact`；否则 `difflib` ratio ≥ `DUP_MATCH_THRESHOLD` → `high_similarity`。**任何候选输出必伴随披露文本"粗匹配 ≠ 确认重复"**——单点定义在 engine/metrics，报告/CLI 只引用同一常量，测试锁死。

新写符号来自会话 Write 载荷的 `def`/`class` 正则提取（首期仅 Python，其他语言**显式披露不支持**，不猜测）；已有符号来自 Read 过且磁盘存在的 `.py` 文件。Codex 源的 apply_patch 载荷无独立 `file_path+content` 双字段形态 → 符号候选未启用并显式披露（不编造，R5/D-M1-4 口径）。

### 3.3 证据锚点（可证伪）

每条返工判定携带 `(源文件:行号)` 锚点 + 版本快照文件名（`<hash>@vN`）；重复候选携带 `源文件:会话id`。`arl bench` 要求锚点可溯源率 100%（12 样例 26/26），锚点错了基准就红——结论不靠模型信用，靠可点开的行号。

## 4. 确定性纪律（K11）与可证伪基准

- **零时钟零随机**：解析、判定、渲染全链路不读时钟不读环境；时间跨度由事件时间戳算出，缺失显式 `None`；
- **渲染纯函数**（K6）：只渲染模型数据；HTML 零外链（内联样式，无 script/http 引用，测试断言）；同一模型两次渲染逐字节一致；空节显示"无数据"，不显示"一切正常"这类假结论；
- **合成基准**：12 个 truth 驱动样例（返工/不返工/链缺失/近失/阈值边界/重复符号两级匹配），`gen_synthetic.py --check` 生成器位级复验 + sha256 对账；覆盖率门槛数值只来自 `manifest.json`（代码零第二份数值）；
- **探活三层级**（D-M4-3）：引擎注入置空 → 基准逐样例红；阈值变异 → 相应样例塌；fixtures 篡改 → sha256 拦截。基准本体可被证伪，"全绿"才有信息量。

## 5. 隐私设计（红线）

- **纯本地**：无网络请求、无遥测；HTML 报告零外链可离线打开；
- **只读**：不修改代码、不修改日志；演示与基准一律合成日志（假路径/假项目名），真实日志绝不入仓；
- 变异/演示一律在 `shutil.copytree` 副本上做（K9），冻结 fixtures 禁手改。

## 6. 已知边界（诚实口径）

- 符号提取首期仅 Python（`def`/`class`）；其他语言显式未支持并披露；
- MultiEdit 字段形态本机未见实测（D-M1-4 降级处理，出现时记 ParseNote）；
- 粗匹配为候选信号（归一化 + 序列相似度），**不是**克隆检测/AST 级分析；
- 检测率/误报率基于 12 case 合成基准，样本规模有限；门槛与对账口径见 README"指标口径"节；
- 覆盖率/确定性承诺只覆盖所核对的日志字段形态（data/README.md §2.6 R1–R6）。
