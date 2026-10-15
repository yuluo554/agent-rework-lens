# HANDOFF-M3（M2 收尾 → M3 引擎交接）

**生成**：2026-10-15（M2 收尾对话）· **续接方式**：新对话输入
`/goal 读取 "<项目绝对路径>\plan\HANDOFF-M3.md" 继续完成任务`（绝对路径仅出现在用户侧命令，库内一律相对路径）

---

## 一、当前进度 + 证据

### M2 已完成（plan/06 M2 全部 DoD 打勾）

| DoD 项 | 证据 |
|---|---|
| 双源解析器按 §2.6 R1–R6 口径实现 | `parsers/claude_code.py`（type 驱动 / `message.content[].tool_use` / 快照行形态校验容 null / MultiEdit 降级注记）+ `parsers/codex.py`（`payload.type` 驱动 / apply_patch 按 V4A `*** Update/Add File: <path>` 指令行提取路径 / exec 只计事件不提路径） |
| file-history 实读建链（K4） | `read_version_chains()`：`<claude_home>/file-history/<session>/` 目录实读 → `{session_id: {hash_stem: {versions, files, max_version}}}`；只信 `@vN` 文件名，记录版本高于目录现存不反推 |
| 合成样例 11 case 逐例回归 | `tests/test_m2_parsing.py`：truth 驱动参数化（会话 id / 写事件计数 / 版本链 / apply_patch 路径全对账）+ 专项：rework-01 链 (1,2,3) / codex-rework-03 4 次 patch 路径一致 / single_edit 链 =1 / missing_chain 链 =0 |
| 双跑 IR 逐字节一致 | 逐例 `ir == again` + `to_json()` 相等；run_scan 端到端双跑 JSON 相等（K3/K11 双锁） |
| 未核对字段 0 泄漏（K7） | 扫描测试：全样例 tool_events 只含已核对 tool_name；未核对 payload.type / 快照多余字段 / MultiEdit / apply_patch 缺 input → 显式 ParseNote，不进计算路径 |
| `arl scan` 全链路可跑 | 发现→解析→IR，输出确定性摘要（会话/工具事件/token 事件/解析注记 + 逐会话写事件与版本链条数；**零判定零外链零时钟**，K6）。实测：3 case 临时 home → `scan 完成：3 个会话，8 个工具事件…` |
| 退出码 4 退役（K2） | **D-M2-1**：删 `STAGE_NOT_READY` 常量 → 改 test_cli（scan 改锁 0 + 摘要）/ test_exitcodes（`not hasattr` 防复活）/ selftest 退出码映射 → 改 plan/07 K2 表。engine/benchmark 的 StageNotReady 护栏（M3/M4 启用）不受影响 |
| 容错 | 坏行（逐行分立注记）/ 空文件 / 非 dict JSON / 快照 entry null / 快照 entry 多余字段 / 文件名无 `@vN`（证据不可用 → 链为空不猜测）/ apply_patch 缺 input（仍计写事件 + 路径 unknown） |
| 全量测试 | **3.12：101 passed**（1.3s）；**3.8：101 passed**（1.6s）——M1 末态 67 + M2 新增/改 34 |
| HANDOFF-M3 落盘 | 本文件 + commit |

### M2 关键实现口径（M3 引擎的直接输入）

- **Claude**：`Edit/NotebookEdit→edit`、`Write→write`、`MultiEdit→edit`+ParseNote（D-M1-4）、`Bash→exec`、`Read→read`、其余→other；事件 `seq` = 源文件行号（1 起）；
- **Codex**：`function_call(name=exec)→exec`；`custom_tool_call(name=apply_patch)→write`，**每个目标文件一条写事件**（同一 patch 更新 N 个文件 = N 条事件）；路径只取自 V4A 指令行（R3）；缺 input 仍计 1 条写事件（file_path=None）；
- **版本链**：`ParsedSession.version_chains`（Codex 恒空 dict）；`ScanOutcome.version_chains` 按会话绑定；`versions` 升序 tuple、`max_version` = 链长（R1）；
- **确定性**：事件按行号 seq；sessions 按 (source, session_id, source_file) 排序；notes 按 (code, message) 去重计数——全部不读时钟（K11）；
- **scan 摘要形态**：`ScanOutcome`（discovery/sessions/version_chains）+ CLI 文本输出；M3 在此之上接 `analyze_rework`（plan/04 §7.1：version_count=链长、edit_count=写事件数、verdict 三态）。

## 二、下一棒待办（M3 · 引擎，详见 plan/06 M3 段与 plan/04 §7）

1. **返工检测** `engine/rework.py::analyze_rework`：输入 = IR 写事件 + FileVersionChain；判定三态（rework / not_rework / insufficient_data）；**K4 禁止反推**：两条件都不成立且链缺失 → insufficient_data；时间跨度 = 首末编辑时间戳差（缺失 → None）；
2. **指标** `engine/metrics.py`：Read:Edit 比（分母 0 → None 不填 0/inf）；writes_by_kind；符号提取 `engine/symbols.py`（首期 Python；未支持语言显式拒绝）；粗匹配（归一化口径 plan/04 §7.4 已冻结 + **K5 披露文本常驻**）；
3. **阈值校准**：用 M1 基准样例校准 N/M/相似度 → config 单点定稿（K1；变更记决策记录）；
4. 测试：truth 驱动对账（rework/threshold_exact 应命中）+ 反例（near_miss / single_edit / normal 不命中）+ missing_chain → insufficient_data + 除零 + 锚点字段（seq / 版本文件名）；
5. M3 收尾按惯例：HANDOFF-M4 + plan/00·06·07 回写 + commit。

## 三、既定口径清单（K 编号摘要；全表 plan/07 §四）

- **K1** 阈值单点 config.py；**K2** 退出码 0/1/2/3（4 已退役，D-M2-1）；
- **K3** IR 唯一契约（KINDS 枚举序锁测试）；**K4** 版本链只实读不反推（解析器已落实）；
- **K5** 粗匹配披露；**K6** 报告零判定零外链零时钟；
- **K7** 未核对字段不进计算路径 → 解析侧已落实（ParseNote 机制 + 扫描测试），引擎侧沿用；
- **K8** CLI 双通路；**K9** 合成数据零真实+确定性（fixtures 禁手改）；**K10** 编码护栏（tools/ 脚本第一行 `_ensure_utf8_stdio()`）；
- **K11** 确定性落盘（时间入参不读时钟）；**K12** 三面一致（M2 未新增测试期依赖，dev extras 仍只有 pytest）。

## 四、本机环境坑（沿用 + M2 复确认）

1. `py -X utf8` + `PYTHONDONTWRITEBYTECODE=1` 全程；Git Bash `~` 不传 Python；裸 `arl` 跑在 3.12 通道；
2. 合成 fixtures 冻结（`.gitattributes -text`）；改动走 `tools/gen_synthetic.py` 重生成 + `--check`（本次 M2 未动 fixtures，`--check` 47 件位级一致复验通过）；
3. 坏行 ParseNote 的 message 含行号 → 逐行分立不聚合计数（测试断言用 `sum(count)`）；
4. run_scan 需要**布局正确的临时 home**（`projects/<sid>/session.jsonl` + `file-history/<sid>/`），case 目录本身不是 home 布局——测试/演示用复制脚本搭（见 test_m2_parsing.py）；
5. 本机数据快照（R1–R6 计数）为 2026-10-15 实测，非交付承诺；测试计数（101）为 M2 末态实测，文档不预写未来里程碑数字。

## 五、M3 DoD checklist（逐项验收，完成后才能写 HANDOFF-M4）

- [ ] `analyze_rework` 三态判定 + reasons + 时间跨度；truth 驱动对账通过（rework / threshold_exact 命中）
- [ ] 反例全绿（near_miss / single_edit / normal 不命中；missing_chain → insufficient_data）
- [ ] Read:Edit 比 + 符号提取 + 粗匹配（含 K5 披露）实现并测试
- [ ] 阈值改动一处 → 全链路同变（config 单点 + 测试）
- [ ] plan/00·06·07 状态回写；HANDOFF-M4 落盘 + commit

## 六、关键命令速查

```bash
# 测试（双解释器；先 export PYTHONDONTWRITEBYTECODE=1）
py -3.12 -X utf8 -m pytest          # 在仓库根（M2 末态 101 项）
py -3.8  -X utf8 -m pytest

# 合成 fixtures（冻结件禁手改）
py -X utf8 tools/gen_synthetic.py --check

# CLI
py -3.12 -X utf8 -m agent_rework_lens scan --claude-home <tmp-home>   # M2 起输出解析摘要（退出码 0）
arl sources

# git
git status && git log --oneline | head -3
```

## 七、诚实口径备忘

- 本仓库**未接远端**：CI 结论一律写"本地等价校验（未接远端，CI 待首推验证）"；
- 测试计数（101）为 M2 末态实测；scan 摘要**不含引擎结论**（M3 接入），报告零判定纪律（K6）不变；
- MultiEdit 字段形态本机未见（解析器按 D-M1-4 降级处理，不编造）；HN 评论原话保持弱表述。
