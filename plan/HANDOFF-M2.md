# HANDOFF-M2（M1 收尾 → M2 解析层交接）

**生成**：2026-10-15（M1 收尾对话）· **续接方式**：新对话输入
`/goal 读取 "<项目绝对路径>\plan\HANDOFF-M2.md" 继续完成任务`（绝对路径仅出现在用户侧命令，库内一律相对路径）

---

## 一、当前进度 + 证据

### M1 已完成（plan/06 M1 全部 DoD 打勾）

| DoD 项 | 证据 |
|---|---|
| 核对项闭环 | data/README §2.6 **R1–R6 全部 ✅**（5/6 项核对闭环；HN 评论原话 1 项显式"条件不足保持待核对"+ 已查渠道，纯题面论据不涉计算路径）；§五 回填闭环表 |
| fixtures + manifest + 真值入仓 | `data/synthetic/`：**47 个冻结文件 / 11 个 case / 7 类样本齐全**（rework 3 / duplicate 2 / normal 2 / missing_chain 1 / single_edit 1 / threshold_exact 1 / near_miss 1）；`manifest.json`（seed + 覆盖度门槛 + 白名单 + 逐文件 sha256）；每个 case 带 `truth.json`（九字段定稿，plan/07 D-M1-7） |
| sha256 三处一致 | manifest ↔ 实际文件逐个比对通过（`tests/test_synthetic_data.py::test_manifest_sha256_matches_frozen_files`）；台账登记总数 47（逐文件哈希只在 manifest 一处，D-M1-6） |
| `--check` 位级一致 | `py -X utf8 tools/gen_synthetic.py --check` → 47 件位级一致，**3.8 与 3.12 双通道实跑通过**；子进程守门测试常驻 |
| 零真实值扫描 | fixtures 目录 + 全仓抽查两道扫描通过（组合路径签名匹配；占位符豁免规则见测试内注释） |
| 覆盖度门槛 | 7 类各达 manifest 最低例数（生成器内 assert + 测试双锁）；阈值**读 config 不抄数值**（K1） |
| 变异验证 ×2 | ① 改生成器输出体例（文档字符串文案 demo → demo-mutated）→ `--check` 红（manifest + 逐文件 sha256 全量报告）→ 恢复复绿；② 手改冻结件字节（追加 LF）→ sha256 守门测试红 → 恢复复绿。两次都改**被测行为**（HANDOFF-M1 §四 方法论落实） |
| 确定性双跑 | `generate()` 双跑 47 件逐字节一致（独立临时目录对账） |
| 全量测试 | **3.12：67 passed**（1.03s）；**3.8：67 passed**（1.41s）——M0 末态 59 + M1 新增 8（test_synthetic_data.py） |
| HANDOFF-M2 落盘 | 本文件 + commit |

### M1 关键核对结论（M2 解析器的直接输入；全文 data/README §2.6）

- **R1**：`@vN` = 第 N 次编辑**前**的备份（v1 = 原始内容）；版本链长度 = `@vN` 最大 N；
- **R2**：快照 = 编辑前全文副本（62/68 UTF-8 文本、6/68 二进制——按二进制计数不解析）；
- **R3**：Codex 目标文件路径在 `payload.input`（V4A 文本）`*** Update/Add File: <path>` 指令行内（**不在 JSON arguments 里**）；`payload.type` 有 function_call / custom_tool_call 两种容器；
- **R4**：MultiEdit 本机 0 次；Edit input 固定 `{file_path, old_string, new_string, replace_all}`、Write 固定 `{file_path, content}`；
- **R5**：Codex 全量工具分布（exec 10093 / apply_patch 104 …）；**apply_patch 是 Codex 唯一写文件工具** = Codex 侧编辑计数主证据；
- **R6**：快照↔目录关联键 = `<transcript stem（session uuid）>` + `backupFileName`（75/75 精确命中）；`trackedFileBackups` 为 dict（键=真实文件路径），entry 固定 4 字段、可含 null（**容错**）；快照记录 version 可高于目录现存（实测 v5 vs v3）→ **只实读目录，不反推**。

### 仓库现状

- 提交链：`ec34524`（题定稿）→ M0 commit（骨架+测试+CI）→ 本次 M1 commit（tools/ + data/synthetic/ + 守门测试 + 台账/plan 回写）；
- 新增：`tools/gen_synthetic.py`（确定性生成器：splitmix64、固定 seed 20261015、常量时间戳、LF/无 BOM、K10 护栏）、`data/synthetic/**`（冻结，`.gitattributes -text` 生效）、`tests/test_synthetic_data.py`（8 项守门）；
- 决策记录：plan/07 §3.3 D-M1-1..7（@vN 语义 / 快照口径 / Codex 解析口径 / MultiEdit 处置 / 稀疏性处置 / 台账哈希形态 / truth schema）。

## 二、下一棒待办（M2 · 解析层，详见 plan/06 M2 段与 plan/04）

1. **双源解析器**：`parsers/claude_code.py` / `codex.py` 按 §2.6 口径实现（R1–R6 即字段策略表）；
   - Claude：`type` 驱动；工具调用在 `message.content[].tool_use`；快照行 4 字段 entry（容 null）；file-history 目录实读建版本链；
   - Codex：`payload.type` 驱动；apply_patch 按 V4A 指令行提取目标路径；
   - 核对状态 ≠ ✅ 的字段落 unknown / 跳过并计 ParseNote（`item_completed.item.type` 不启用；MultiEdit 见 R4）；
2. **file-history 读取**：`file → versions` 结构，与 IR 会话关联（注意 R6 稀疏性 + R2 二进制快照）；
3. 路径自适应接入 `scan`；**M2 起退出码 4 逐项退役**（退役 = 删常量 + 改 test_cli + 改 plan/07 K 表，K2 流程）；
4. 测试：**合成样例逐例回归**（data/synthetic 11 case 全过）+ 坏行容错 + 空文件 + **双跑 IR 逐字节一致**（K3/K11）；
5. M2 收尾按惯例：HANDOFF-M3 + plan/00·06·07 回写 + commit。

## 三、既定口径清单（K 编号摘要；全表 plan/07 §四）

- **K1** 阈值单点 config.py（生成器已示范"读 config 不抄数值"）；
- **K2** 退出码 0/1/2/3/4（M2 起逐项退役 4）；
- **K3** IR 唯一契约（KINDS 枚举序锁测试）；**K4** 版本链只实读不反推（R1/R6 已给出实现口径）；
- **K5** 粗匹配披露；**K6** 报告零判定零外链零时钟；
- **K7** 未核对字段不进计算路径 → **M1 已解锁**：被解析字段全部 ✅ 或显式不启用（M2 落实为 ParseNote 机制）；
- **K8** CLI 双通路；**K9** 合成数据零真实+确定性（fixtures 禁手改）；**K10** 编码护栏（tools/ 脚本第一行 `_ensure_utf8_stdio()`——gen_synthetic.py 已示范）；
- **K11** 确定性落盘（时间入参不读时钟）；**K12** 三面一致（M1 未新增测试期依赖，dev extras 仍只有 pytest）。

## 四、本机环境坑（M1 新增/复确认）

1. **合成 fixture 的 EOL**：生成器全部显式 `\n` + 二进制写盘（`write_bytes`），Windows 不会引入 CRLF；`.gitattributes` `data/synthetic/** -text` 已生效——**不要**把 fixtures 当普通文本编辑（会破坏 sha256）；
2. **临时目录生成对账**：`--check` 用 `tempfile.TemporaryDirectory()` 重生成比对——对账前**清空目标目录**的旧文件也要比（"未登记的现存文件"检查），防手改文件藏在 manifest 之外（守门测试有反向检查）；
3. 零真实值扫描的**占位符豁免**：`C:\Users\<user>`、`/home/<user>` 这类形态说明（尖括号占位）不算命中——签名命中后看下一字符是否 `<`/`{`；台账 §2.5 有合法的形态说明文本，全仓扫描不要误伤；
4. M0 坑全部沿用：`py -X utf8` + `PYTHONDONTWRITEBYTECODE=1` 全程；Git Bash `~` 不传 Python；裸 `arl` 跑在 3.12 通道；
5. 本机数据快照（R1–R6 的计数）为 2026-10-15 实测，**非交付承诺**；真实日志零原始文本/零真实路径/零真实 session id 入仓（已由扫描测试兜底）。

## 五、M2 DoD checklist（逐项验收，完成后才能写 HANDOFF-M3）

- [ ] 双源解析器按 §2.6 R1–R6 口径实现；合成样例（11 case）逐例解析通过
- [ ] 双跑 IR 逐字节一致（确定性对账测试）
- [ ] 未核对字段 0 泄漏进计算路径（扫描测试：ParseNote 机制生效）
- [ ] `arl scan` 全链路（发现→解析→IR）可跑通并输出会话/事件计数摘要（暂不含引擎结论）；退出码 4 的骨架期语义按 K2 流程逐项退役
- [ ] 坏行容错 / 空文件 / 二进制快照（R2）不炸解析器
- [ ] plan/00·06·07 状态回写；HANDOFF-M3 落盘 + commit

## 六、关键命令速查

```bash
# 测试（双解释器；先 export PYTHONDONTWRITEBYTECODE=1）
py -3.12 -X utf8 -m pytest          # 在仓库根（M1 末态 67 项）
py -3.8  -X utf8 -m pytest

# 合成 fixtures（冻结件禁手改；改动走重生成）
py -X utf8 tools/gen_synthetic.py --check    # 位级一致（exit 1 = 有差异）
py -X utf8 tools/gen_synthetic.py            # 整目录重生成 + manifest

# CLI 双通路
py -3.12 -X utf8 -m agent_rework_lens version
arl sources                          # 列本机日志源
arl scan                             # M2 起逐步解除 exit 4 拦截

# git
git status && git log --oneline | head -3
```

## 七、诚实口径备忘

- 本仓库**未接远端**：一切 CI 结论写作"本地等价校验（未接远端，CI 待首推验证）"；
- data/README 的 R1–R6 计数与 §2 各源条数为 2026-10-15 实测快照，非交付承诺；
- 测试计数（67）为 M1 末态实测，文档不预写未来里程碑的数字；
- MultiEdit 字段形态**本机未见**（如实登记，未编造）；HN 评论原话保持弱表述。
