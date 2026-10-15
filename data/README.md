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
| ⬜→✅ 待核对（M1 已闭环） | `version` 字段语义与快照内容格式 → **已核对，见 §2.6 核对记录 R1/R2** |

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
| ⬜→✅ 待核对（M1 已闭环） | `apply_patch` 载荷内目标文件路径格式 → **已核对，见 §2.6 R3**；`item_completed.item.type` 枚举 → M1 核对（结论：非计算必需字段，**保持待核对/不启用**，M2 解析不读它） |

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

### 2.6 M1 字段核对记录（2026-10-15 实测；只落统计数字 + 字段名 + 结论，零原始文本/真实路径/真实 session id）

**核对方法**：临时脚本离线聚合统计（脚本不落仓）；所有计数为本机实测快照。

| # | 待核对项 | 状态 | 样本出处（脱敏描述） | 结论 |
|---|---|---|---|---|
| R1 | file-history `version` 语义（v1 = 原始 or 首次备份） | ✅ **已核对** | 68 个快照文件 × 49 个（会话,文件哈希）链；与会话 transcript 内 Edit `old_string`/`new_string` 交叉比对 | **`@vN` = 第 N 次编辑前的内容备份**（v1 = agent 首次修改前的原始内容）。证据：v1 强烈富集 Edit `old_string` 命中（43 处 pre-image vs 37 处 post-image）；链级抽样中"低版本=pre-image、高版本=post-image"成对出现（2 例明确、其余链长不足）。**口径**：版本链长度 = `@vN` 最大 N；判"返工"以实读链为准（K4 不反推） |
| R2 | 快照文件内容格式 | ✅ **已核对** | 68 个文件字节头 + 解码抽样 | 内容 = **编辑前文件全文副本**：62/68 为 UTF-8 文本、6/68 非 UTF-8（二进制副本照存）；大小 305 B–约 100 KB；同链相邻版本哈希两两不同（非占位符）。**口径**：按"全文副本"读，不可解码的按二进制计数、不解析内容 |
| R3 | Codex `apply_patch` 载荷内目标文件路径字段 | ✅ **已核对** | 220 文件全量聚合：104 次 `apply_patch`，`payload` 键集固定，`input` 100% 为 str | 目标文件路径**不在 JSON arguments 里，而在 `payload.input`（V4A 补丁文本）的指令行内**：`*** Update File: <path>` / `*** Add File: <path>`（实测 Update 103 / Add 88 / Delete 0；路径绝对形态 142 / 相对形态 49）。**口径**：M2 解析器按指令行提取目标路径；`payload.type` ∈ {function_call, custom_tool_call} 两种容器都出现 |
| R4 | Claude `MultiEdit` 存在性与字段形态 | ✅ **已核对** | 125 文件全量工具名聚合 | **本机 125 文件 0 次 `MultiEdit`**（不存在于本机快照）。写工具实测两种且字段形态固定：`Edit{file_path, old_string, new_string, replace_all}` 252 次、`Write{file_path, content}` 116 次。**口径**：M2 按 Edit/Write 解析；MultiEdit 字段留 known-name 占位（KIND_MULTIEDIT 已在 IR 注册），出现即按"多段 Edit 序列"语义降级处理并计 ParseNote |
| R5 | Codex 全量工具调用分布 | ✅ **已核对** | 220 文件全量聚合（function_call + custom_tool_call） | `exec` 10093 / `wait_agent` 1258 / `wait` 916 / `js` 576 / `send_message` 309 / `shell_command` 271 / **`apply_patch` 104** / `exec_command` 93 / `list_agents` 86 / `view_image` 59 / `followup_task` 45 / `update_plan` 44 / `run` 33（前 13 项，其余零散）。**唯一写文件工具 = apply_patch**；`payload.type` 全量分布：token_count 37500 / item_completed 24583 / reasoning 15645 / custom_tool_call 10197 / message 6020 / function_call 3908 / … |
| R6 | `file-history-snapshot` 内联字段与 file-history 目录的关联方式 | ✅ **已核对** | 123 条快照行 × 68 个目录文件交叉比对 | 关联键 = **`<transcript 文件名 stem（= session uuid）>` + `backupFileName`**：`trackedFileBackups` 为 **dict**（键 = 被跟踪真实文件路径字符串），entry 固定 `{backupFileName: str, version: int, backupTime: ISO, realParentDir: str}` 4 字段；75/75 个非空 `backupFileName` 精确命中 `file-history/<session-uuid>/<backupFileName>`；3 个 entry 的 `backupFileName` 为 null（**稀疏性**，解析须容空）。快照行 `snapshot` 内层固定 `{messageId, timestamp, trackedFileBackups}`；**快照记录的 version 可高于目录现存文件**（实测记录到 v5、目录仅存到 v3）→ 目录是**稀疏证据**，只能实读不可反推（与 K4 互证） |

**M1 核对总结**：data/README §五 5 项全部闭环（R1–R6）；K7 解锁——M2 可按上述口径实现双源解析器。

---

## 三、合成数据纪律（M1 起含生成器与冻结登记）

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

### 3.1 生成器说明（M1 落地）

- **脚本**：`tools/gen_synthetic.py`（自研 splitmix64 RNG、seed 固定于 manifest；**禁 stdlib random、禁系统时钟**；所有时间戳为常量）；
- **命令**：`py -X utf8 tools/gen_synthetic.py`（生成/重生成整目录）；`py -X utf8 tools/gen_synthetic.py --check`（重生成与冻结件**逐字节比对**，差异 → exit 1）；
- **样本矩阵**：7 类（rework / duplicate / normal / missing_chain / single_edit / threshold_exact / near_miss），阈值**读 `agent_rework_lens.config`，不抄数值**（K1）；真值 truth.json 生成时同步标注（plan/05 §4.3 字段集）；
- **形态忠实度**：Claude/Codex 行形态按 §2.6 R3–R6 核对结论构造（字段名、嵌套结构、V4A 指令行、快照 4 字段 entry）；
- **确定性验证**：双跑逐字节一致（实测通过）；`--check` 守门入 pytest（`tests/test_synthetic_data.py`）。

### 3.2 冻结登记（M1）

- **冻结范围**：`data/synthetic/**`（manifest.json + samples/ 全部文件）；**禁手改**，改动走生成器整目录重生成；
- **sha256 三联动**：manifest 内 `sha256` 映射 ↔ 实际文件 ↔ 本台账登记（**47 个冻结文件**，样例 11 case，基准日 2026-10-15；逐文件哈希以 manifest 为准，本台账登记总数——台账不抄第二份哈希清单，防漂移）；
- **覆盖度门槛**（数值单点在 manifest `coverage.min_count_by_type`，此处不复制数值）：7 类各有最低例数；实际计数见 manifest `actual_count_by_type`；
- **EOL 冻结**：`.gitattributes` `data/synthetic/** -text` 已生效（克隆/检出不改字节，sha256 稳定）；
- **守门测试**：`tests/test_synthetic_data.py` 8 项（sha256 三处一致 / `--check` 子进程位级 / 覆盖度达标 / truth schema / 白名单形态 / 零真实值扫描 fixtures + 全仓 / .gitattributes 规则）；
- **变异验证实录**（M1，方法论见 HANDOFF-M1 §四）：① 改生成器输出体例（文档字符串文案）→ `--check` 变红（manifest + 逐文件 sha256 全量报告）→ 恢复绿；② 手改冻结件字节（加 LF）→ sha256 守门测试变红 → 恢复绿。两次变异都改**被测行为**，非等价改写。

---

## 四、数值口径纪律

1. **阈值一处定义**：返工版本数阈值 N、Edit 次数阈值 M、粗匹配相似度阈值等**只在配置一处定义**（配置文件 / 常量模块）；**报告、基准、README、文档一律引用该处**，**禁止在任何地方手写第二份阈值口径**（"逐字节一致"式守门会把错误口径一起冻结，事后抓不到）。
2. **题面不写会漂移的硬数字**：测试数 / 文件数 / 体积 / 通过数**一律不写**，确需时以**末态回填**；本台账中的数据源条数是**本机实测快照**（附基准日 2026-10-15），**不是交付承诺**。
3. **指标口径明示**：Read:Edit 比的分子分母（哪些工具计入）、"粗匹配"的归一化规则与相似度定义、返工判定的两个门槛，**全部写进 README 指标口径节**，与配置同源。
4. **粗匹配 ≠ 确认重复**：报告与文档**必须显式标注**"符号名粗匹配是**信号/候选**，不是克隆判决"，并列出匹配对与命中理由供人复核——**不得把候选当结论**。
5. **计数事实 ≠ AI 评分**：所有指标是**确定性计数与结构性事实**（版本链、Edit 次数、Read:Edit 比、符号名匹配）；**不引入任何模型 judgement**。

---

## 五、待核对项（⬜ 闭环路径）—— M1 全部闭环（2026-10-15）

| # | 待核对项 | 闭环状态（M1） |
|---|---|---|
| 1 | HN item 44548554 内"refactor duplicate code"评论的**精确原话与楼层锚点** | **⬜ 保持待核对**（条件不足：本对话未抓取评论树；已查渠道 = Firebase API 条目级实测）。未核到前题面保持"该讨论中"的弱表述——**不影响计算路径**（纯题面论据） |
| 2 | Codex `apply_patch` 载荷内**目标文件路径字段**格式 | ✅ 已核对 → §2.6 R3 |
| 3 | `file-history` 的 `version` 语义与快照文件内容格式 | ✅ 已核对 → §2.6 R1/R2 |
| 4 | Claude Code `MultiEdit` / 其他写工具字段形态 | ✅ 已核对（本机不存在 MultiEdit）→ §2.6 R4 |
| 5 | Codex 全量工具调用分布 | ✅ 已核对 → §2.6 R5 |
| 6 | Claude `file-history-snapshot` 与目录的关联方式 | ✅ 已核对 → §2.6 R6 |

**K7 状态**：将被解析的字段已全部核对（或显式"不启用"：`item_completed.item.type` 枚举、MultiEdit 字段）→ M2 解析器可按 §2.6 口径实现。
