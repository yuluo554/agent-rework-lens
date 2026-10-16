# HANDOFF-M6（M5 收尾 → M6 发布交接）

**生成**：2026-10-15（M5 收尾对话）· **续接方式**：新对话输入
`/goal 读取 "<项目绝对路径>\plan\HANDOFF-M6.md" 继续完成任务`（绝对路径仅出现在用户侧命令，库内一律相对路径）

---

## 一、当前进度 + 证据

### M5 已完成（plan/06 M5 全部 DoD 打勾；commit 19d3557 + 本次收尾 commit）

| DoD 项 | 证据 |
|---|---|
| 报告成稿 | `pipeline.build_report_model(outcome)` 组装 ReportModel（meta 阈值口径取 config 运行时值 / findings / dup_candidates / session_metrics / notes）；渲染器补**证据锚点列**（返工行 `源文件:行号` + `<hash>@vN`；候选行 `源文件:会话id`）；CLI `arl scan --report-md PATH` / `--report-html PATH` 落盘（D-M5-3，写入显式 `newline="\n"`，3.8 兼容 + 跨平台字节一致）；空节"无数据"、候选节必带 `DUP_DISCLOSURE`（K5/K6 不变） |
| 符号候选进报告 | pipeline 重读会话 Write 载荷提取新写符号（与 bench 同构，D-M5-1）；已有符号 = Read 过且磁盘存在的 `.py`（04 §7.3）；源根 = `<home>/projects`；Codex 源符号候选**未启用并显式披露**（D-M5-2）；未支持语言写入 → 显式披露跳过 |
| `docs/TECHNICAL-REPORT.md` | 落盘 6 节：问题与交付形态 / 数据流与 schema / 判定口径（三态+粗匹配+锚点）/ 确定性纪律与可证伪基准 / 隐私设计 / 已知边界（诚实口径） |
| README 演示节 + 退出码对账 | 新增"演示"节（可复制命令 + 预期输出形态 + 报告章节说明）；退出码表对齐 `exitcodes.py`：0/1/2/3 四码 + "4 已于 M2 退役（D-M2-1）"注记；状态行转"✅ 功能完整（M5）" |
| 干净环境验证留档 | 全新 clone（commit 19d3557）+ 全新 venv **双解释器**（3.12 / 3.8）`pip install -e ".[dev]"` → pytest **150+150 全绿**；5 命令逐条跑：`version`/`sources`/`selftest`/`bench` 退出码全 0；退出码语义逐条符合——`scan` 无源 → **3**（不伪造空报告）、`badcmd` → **2**、`bench --data-dir /nonexistent` → **1**（not_enabled）；合成数据副本演示 `scan --report-md/--report-html` → 退出码 0 + 报告落盘 + HTML 外链 grep **0 命中** |
| 三方对账 | `tests/test_m5_report.py::test_three_way_equivalence`：CLI 落盘报告 = pipeline 直调渲染（逐字节）= CLI stdout verdict 行文件均在报告；另有双跑确定性、锚点列、披露、Codex 未启用、未支持语言、零外链共 7 项新测试 |
| 全量测试 | **3.12：150 passed；3.8：150 passed**（M4 末态 143 + M5 新增 7）；`gen_synthetic --check` 47 件位级一致（M5 未动 fixtures） |

### M5 实录（2026-10-15，本机 3.12 通道）

```text
$ arl bench                          # 全量不变：达标，退出码 0
$ arl scan --report-md report.md --report-html report.html \
    --claude-home demo-claude --codex-home demo-codex   # 合成数据副本
报告已写入：report.md（Markdown）
报告已写入：report.html（HTML）       # 退出码 0；HTML 外链 grep 0 命中
$ arl scan --claude-home empty --codex-home empty       # 无源
未发现可分析日志源。……                 # 退出码 3（不伪造空报告）
```

### M5 新增决策（全表 plan/07 §3.6）

- **D-M5-1** 报告符号候选组装策略（pipeline 重读 Write 载荷；源根 = sessions root 本体；`SYMBOL_LANGUAGE_BY_SUFFIX` 进 config 单点）；
- **D-M5-2** Codex 源符号候选未启用（披露制，不编造 R5/D-M1-4 同族）；
- **D-M5-3** CLI 报告参数形态（`--report-md/--report-html` 落盘；`newline="\n"`；无源不写报告）。

### M5 踩坑实录（沿用）

- **Windows `Path('/demo/x').is_absolute() == False`**（无盘符）→ 初版 `_resolve_existing` 走错分支：`source_root / raw` 拼成 `C:\demo\x` 而非尾部拼接。已改为统一按 `parts` 尾部逐级回退（`_resolve_existing`），有演示测试覆盖（duplicate case 端到端）；
- **`Path.write_text(newline=)` 是 3.10+ 参数** → 3.8 报 TypeError；改 `open(..., newline="\n")`（cli.py 报告写入）；
- **测试造临时 home 必须显式传空 codex home**：`run_scan(str(home), str(codex))`——漏传会自动发现本机真实 `~/.codex`（M5 冒烟时扫出 221 个真实会话，未入任何产物即纠正）；
- Git Bash heredoc/裸 `python` 坑沿用（`py -X utf8` + `PYTHONDONTWRITEBYTECODE=1`；pycache 陈旧会出"代码对但跑不对"，清缓存复跑）。

## 二、下一棒待办（M6 · 发布，详见 plan/06 M6 段）

1. **干净环境复核**（重复 M5 要点，快速回归即可）；
2. **脱敏扫描**（发布前置清单见下）→ 建仓 `yuluo554/agent-rework-lens`（**对外动作：需用户确认**）→ CI 首跑（三腿 3.8/3.12/Windows，run 与 push 逐条配对）；
3. tag + Release 附源码 zip（sha256 留档）+ `plan/RELEASE-M6.md` 发布留档；
4. README 状态行转正 + CI 结论据实补记（追加事实，不改历史措辞）；
5. HANDOFF-M7 落盘 + commit。

### 发布前置清单（M6 开工先逐条过）

- [ ] **脱敏四步**：① 全仓 grep 真实标识（本机用户名 / 真实项目名 / 用户目录前缀路径 / 邮箱 / token 形态串）——工作树扫描全 0；② `git log -p` + `git rev-list --objects --all` 历史扫描全 0；③ 合成数据白名单假名复核（fixtures 禁手改，只查不修）；④ plan/ 目录隐私（系列前作名称/业务领域不入公开仓的纪律复查，见 plan/00 品牌隔离项）；
- [ ] **产物扫描**：`git status` 干净；无 `.venv`/`__pycache__`/报告产物误入仓（`.gitignore` 复核）；
- [ ] **历史=工作树三连**：`git status` / `git log --oneline` / `git rev-list --objects --all` 逐条与预期一致；
- [ ] **远端接通**：`git remote add origin` → 首推（**对外动作，推前向用户确认**）→ CI 三腿全绿（预算多轮诊断）；
- [ ] CI 结论措辞：接远端前一切记录写"本地等价校验（未接远端，CI 待首推验证）"——首推后据实补记。

## 三、既定口径清单（K 编号摘要；全表 plan/07 §四）

- **K1** 阈值单点 config.py（D-M3-1 定稿 `REWORK_MIN_VERSIONS` / `REWORK_MIN_EDITS` / `DUP_MATCH_THRESHOLD`，数值见 config 单点 + M5 新增 `SYMBOL_LANGUAGE_BY_SUFFIX`）；**K2** 退出码 0/1/2/3（4 已退役）；
- **K3** IR 唯一契约；**K4** 版本链只实读不反推；**K5** 粗匹配披露单点（engine/metrics）；
- **K6** 报告零判定零外链零时钟；**K7** 未核对字段不进计算路径；**K8** CLI 双通路；
- **K9** 合成数据零真实+确定性（fixtures 禁手改；变异/演示一律副本）；**K10** 编码护栏；
- **K11** 确定性落盘（渲染/CLI 报告写入 `newline="\n"`）；**K12** 三面一致（dev extras 仍只有 pytest）。

## 四、本机环境坑（沿用 M5 §四 + 速查）

```bash
# 测试（双解释器；仓库根）
py -3.12 -X utf8 -m pytest          # M5 末态 150 项
py -3.8  -X utf8 -m pytest

# 合成 fixtures（冻结件禁手改）
py -X utf8 tools/gen_synthetic.py --check

# CLI（5 命令全可用）
py -3.12 -X utf8 -m agent_rework_lens scan --report-md r.md --report-html r.html \
    --claude-home <tmp> --codex-home <tmp>       # 临时 home 必须显式传空目录！
arl bench                                        # 退出码 0

git status && git log --oneline | head -3
```

其余坑（/tmp 路径、heredoc、run_scan 临时 home 布局、fixtures 冻结）见 HANDOFF-M5 §四，全部沿用。

## 五、M6 DoD checklist（逐项验收，完成后才能写 HANDOFF-M7）

- [ ] 脱敏扫描全 0（工作树 + 历史 + tag 可达对象）+ 审计项逐条留档
- [ ] CI 全绿（三腿）且 run 与 push 逐条配对（首推后据实补记）
- [ ] tag + Release 附件可下载复验 sha256；`gh release view` 核验 draft=false
- [ ] RELEASE-M6.md 入库；README 状态行转正
- [ ] HANDOFF-M7 落盘 + commit

## 六、诚实口径备忘

- 本仓库**仍未接远端**：M5 所有 DoD 的 CI 相关结论均为"本地等价校验（未接远端，CI 待首推验证）"；
- 测试计数（150）为 M5 末态实测；三方对账/零外链/披露均为测试锁定，非口头承诺；
- 干净环境验证在本机双解释器完成，未覆盖 Linux/macOS 差异（CI 三腿首推后补齐）；
- 符号候选链路（Write 载荷重读 + Read 目标磁盘提取）是 M5 新增的真实通路，探活注入测试仍在 runner 消费处（`benchmark.runner.analyze_rework`）——若 M6/M7 重构导入结构需同步 review 探活测试。
