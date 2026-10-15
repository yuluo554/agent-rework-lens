# data/ 数据台账

**基准日**：2026-10-15（出题阶段查证与本机数据源实测）
**纪律**：**未挂数据格式核对不得落库 / 不得进入指标计算路径**；阈值只在配置一处定义；题面不写会漂移的硬数字；数据源条数为**本机实测快照**（附基准日），**非交付承诺**。

---

## 一、依据查证记录（逐条三态 + URL + 基准日）

### 1.1 痛点证据（HN 原话，✅ 已核对）

| 依据 | 三态 | 原话 / 说明与来源 |
|---|---|---|
| HN《How to improve code quality of Claude Code and codex》 | ✅ **原话已核对** | 原话：*"agent always **duplicate and create new method instead of think about gracefully extending existing methods**...A carefully maintained claude.md imo is only a mitigation, **not a scalable solution**"*（**明说现有方案不 scalable = 空白**）。条目经 Firebase API 实测：标题含 "Claude Code and codex"，提交时间 **2026-05-06**（ts 1778056637）→ 与题面所记 "2026-05" 一致。https://news.ycombinator.com/item?id=48033774 |
| HN《Ask HN: What tools are you using for human code review of AI-assisted code?》 | ✅ **原话已核对** | 原话：*"AI code review tools...good at finding bugs and style nits, but **less good at finding duplicate code, module cross coupling, bad separation of concerns**"*。条目经 Firebase API 实测：提交时间 **2026-08-16**（ts 1786897245）。https://news.ycombinator.com/item?id=49321400 |
| HN《Ask HN: How are you productively using Claude code?》 | ✅ 条目已核对 / ⬜ 具体评论原话待补 | 该讨论中 agent 做 *"refactor duplicate code into a helper function"* 这类任务直接做错。条目经 Firebase API 实测：提交时间 **2025-07-13**（ts 1752395284）。**⚠️ 精确评论原话与楼层锚点 ⬜ 待补**——题面引用时须降级为"该讨论中"，不得当作已逐字核对的引文。https://news.ycombinator.com/item?id=44548554 |

### 1.2 开源空白检索（7 条检索式，⬜ 软论据）

**检索渠道**：GitHub Search API（`api.github.com/search/repositories`），**基准日 2026-10-15**。
**论据强度声明**：以下为**软论据 ⬜**——有检索式、有基准日、有 API 实测计数，但**无入库截图**，故**不得与"官方文档直连核对"并列作硬锚点**，只能作辅助性空白论据。

| # | 检索式 | total_count（实测） | 最高星 | 判定 |
|---|---|---|---|---|
| 1 | `agent duplicate code instead of refactor` | **0** | — | 空白 |
| 2 | `claude code rework detection` | **1** | `Cliff-AI-Lab/dev-efficiency-monitor` **1★** | 近乎空白 |
| 3 | `agent created duplicate function existing util` | **0** | — | 空白 |
| 4 | `AI code duplication detector` | **7** | `Rafaelpta/dupehound` **97★** | 有竞品但**非 agent 场景**：README 明示 "No AI required"，是通用重复检测 |
| 5 | `duplicate code detector` | — | `ex_dna` 117★ / `reson` 112★ / `microsoft near-duplicate` 105★ | 全是**传统静态克隆检测**（不看会话日志、不做返工） |
| 6 | `AI generated code tech debt` | **7** | `ghostinhershell/reduce-technical-debt-challenge` **11★** | 低星 |
| 7 | `vibe coding technical debt detector` | **2** | `Chillipeeper1/techdebt-ml` **3★** | 低星 |

**判定**：**"针对 agent 会话的重复/返工"是纯空白**——最大竞品 97★（`dupehound`）且**不面向 agent**，其余面向 agent 的项目 ≤1★ 或无结果。本工具与既有克隆检测的**差异化维度**是：既有工具看**代码本体**（AST / 指纹 / 文本），本工具看**会话行为**（版本快照链、Edit 次数、Read:Edit 比）——这些维度既有工具完全不看。

### 1.3 官方文档锚点（✅ 直连核对）

| 依据 | 三态 | 说明与来源 |
|---|---|---|
| Claude Code hooks 文档：会话 transcript 路径与字段 | ✅ **直连核对** | "Common input fields" 表内实测含 `session_id`（Current session identifier）、`transcript_path`（Path to conversation JSON）、`cwd`（Current working directory when the hook is invoked）——证明**会话日志路径与 session_id 是官方公开契约**，非逆向猜测。https://code.claude.com/docs/en/hooks |

---

## 二、数据源可获取性记录（本机当场实测，含字段核对）

**⚠️ 路径自适应声明**：以下路径为**本机（当前用户名）实测**。**用户本地路径因机器而异**（不同用户名、不同安装方式、agent 版本升级可能改目录）——工具**必须自适应发现**（环境变量 / 常见位置探测 + 显式参数覆盖），**不得硬编码绝对路径**；找不到源时明确提示"未发现可分析日志"，**不得伪造空报告**。

### 2.1 Claude Code 会话日志（✅ 本机实测）

| 项 | 实测结果（2026-10-15） |
|---|---|
| 路径 | `~/.claude/projects/<project-slug>/<session-uuid>.jsonl`（`<project-slug>` 由 cwd 路径变形而来，如 `D--ProgramData-claude-code`） |
| 文件数 | **125** 个 `.jsonl`（递归实测；其中一层深 `*/` 下 94 个，分属 5 个 project-slug 目录） |
| 行类型（`type` 字段实测） | `assistant` / `user` / `attachment` / `last-prompt` / `mode` / `permission-mode` / `ai-title` / `system` / **`file-history-snapshot`** |
| 工具调用字段 | `message.content[]` 内 `{"type":"tool_use","name":…}`；实测工具名与计数（**全量 125 文件聚合快照**）：`Bash` 711 / **`Read` 512** / `PowerShell` 328 / **`Edit` 252** / `Grep` 181 / `Glob` 121 / **`Write` 116** / `mcp__desktop-commander__read_file` 92 / `TaskUpdate` 83 / `mcp__windows-mcp__PowerShell` 79 / `WebSearch` 48 / `WebFetch` 48 …（未列全） |
| token 计量字段 | `message.usage` 实测键：`input_tokens` / `cache_creation_input_tokens` / `cache_read_input_tokens` / `output_tokens` / `server_tool_use` / `service_tier` / `cache_creation` / `inference_geo` / `iterations` / `speed` → **可算 Read:Edit 比与 token 侧口径** |
| 版本快照内联字段 | `file-history-snapshot` 行含 `snapshot.trackedFileBackups`，条目形如 `{"backupFileName":"a8f60eb1c3809243@v2","version":2,"backupTime":"2026-08-19T07:45:45.513Z","realParentDir":"D:\\…"}`（**实测样本**）→ 可直接给出"文件 → 版本号 → 备份时间 → 真实父目录"四元组 |
| 覆盖度实况 | `file-history-snapshot` 行 123 条，其中 `trackedFileBackups` **非空仅 11 条** → **版本快照内联信息稀疏，不能只靠它**，必须并读 §2.2 的 file-history 目录 |

### 2.2 Claude Code 文件版本快照（✅ 本机实测，**返工检测的真正底座**）

| 项 | 实测结果（2026-10-15） |
|---|---|
| 路径 | `~/.claude/file-history/<session-uuid>/<hash>@v<N>` |
| 文件数 | **68** 个版本快照文件，分属 **9** 个会话目录（单会话最多 38 个快照） |
| 版本号分布 | `@v1` **21** 个 / `@v2` **46** 个 / `@v3` **1** 个 |
| 可做的判定 | **同一文件出现 `@v1→@v2→@v3` 即"被反复覆盖"= 返工的结构性证据**；配合 §2.1 的 `trackedFileBackups` 可得"哪个真实文件被覆盖了几次" |
| ⬜ 待核对 | `version` 字段语义（v1 是否 = 原始版本或首次备份）→ **M1 用真实样本逐条核对后写进口径**；快照文件内容格式（是否为文件全文副本）→ M1 核对 |

### 2.3 Codex 会话日志（✅ 本机实测）

| 项 | 实测结果（2026-10-15） |
|---|---|
| 路径 | `~/.codex/sessions/YYYY/MM/DD/rollout-<ISO时间>-<uuid>.jsonl` |
| 文件数 | **220** 个（实测 **220/220 全部含 `apply_patch`**，即全部有代码写入行为） |
| 行类型（`type` 实测） | `session_meta` / `response_item` / `event_msg` / `turn_context` |
| `session_meta` 字段 | `session_id` / `id` / `timestamp` / `cwd` / `originator` / `cli_version` / `source` / `thread_source` / `model_provider` / `base_instructions` |
| `payload.type` 实测分布 | `item_completed` 81 / `reasoning` 61 / **`function_call` 49** / `function_call_output` 49 / `message` 48 / **`token_count` 46** / `web_search_call` 31 / `custom_tool_call` 7 / `task_started` 4 / `task_complete` 4 … |
| 工具调用名（实测） | `exec_command` 35 / `update_plan` 10 / **`apply_patch` 7** / `update_goal` 3 / `create_goal` 1（单样本实测；全量分布待 M1 统计） |
| token 计量字段 | `token_count` 载荷 `info.total_token_usage` 实测键：`input_tokens` / `cached_input_tokens` / `cache_write_input_tokens` / `output_tokens` / `reasoning_output_tokens` / `total_tokens`；另有 `last_token_usage` 与 `model_context_window` |
| ⬜ 待核对 | `apply_patch` 载荷（`arguments` JSON 字符串）内的**目标文件路径字段**格式 → **M1 数据先行逐样本核对**；`item_completed.item.type` 枚举（实测见 `UserMessage` 等）→ M1 核对 |

### 2.4 代码侧回滚证据（✅ 可用）

| 项 | 说明 |
|---|---|
| 项目 git log / diff | agent 改完后**是否被人回滚**（revert / 重新提交覆盖）→ 可作为"返工"的第三方佐证，与 §2.2 版本链交叉验证。**首期为可选增强**，不做硬承诺（需项目本身是 git 仓库） |

### 2.5 渠道坑与实测教训

- **Windows 路径两套写法**：Git Bash 下 `~/.claude/...` 展开为 `/c/Users/<user>/...`，而 Windows Python 不认该形式 → **实测教训**：脚本内一律用 `os.path.expanduser` + `pathlib`，**不得把 shell 展开后的路径传给 Python**（本次实测踩过 `FileNotFoundError`）。
- **同一 `~` 下两种深度**：`~/.claude/projects/*/*.jsonl` 只取到一层，实际有嵌套 → 发现逻辑须**递归**，且**按后缀过滤**（`projects` 目录下可能存在空目录）。
- **快照内联信息稀疏**：`file-history-snapshot` 行 123 条里非空仅 11 条 → **不可只用内联字段做返工检测**，必须并读 `file-history` 目录。
- **Codex 与 Claude 结构完全不同**：前者 `payload.type` 驱动、工具调用是 `function_call`；后者 `type` 驱动、工具调用藏在 `message.content[]` 的 `tool_use` → **必须经统一 IR 归一**，不得让下游直接吃两种原始格式。

---

## 三、合成数据纪律

**总则**：基准与演示一律使用**合成会话日志**；**零真实项目、零真实路径、零真实用户名**。

1. **白名单登记**（假名统一登记，禁止真实值入库）：
   - 假项目名：如 `demo-project-alpha` / `demo-project-beta`（**禁**真实项目名、真实仓库名）；
   - 假文件路径：如 `/demo/alpha/src/util_a.py`、`D:\demo\beta\helper.py`（**禁**真实用户目录、真实业务文件名）；
   - 假 session id：形如 `00000000-0000-4000-8000-0000000000NN`（**禁**真实会话 uuid）；
   - 假用户名 / 假主机名：如 `demo-user` / `demo-host`（**禁**真实用户名，见 §二 本机实测路径中的真实用户名**不入仓**）。
2. **植入真值 = 程序化标注**：合成会话日志由生成器**同步产出真值**——生成器在造样例时即记录"该文件应判为返工 / 该符号应判为重复 / 该文件为正常"（**程序化标注，非人工事后补写**），真值库与样例同源同版本入仓，可审计、可复现。
3. **真值覆盖度门槛（口径，非硬数字）**：基准须按**异常类型**（返工 / 重复造轮子 / 正常）与**边界类型**（版本链缺失、单次编辑、恰好卡阈值、符号名近但不重）分别设置最低覆盖项，**覆盖度口径写进 manifest**（各类型最低例数在 manifest 一处定义），防止合成真值偏科。
4. **禁止真实日志入库**：本机真实会话日志**含真实代码与 prompt**——**一律不入仓**（`.gitignore` 兜底 + 提交前审计）；仅在**台账中记录聚合计数快照**（如工具计数），不落原始文本、不落真实路径、不落真实 session id。
5. **禁止"换标签充数"**：合成样例的不同"类型"必须由**生成逻辑本身**区分（真值随生成逻辑产出），不得把同一份样例换标签冒充不同异常类型。

---

## 四、数值口径纪律

1. **阈值一处定义**：返工版本数阈值 N、Edit 次数阈值 M、粗匹配相似度阈值等**只在配置一处定义**（配置文件 / 常量模块）；**报告、基准、README、文档一律引用该处**，**禁止在任何地方手写第二份阈值口径**（"逐字节一致"式守门会把错误口径一起冻结，事后抓不到）。
2. **题面不写会漂移的硬数字**：测试数 / 文件数 / 体积 / 通过数**一律不写**，确需时以**末态回填**；本台账中的数据源条数是**本机实测快照**（附基准日 2026-10-15），**不是交付承诺**。
3. **指标口径明示**：Read:Edit 比的分子分母（哪些工具计入）、"粗匹配"的归一化规则与相似度定义、返工判定的两个门槛，**全部写进 README 指标口径节**，与配置同源。
4. **粗匹配 ≠ 确认重复**：报告与文档**必须显式标注**"符号名粗匹配是**信号/候选**，不是克隆判决"，并列出匹配对与命中理由供人复核——**不得把候选当结论**。
5. **计数事实 ≠ AI 评分**：所有指标是**确定性计数与结构性事实**（版本链、Edit 次数、Read:Edit 比、符号名匹配）；**不引入任何模型 judgement**。

---

## 五、待核对项（⬜ 闭环路径）

| # | 待核对项 | 闭环路径 |
|---|---|---|
| 1 | HN item 44548554 内"refactor duplicate code"评论的**精确原话与楼层锚点** | 有条件时抓取该条评论树，核到逐字原话后升级为 ✅；未核到前题面保持"该讨论中"的弱表述 |
| 2 | Codex `apply_patch` 载荷内**目标文件路径字段**格式 | **M1 数据先行**逐样本核对，核对记录回填本台账 §2.3 |
| 3 | `file-history` 的 `version` 语义（v1 = 原始 or 首次备份）与快照文件内容格式 | **M1** 用真实样本核对后写进口径；未核对前不得据此下"返工"结论 |
| 4 | Claude Code `MultiEdit` / 其他写工具在日志中的字段形态 | **M1** 核对（本机 125 文件快照内未见 `MultiEdit` 计数 → 需确认是否存在、字段是否同形） |
| 5 | Codex 全量工具调用分布（当前仅单样本实测） | **M1** 全量 220 文件聚合统计 |
