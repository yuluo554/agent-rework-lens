# agent-rework-lens

> **AI 代码"重复造轮子 + 返工"体检器** —— 扫描本机 Claude Code / Codex 会话日志，回答：**这次会话里 agent 有几成 Edit/Write 是在重写项目里已存在的工具函数？哪些文件被反复改回（返工）？** 纯本地、零模型、零上传。

**状态**：✅ 功能完整（M5）——`version` / `sources` / `selftest` / `scan`（引擎判定 + 报告落盘）/ `bench`（合成基准）全部可用；技术报告见 [docs/TECHNICAL-REPORT.md](docs/TECHNICAL-REPORT.md)。路线图见 [plan/06-里程碑.md](plan/06-里程碑.md)。

## 它回答什么

1. **返工**：哪些文件在会话中被反复改回？（版本快照链 v1→v2→v3 / 同一文件多次 Edit）
2. **重复造轮子**：会话内新写的符号里，有多少与项目已有 util/符号**粗匹配**？（候选信号，**非判决**）
3. **Read:Edit 比**：这次会话读了多少才动笔写？

全部指标为**确定性计数与结构性事实**（版本链、Edit 次数、Read:Edit 比、符号名粗匹配）——没有 LLM、没有 AI 评分、没有网络请求。这两块数据（本机版本快照链 + 持久测量基线）是 LLM 聊天拿不到的。

## 隐私声明（红线）

- **纯本地**：不发送任何数据、无遥测、无网络请求；
- **只读**：不修改你的代码，不修改你的日志；
- 真实会话日志含代码与 prompt —— 本仓库的演示与基准一律使用**合成会话日志**（假项目名 / 假路径），**真实日志绝不入仓**。

## 快速开始

```bash
git clone <repo-url> && cd agent-rework-lens
python -m venv .venv
# Windows (Git Bash):  . .venv/Scripts/activate
# Linux / macOS:       source .venv/bin/activate
python -m pip install -e ".[dev]"      # 与 CI 使用同一 extras 集合
arl sources                            # 列出本机发现的日志源与文件数
arl selftest                           # 内置自检
```

`python -m agent_rework_lens` 与 `arl` 等价（两条通路均受支持）。

## 退出码

| 码 | 含义 |
|---|---|
| 0 | 成功（含 `bench` 达标） |
| 1 | 内部错误（未预期异常）；`bench` 未达标/未启用（明确清单，**不冒充通过**） |
| 2 | 用法错误 / 未知命令 |
| 3 | 未发现可分析日志（明确提示，不伪造空报告） |

> 编号 4（阶段未就绪）已于 M2 按 K2 流程退役（D-M2-1），不再使用、不复用。

## 基准（`arl bench`）

```bash
arl bench                 # 合成基准：11 个样例逐例与 truth.json 对账
arl bench --json          # 机读输出（确定性 sort_keys）
arl bench --data-dir <目录>
```

- 数据：`data/synthetic/`（M1 冻结 fixtures，`tools/gen_synthetic.py --check` 位级复验）；**门槛数值只来自 `manifest.json`**，代码与文档零数值；
- 达标 = 覆盖率门槛满足 + 全部样例 verdict/edit_count/版本链/符号候选与 truth 一致 + 证据锚点 100% 可溯源 + 冻结件 sha256 对账通过；
- 未启用（数据目录缺失）与未达标（任一对账失败）均退出码 1，附明确清单——**空分母不冒充满分**；
- 可证伪探活：注入缺陷（返工判定强行置空）→ 基准必须报未达标（实录见 plan/06 M4 节）。

## 演示（`arl scan` + 报告落盘）

```bash
# 扫描本机会话（Claude + Codex 自动发现），输出人读摘要
arl scan
arl scan --claude-home <目录> --codex-home <目录>   # 显式指定日志位置

# 同一分析落盘为报告（Markdown 默认形态 + HTML 可选，均零外链可离线打开）
arl scan --report-md report.md
arl scan --report-md report.md --report-html report.html
```

预期输出形态（摘要人读；报告章节与摘要同一处引擎产出，`tests/test_m5_report.py` 锁三方一致）：

```text
scan 完成：N 个会话，M 个工具事件，K 个 token 事件，P 条解析注记
返工判定（阈值：版本 ≥ REWORK_MIN_VERSIONS 或编辑 ≥ REWORK_MIN_EDITS）：a 项 rework / b 项 insufficient_data / c 项 not_rework
  - [claude_code] <会话 id>：工具事件 x，写事件 y，版本链 z 条
  [verdict] rework <文件路径>：版本 3 / 编辑 4 / 跨度 1200s / 理由 versions>=N,edits>=M
    [evidence] <会话源文件>:<行号>
    [evidence] <版本快照 hash>@v3
报告已写入：report.md（Markdown）
```

报告章节：返工文件 Top（含证据锚点列）/ 重复候选 Top（**必带"粗匹配 ≠ 确认重复"披露**）/ 会话指标（Read:Edit 比，分母 0 显式"未定义"）/ 注记（解析注记与显式披露，如未支持语言、Codex 源符号候选未启用）。空节显示"无数据"，不显示"一切正常"。

## 指标口径

### 返工判据（M3 定稿）

1. **版本判据**：同一文件在 `file-history` 版本快照链中出现 ≥ `REWORK_MIN_VERSIONS` 个版本 → rework；
2. **编辑判据**：单会话内同一文件被 Edit ≥ `REWORK_MIN_EDITS` 次 → rework；
3. 两条都不成立且**版本链缺失**（有 Edit、链应存在而缺失）→ `insufficient_data`（不反推，K4）；
4. 两条都不成立且链存在 / 纯 Write 新建（首写不备份，无链属正常）→ `not_rework`。
5. Codex 源无 file-history：版本数恒缺失，判据以 apply_patch 写事件计数为主，不判 insufficient_data。

数值见 [`src/agent_rework_lens/config.py`](src/agent_rework_lens/config.py)（`REWORK_MIN_VERSIONS` / `REWORK_MIN_EDITS` / `DUP_MATCH_THRESHOLD`）——**文档不抄数值**，以该单点为准。

### Read:Edit 比

分子 = Read 事件数（`READ_EVENT_KINDS`）；分母 = 写事件数（Edit/Write/MultiEdit，`WRITE_EVENT_KINDS`）；分母为 0 → 比值"未定义"（`None`，**不填 0 不填 inf**）。

### 粗匹配（"新建 vs 复用"候选）

- 归一化 5 步（冻结口径）：① 转小写；② `-`→`_`；③ 去首尾 `_`；④ 首段命中 `SYMBOL_PREFIX_TOKENS` 或尾段命中 `SYMBOL_SUFFIX_TOKENS` → 剔除（可迭代）；⑤ 剩余 token 拼接；
- 匹配两级：归一化精确相等 → `normalized_exact`；否则 `difflib` ratio ≥ `DUP_MATCH_THRESHOLD` → `high_similarity`（附 ratio）；
- **披露制**：任何候选输出伴随披露文本——**粗匹配 ≠ 确认重复**，候选仅为信号，需人工复核。

### 证据锚点

每条结论持 `(源文件:行号)` 与版本快照文件名（`<hash>@vN`）锚点，`bench` 要求可溯源率 100%。

### 门槛来源

`bench` 的覆盖率门槛**只读 `data/synthetic/manifest.json`**（`coverage.min_count_by_type`）——代码中不存在第二份数值；`tests/test_m4_bench.py` 锁死这一来源关系。

## 文档

| 文档 | 内容 |
|---|---|
| [plan/00-README总览.md](plan/00-README总览.md) | 项目总览 / 决策记录 / 里程碑 |
| [plan/01-题目文档.md](plan/01-题目文档.md) | 项目题全文（痛点锚点 / 任务 / 评分 / 边界） |
| [plan/02–07](plan/06-里程碑.md) | 需求解读 / 架构 / 模块详设 / 数据计划 / 里程碑 / 交付对标 |
| [data/README.md](data/README.md) | 数据台账（字段核对记录 / 合成数据纪律） |
| [docs/TECHNICAL-REPORT.md](docs/TECHNICAL-REPORT.md) | 技术报告（schema / 判定口径 / 确定性纪律 / 隐私设计） |

## License

MIT © 2026 yuluo554
