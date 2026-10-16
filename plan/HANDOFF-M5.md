# HANDOFF-M5（M4 收尾 → M5 交付交接）

**生成**：2026-10-15（M4 收尾对话）· **续接方式**：新对话输入
`/goal 读取 "<项目绝对路径>\plan\HANDOFF-M5.md" 继续完成任务`（绝对路径仅出现在用户侧命令，库内一律相对路径）

---

## 一、当前进度 + 证据

### M4 已完成（plan/06 M4 全部 DoD 打勾）

| DoD 项 | 证据 |
|---|---|
| `arl bench` 全绿且可复现 | `run_bench(data_dir) -> BenchSummary`（`benchmark/runner.py`）：11 样例逐例 truth 对账全过——rework 命中 **4/4**、误报 **0/6**、锚点可溯源 **25/25**、覆盖率门槛（只读 manifest：要求 7 类全满足，actual rework=3 > 门槛 2）；人读双跑 stdout `diff` 为空；`--json`（sort_keys）双跑一致；CLI 退出码 0 |
| 探活变异验证留档 | 真实通路注入 `analyze_rework = lambda *a, **k: ()` → rc=1 + 逐样例 FAIL（rework-01"期望文件未全部产生 finding"等）；去掉注入 → rc=0"达标"。另锁进测试：探活 A（runner 侧注入→灭→undo→绿）、探活 B（`REWORK_MIN_EDITS`→99 → codex-rework-03 塌）、探活 C（子进程 `-c` 注入 → rc=1；干净 → rc=0）、探活 D（副本 session.jsonl 追加字节 → sha256 拦截）。实录见 plan/06 M4 节 |
| 覆盖率门槛不足明确拦截 | manifest 副本把 `rework` 门槛改 99 → `[覆盖率] 覆盖率门槛不足：rework 实际 3 < 门槛 99` → 退出码 1；"未启用"三态（目录缺失 / manifest 缺失 / 样例为空）→ `not_enabled` + 说明 + 退出码 1，**空分母不冒充满分** |
| 退出码三语义锁测试 | `tests/test_m4_bench.py`：0（达标）/ 1（未达标+未启用，两类各一测试）/ 2（未知选项 argparse SystemExit） |
| README 指标口径成稿 | README 新增"基准（arl bench）"+"指标口径"两节：返工判据五条（引用 config 常量名，不抄数值）/ Read:Edit 定义 / 粗匹配 5 步归一化 + 两级匹配 + 披露制 / 证据锚点 / 门槛来源 = manifest |
| 全量测试 | **3.12：143 passed；3.8：143 passed**（M3 末态 125 + M4 新增 18）；`gen_synthetic --check` 47 件位级一致（M4 未动 fixtures，变异全在副本上，K9） |

### M4 关键实现口径（M5 报告层的直接输入）

- **runner 入口**：`run_bench(data_dir=None) -> BenchSummary`；data_dir 缺省 = 仓库内 `data/synthetic`（`Path(__file__).parents[3]`，src 布局）；
- **BenchSummary**：`not_enabled` / `not_enabled_detail` / `manifest_schema` / `coverage: CoverageReport`（required/actual/missing/extra/under）/ `cases: Tuple[CaseMetrics]` + 聚合属性 `rework_hit` / `rework_total` / `false_positive` / `not_rework_total` / `anchor_ok` / `anchor_total` / `passed` / `failures()`；
- **CaseMetrics 逐项对账**：verdict（期望三态映射：expected_rework→rework；expect_status=insufficient_data→insufficient_data；否则 not_rework）+ expected_rework 逐项（edit_count / version_count / reason）+ expected_normal（edit_count / 不持 rework 理由）+ also_expect（edit_count / version_chain_observed）+ 符号候选集合对账（duplicate case）+ 锚点可溯源（`源文件:行号` 或 `@v`）+ 冻结件 sha256（session+truth；manifest 无记录 → None 不拦，不符 → False 拦）；
- **探活生效点**：monkeypatch 必须打在**消费处**（`benchmark.runner.analyze_rework` 导入引用），打在 engine 模块不生效——探活测试已锁此语义；
- **CLI**：`arl bench [--data-dir] [--json]`；退出码 0/1/2；人读中文 / 机读 sort_keys；未达标清单逐样例逐条打印。

## 二、下一棒待办（M5 · 交付，详见 plan/06 M5 段与 plan/04 §8/§10）

1. **报告成稿**：Markdown 默认 + HTML 可选（`--report`/`--report-dir` 待定）；只渲染模型数据（K6 零判定零外链零时钟）；空节显式"无数据（未启用/未发现）"；候选节必带 `DUP_DISCLOSURE`（K5，engine/metrics 单点）；锚点三元组齐备；
2. **`docs/TECHNICAL-REPORT.md`**：schema 设计 / 判定口径 / 粗匹配方法 / 确定性纪律与隐私设计；
3. README 演示节（可复制命令 + 预期输出形态）；退出码语义逐条与 README 对账（M4 已成稿指标口径节，M5 只补演示）；
4. **干净环境验证**：新目录 clone + 全新 venv 按 README 逐条跑（`.[dev]` 同一 extras 集合，K12）；
5. **行为等价三方对账**：CLI stdout = pipeline 直调 = 报告章节（plan/04 §10，M5 起）；
6. M5 收尾按惯例：HANDOFF-M6（**含发布前置清单**，M6 为发布对话）+ plan/00·06·07 回写 + commit。

## 三、既定口径清单（K 编号摘要；全表 plan/07 §四）

- **K1** 阈值单点 config.py（D-M3-1 定稿 `REWORK_MIN_VERSIONS` / `REWORK_MIN_EDITS` / `DUP_MATCH_THRESHOLD`，数值见 config 单点）；**K2** 退出码 0/1/2/3（4 已退役）；
- **K3** IR 唯一契约；**K4** 版本链只实读不反推；**K5** 粗匹配披露单点（engine/metrics）；
- **K6** 报告零判定零外链零时钟；**K7** 未核对字段不进计算路径；**K8** CLI 双通路；
- **K9** 合成数据零真实+确定性（fixtures 禁手改；**变异/演示一律用副本**——M4 已实践）；**K10** 编码护栏；
- **K11** 确定性落盘（bench 双跑一致已锁）；**K12** 三面一致（M4 未新增测试期依赖，dev extras 仍只有 pytest）。

M4 新增决策：**D-M4-1**（门槛来源=manifest + 达标语义 + sha256 对账）/ **D-M4-2**（未启用≠未达标，同码不同义）/ **D-M4-3**（探活三层级 + 副本纪律）——全表 plan/07 §3.6。

## 四、本机环境坑（沿用 + M4 新增）

1. `py -X utf8` + `PYTHONDONTWRITEBYTECODE=1` 全程；裸 `arl` 跑在 3.12 通道；
2. **Git Bash `/tmp` 路径 Windows Python 不可见**（`py -X utf8` 是原生 Windows 解释器）——涉及 Python 读写临时文件的演示，路径用 `cygpath -w` 转换或放仓库/工作目录内；heredoc（`<<EOF`）传 Python 源也会失败（exit 49），用 `py -c` 单引号串；
3. run_scan 需要布局正确的临时 home（沿用 M2 口径）；bench 不需要（直接吃 case 目录）；
4. fixtures 冻结（`.gitattributes -text`）：M4 未动；覆盖率/篡改演示一律 `shutil.copytree` 副本；
5. 测试计数（143）为 M4 末态实测，文档不预写未来里程碑数字。

## 五、M5 DoD checklist（逐项验收，完成后才能写 HANDOFF-M6）

- [ ] 报告成稿（Markdown 默认 + HTML 可选；证据锚点；披露制；零外链；K6）
- [ ] `docs/TECHNICAL-REPORT.md` 落盘
- [ ] README 演示节 + 退出码语义对账
- [ ] 干净环境逐条跑通（留档，含退出码语义符合性）
- [ ] 行为等价三方对账（CLI stdout = pipeline 直调 = 报告章节）
- [ ] plan/00·06·07 状态回写；HANDOFF-M6（含发布前置清单）落盘 + commit

## 六、关键命令速查

```bash
# 测试（双解释器；先 export PYTHONDONTWRITEBYTECODE=1）
py -3.12 -X utf8 -m pytest          # 在仓库根（M4 末态 143 项）
py -3.8  -X utf8 -m pytest

# 合成 fixtures（冻结件禁手改）
py -X utf8 tools/gen_synthetic.py --check

# CLI（M4 起可用全部 5 个命令）
py -3.12 -X utf8 -m agent_rework_lens bench --data-dir data/synthetic   # 退出码 0
py -3.12 -X utf8 -m agent_rework_lens bench --json
py -3.12 -X utf8 -m agent_rework_lens scan --claude-home <tmp-home> --codex-home <tmp-codex>
arl sources

# git
git status && git log --oneline | head -3
```

## 七、诚实口径备忘

- 本仓库**未接远端**：CI 结论一律写"本地等价校验（未接远端，CI 待首推验证）"；
- 测试计数（143）为 M4 末态实测；bench 判定**只来自引擎单点**（runner 只做对账不重复实现判定语义）；
- 检测率/误报率口径基于 11 case 合成基准，样本规模有限（README 已如实标注门槛来源与对账口径）；
- MultiEdit 字段形态本机未见（解析器按 D-M1-4 降级处理，不编造）；
- 探活注入生效点在 runner 消费处（非 engine 模块本体）——若 M5 重构导入结构，需同步 review 探活测试（tests/test_m4_bench.py 探活 A/C）。
