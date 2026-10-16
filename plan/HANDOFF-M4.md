# HANDOFF-M4（M3 收尾 → M4 基准交接）

**生成**：2026-10-15（M3 收尾对话）· **续接方式**：新对话输入
`/goal 读取 "<项目绝对路径>\plan\HANDOFF-M4.md" 继续完成任务`（绝对路径仅出现在用户侧命令，库内一律相对路径）

---

## 一、当前进度 + 证据

### M3 已完成（plan/06 M3 全部 DoD 打勾）

| DoD 项 | 证据 |
|---|---|
| 合成真值驱动的检测对账通过 | `tests/test_m3_engine.py::test_engine_matches_truth`：11 case 逐例参数化——rework-01/02/threshold_exact-01 命中（版本 3/4/3，`versions>=N`）、codex-rework-03 命中（`edits>=M`，apply_patch 4 次）、duplicate-01/02 引擎侧符号候选对账（`normalized_exact`）、single_edit/normal/near_miss → not_rework、missing_chain → insufficient_data |
| 反例全绿 | near_miss（ratio ≈ 0.48 < `DUP_MATCH_THRESHOLD` 不命中）/ single_edit（链 =1）/ normal（纯 Write 无链）不命中；missing_chain → insufficient_data 且 `version_count=None`、理由含 `version_chain_missing`（K4 不猜测） |
| 阈值改动一处 → 全链路同变 | `test_threshold_edits_change_flips_verdict_everywhere`（monkeypatch 改 `config.REWORK_MIN_EDITS` → verdict 翻转）/ `test_threshold_versions_change_flips_verdict` / `test_dup_threshold_change_affects_matching`（改 `DUP_MATCH_THRESHOLD` → 匹配翻转） |
| Read:Edit 比 + 符号提取 + 粗匹配 | `engine/metrics.py`（除零 → None 不填 0/inf；`compute_session_metrics` 聚合；`writes_by_kind` 有序键值）+ `engine/symbols.py`（def/class 正则 + 未支持语言显式 `None`）+ 归一化 5 步（plan/04 §7.4 冻结口径）+ K5 披露单点 `DUP_DISCLOSURE`（迁至 metrics，report/model 引用，D-M3-4） |
| `arl scan` 输出引擎结构化摘要 | `run_scan` 接 `analyze_rework` → `ScanOutcome.findings`（按 session/file/verdict 排序）；CLI 输出三态计数（阈值取 config 运行时值）+ 逐 finding 的版本/编辑/跨度/理由/证据锚点。实测 11 case 全量：`4 项 rework / 1 项 insufficient_data / 6 项 not_rework`，与 truth 全对上 |
| 确定性 | CLI scan 双跑逐字节一致；3.8 与 3.12 输出一致 |
| 阈值校准定稿 | **D-M3-1**：`REWORK_MIN_VERSIONS` / `REWORK_MIN_EDITS` / `DUP_MATCH_THRESHOLD` 三常量经基准校准后原值定稿（**数值见 config.py 单点**；threshold_exact `≥` 语义命中 / near_miss 不命中即校准依据）；plan/07 §3.5 |
| 全量测试 | **3.12：125 passed**；**3.8：125 passed**——M2 末态 101 + M3 新增/改 24；`gen_synthetic --check` 47 件位级一致（本次未动 fixtures） |

### M3 关键实现口径（M4 runner 的直接输入）

- **判定入口**：`analyze_rework(ir, version_chains, snapshot_file_map) -> Tuple[ReworkFinding, ...]`；`ReworkFinding(file_path, session_id, verdict, version_count, edit_count, first_edit_seq, last_edit_seq, span_seconds, reasons, evidence)`；
- **verdict 三态**：`versions>=N` 或 `edits>=M` → rework；都未达且 Edit 无链 → insufficient_data（K4）；都未达且链存在或纯 Write 新建 → not_rework（**D-M3-3 链缺失语义细分**：Write 新建无链属正常，Edit 无链才是证据缺失）；
- **链归属（D-M3-2）**：`read_snapshot_file_map(会话文件)` 实读快照行 `trackedFileBackups` 的 `file_path → backupFileName`（R6 关联键，只取已核对字段）+ `read_version_chains(file-history 目录)` 按 hash stem 对齐；对不上 → None；
- **Codex**：无 file-history → 版本数恒缺失，判据以 apply_patch 写事件计数为主（truth `reason: "edits"`），不判 insufficient_data；
- **reasons 字面量**：`versions>=N` / `edits>=M` / `both_below_threshold` / `version_chain_missing`（engine/rework 常量单点）；
- **锚点**：`evidence` = `源文件:行号` 列表 + `<hash>@vN` 版本文件名（链存在时）；span = 首末编辑时间戳差（ISO 解析，缺失 → None）；
- **粗匹配**：`find_dup_candidates(new_symbols, existing_symbols)`，`match_symbols` 两级（normalized_exact / high_similarity+difflib ratio）；披露文本 `DUP_DISCLOSURE` 单点在 engine/metrics（K5）；
- **scan 摘要形态**：`ScanOutcome(discovery, sessions, version_chains, findings)` + `rework_count` 属性；M4 在此之上接 `run_bench`（plan/04 §9）。

## 二、下一棒待办（M4 · 基准，详见 plan/06 M4 段与 plan/04 §9）

1. **`benchmark/runner.py`**：`run_bench(data_dir) -> BenchResult`——读 manifest 门槛（**数值只在下发数据里，不在代码里**）→ 逐样例解析→引擎→truth 对账（检测率/误报率/锚点可溯源率）→ 汇总；
2. 退出码三语义（0 达标 / 1 未达标 / 2 用法）锁测试；**"未启用"套件不冒充通过**（空分母 → `not_enabled` + 说明 + 退出码 1 的探活保护）；
3. **可证伪探活（变异验证）**：注入缺陷（如把返工判定强行置 False）→ 基准必须报未达标；命令 + 结果留档 plan/06 或 HANDOFF-M5；恢复 → 变绿；
4. 覆盖率门槛不足时的明确拦截（造一次"不达标"演示并留档）；
5. README 指标口径节成稿（Read:Edit 定义 / 返工判据 / 粗匹配规则 / 门槛来源 = manifest）；
6. M4 收尾按惯例：HANDOFF-M5 + plan/00·06·07 回写 + commit。

## 三、既定口径清单（K 编号摘要；全表 plan/07 §四）

- **K1** 阈值单点 config.py（**已定稿 D-M3-1：3/3/0.9**）；**K2** 退出码 0/1/2/3（4 已退役）；
- **K3** IR 唯一契约；**K4** 版本链只实读不反推（解析侧+引擎侧均已落实，D-M3-2/3）；
- **K5** 粗匹配披露（单点 engine/metrics，D-M3-4）；**K6** 报告零判定零外链零时钟；
- **K7** 未核对字段不进计算路径（快照映射只取 `backupFileName`/`version` 已核对字段）；**K8** CLI 双通路；
- **K9** 合成数据零真实+确定性（fixtures 禁手改）；**K10** 编码护栏；**K11** 确定性落盘（引擎不读时钟，span 由事件时间戳入参计算）；**K12** 三面一致（M3 未新增测试期依赖，dev extras 仍只有 pytest）。

## 四、本机环境坑（沿用 + M3 复确认）

1. `py -X utf8` + `PYTHONDONTWRITEBYTECODE=1` 全程；Git Bash `~` 不传 Python；裸 `arl` 跑在 3.12 通道；
2. 合成 fixtures 冻结（`.gitattributes -text`）；本次 M3 未动 fixtures，`--check` 47 件位级一致复验通过；
3. run_scan 需要**布局正确的临时 home**（`projects/<sid>/session.jsonl` + `file-history/<sid>/`；codex = `sessions/<sid>/session.jsonl`）——case 目录本身不是 home 布局，测试/演示用复制脚本搭（见 test_m2_parsing.py / HANDOFF 三.4）；
4. 坏行 ParseNote 的 message 含行号 → 逐行分立不聚合计数（测试断言用 `sum(count)`）；
5. 3.8 无 `datetime.fromisoformat` 的部分特性依赖？**已实测无碍**（rework-01 span=1200s 在双解释器一致）——`fromisoformat` 在 3.8 可用，但带 `Z` 后缀的 ISO 需手工转 `+00:00`（engine/rework 已处理）；
6. 测试计数（125）为 M3 末态实测，文档不预写未来里程碑数字。

## 五、M4 DoD checklist（逐项验收，完成后才能写 HANDOFF-M5）

- [ ] `arl bench` 全绿且可复现（双跑一致）；退出码 0/1/2 三语义锁测试
- [ ] 探活变异验证留档（注入缺陷 → 变红；恢复 → 变绿）
- [ ] 覆盖率门槛不足时有明确拦截（造一次"不达标"演示并留档）
- [ ] README 指标口径节成稿（定义 / 阈值引用 config 常量名 / 复现命令）
- [ ] plan/00·06·07 状态回写；HANDOFF-M5 落盘 + commit

## 六、关键命令速查

```bash
# 测试（双解释器；先 export PYTHONDONTWRITEBYTECODE=1）
py -3.12 -X utf8 -m pytest          # 在仓库根（M3 末态 125 项）
py -3.8  -X utf8 -m pytest

# 合成 fixtures（冻结件禁手改）
py -X utf8 tools/gen_synthetic.py --check

# CLI（M3 起输出引擎判定摘要，退出码 0）
py -3.12 -X utf8 -m agent_rework_lens scan --claude-home <tmp-home> --codex-home <tmp-codex>
arl sources

# git
git status && git log --oneline | head -3
```

## 七、诚实口径备忘

- 本仓库**未接远端**：CI 结论一律写"本地等价校验（未接远端，CI 待首推验证）"；
- 测试计数（125）为 M3 末态实测；scan 输出的判定**只来自引擎单点**，报告渲染（M4/M5 充实）仍守 K6 零判定纪律；
- MultiEdit 字段形态本机未见（解析器按 D-M1-4 降级处理，不编造）；HN 评论原话保持弱表述；
- 阈值校准基于 11 case 合成基准（正反例全分开），样本规模有限——M4 runner 落地后如需调阈值，仍走 config 单点 + 决策记录。
