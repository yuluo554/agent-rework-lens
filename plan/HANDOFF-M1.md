# HANDOFF-M1（M0 收尾 → M1 数据先行交接）

**生成**：2026-10-15（M0 收尾对话）· **续接方式**：新对话输入
`/goal 读取 "<项目绝对路径>\plan\HANDOFF-M1.md" 继续完成任务`（绝对路径仅出现在用户侧命令，库内一律相对路径）

---

## 一、当前进度 + 证据

### M0 已完成（plan/06 M0 全部 DoD 打勾）

| DoD 项 | 证据 |
|---|---|
| plan/00–07 齐全且状态回写 | plan/00 索引表、plan/06 回写区与 M0 段已回写 ✅；02–07 六份 M0 定稿 |
| 骨架可运行 | `arl version` / `arl sources` / `arl selftest` 实跑通过（selftest 5 项全 ok，本机探测 413 文件）；`arl scan` 无源 → exit 3、有源 → exit 4 明确拦截 |
| 双解释器全量测试 | 3.12：**59 passed**（0.85s）；3.8：**59 passed**（1.38s）；安装态（`pip install -e ".[dev]"` 双版本成功）后复跑仍全绿 |
| CI workflow 落盘 | `.github/workflows/ci.yml`：三腿（ubuntu-22.04×3.8 / ubuntu-latest×3.12 / windows-latest×3.12）+ 双通路冒烟。**本地等价校验（未接远端，CI 待首推验证）**：可本机实跑的等价物 = 双解释器全量 pytest + `python -m`/`arl` 双通路冒烟 + selftest 全 ok；不可本机实跑 = CI 三腿 runner 环境 → 待首推验证 |
| 退出码 + 守门测试 | exit 0/2/3/4 真实触发（`tests/test_cli.py`）；阈值 AST 守门（`tests/test_config.py`）通过 |
| 变异验证（编码护栏） | 见 §四（含第一轮无效变异实录） |
| HANDOFF-M1 落盘 | 本文件 + commit |

### 仓库现状

- 提交链：`ec34524`（题定稿）→ 本次 M0 commit（plan/00–07 + 骨架 + 测试 + CI）；
- 工程：`pyproject.toml`（零运行时依赖，dev=pytest）、src 布局单包 `agent_rework_lens`、`.gitattributes`（EOL 归一 + `data/synthetic/** -text` 预案）、README/LICENSE；
- 核心层：`config`（阈值单点）/ `exitcodes` / `stdio`（护栏）/ `errors`（NoSourcesFound·StageNotReady）/ `discovery`（递归发现+缺源语义）/ `ir`（schema v1 frozen dataclass）/ `parsers`（common 已实现，双源骨架拦截）/ `engine`（metrics 计数助手已实现，rework/symbols 拦截）/ `report`（markdown+html 渲染器已实现，含披露与零外链）/ `pipeline` / `selftest` / `cli`；
- 测试 59 项：exitcodes / config AST 守门 / ir 确定性 / stdio（cp1252 复现+cp936 不动+阳性对照）/ discovery（递归/缺源/优先级/确定性）/ cli（分支+子进程）/ report（披露/零外链/确定性/空节）/ engine / parsers / selftest。

## 二、下一棒待办（M1 · 数据先行，详见 plan/06 M1 段与 plan/05）

1. **字段核对**（data/README §五 5 项 + plan/02 §六）：
   - file-history `version` 语义（v1 = 原始 or 首次备份）+ 快照内容格式 → 决定 FR-5/6 启用方式；
   - Codex `apply_patch` 载荷内目标文件路径字段格式；
   - `MultiEdit` 存在性与字段形态（本机快照未见计数）；
   - Codex 全量 220 文件工具调用分布聚合；
   - `file-history-snapshot` 内联字段与目录的关联方式；
   - **纪律**：核对输出只落"统计数字 + 字段名 + 结论"，原始文本/真实路径/真实 session id 一律不入仓（data/README §三）。
2. **合成生成器** `tools/gen_synthetic.py`：确定性（自研 RNG、禁 stdlib random/禁时钟、固定 seed）；7 类样本矩阵（rework / duplicate / normal / missing_chain / single_edit / threshold_exact / near_miss）；真值同步标注 + 互斥断言；`--check` 位级一致；
3. **冻结 fixtures**：`data/synthetic/**` + `manifest.json`（覆盖率门槛数值 + 假名白名单 + 逐文件 sha256）；`.gitattributes` 已预案；
4. **守门测试**：再生成位级一致 + 零真实值扫描（组合路径签名匹配）；
5. data/README 全面回填（核对记录三态表 + 生成器说明 + 冻结登记）。

## 三、既定口径清单（K 编号，动了会打挂测试；全表 plan/07 §四）

- **K1** 阈值单点：`REWORK_MIN_VERSIONS` / `REWORK_MIN_EDITS` / `DUP_MATCH_THRESHOLD` 三常量只在 `config.py` 赋值（**数值以 config.py 为准，文档不抄第二份**）；AST 守门锁"模块级赋值只允许出现在 config.py"。生成器造"卡阈值"样例时**读 config**，不许抄数值。
- **K2** 退出码：0 成功 / 1 内部错误 / 2 用法 / 3 未发现源 / 4 阶段未就绪（M2 起逐项退役；退役 = 删常量+改 test_cli+改 plan/07）。
- **K3** IR 唯一契约：下游只认 IR；`KINDS` 枚举序已锁测试。
- **K4** 版本链只来自 file-history 实读；缺失 → `insufficient_data`；禁止反推。
- **K5** 粗匹配披露：任何候选输出必带 `DUP_DISCLOSURE`（报告层已锁测试）。
- **K6** 报告零判定 + 零外链 + 渲染器不读时钟（空节"无数据"已锁）。
- **K7** 未核对字段不进计算路径 → M1 核对完成前解析器保持 `StageNotReady`（**这就是 scan exit 4 的原因**，不是缺陷）。
- **K8** CLI 双通路：`python -m agent_rework_lens` ≡ `arl`；CI 双冒烟已配。
- **K9** 合成数据零真实 + 确定性（禁 stdlib random / 禁时钟；白名单登记制）。
- **K10** 编码护栏：所有会打印的入口（cli + **M1 新增的每个 tools/ 脚本第一行**）调 `_ensure_utf8_stdio()`。
- **K11** 确定性落盘：时间一律入参，不读系统时钟。
- **K12** 三面一致：测试面 = 安装面 = README 面；dev extras 只含 pytest；M1 若新增测试期依赖必须同步 pyproject + README + CI。

## 四、本机环境坑（只写实测过的）

1. **变异验证第一轮无效（本对话实录，方法论级）**：把 `_stream_needs_utf8` 的 `return False` 改成 `return False if True else False`——**等价改写**，测试照绿 = 无效对照（skill 教训"对照组必须改被测行为"的现场复现）。正确变异 = 改**探针的 except 分支**（cp1252 应判 True 处返回 False）→ 3 项测试红（test_cp1252_detected_and_recovered / test_ascii_reconfigured / test_guard_idempotent）→ 恢复后绿。**M1 起做生成器 `--check` 等守门的变异验证时，先问"我改的是被测行为吗"。**
2. `py -X utf8` 全程使用；`PYTHONDONTWRITEBYTECODE=1` 全程（含 pip install）。
3. 双解释器通道实测可用：3.8.8（pip 25.0.1 / pytest 7.4.4 / setuptools 75.3.4）+ 3.12（pip 26.2.1 / pytest 8.4.2）；3.8 装包后 `arl.exe` 落在 3.8 的 Scripts（不在 PATH），`which arl` 命中 3.12 的——**裸命令测试跑在 3.12 通道**，属已知且无碍（CI 双通路另验）。
4. `pip install -e` 双版本一次性成功，无 venv ensurepip 问题；editable 安装后 `arl` 直查分发元数据。
5. Git Bash 下 `~` 展开与 Windows Python 的路径差异：代码内一律 `pathlib + expanduser`（discovery 已如此），**不要把 shell 展开路径传给 Python**。
6. 本机会话日志实测规模：`arl selftest` 的发现探测 = 413 个文件（Claude 125 + file-history 68 + Codex 220），与 data/README 快照一致。

## 五、M1 DoD checklist（逐项验收，完成后才能写 HANDOFF-M2）

- [ ] data/README §五 待核对项全部闭环（或显式"条件不足保持待核对"+已查渠道）
- [ ] `tools/gen_synthetic.py` + 冻结 fixtures + `manifest.json` 入仓；sha256：manifest ↔ 台账 ↔ 实际文件三处一致
- [ ] 生成器 `--check` 位级一致通过（且做过一次"改体例 → check 红"的变异验证）
- [ ] 覆盖度门槛：7 类样本各达 manifest 最低例数；真值与样例同源生成
- [ ] 零真实值扫描测试通过（fixtures 目录 + 全仓抽查）
- [ ] `.gitattributes` 对 `data/synthetic/**` 的 `-text` 生效（克隆后 sha256 不变）
- [ ] plan/00·05·06·07 状态回写；HANDOFF-M2 落盘 + commit

## 六、关键命令速查

```bash
# 测试（双解释器；先 export PYTHONDONTWRITEBYTECODE=1）
py -3.12 -X utf8 -m pytest          # 在仓库根
py -3.8  -X utf8 -m pytest

# CLI 双通路
py -3.12 -X utf8 -m agent_rework_lens version
arl sources                          # 列本机日志源
arl selftest                         # 自检 5 项
arl scan                             # M0 语义：无源 exit 3 / 有源 exit 4（K7 拦截）

# 安装（README 同款；dev extras = pytest）
py -3.12 -m pip install -e ".[dev]"

# git
git status && git log --oneline | head -3
```

## 七、诚实口径备忘

- 本仓库**未接远端**：一切 CI 结论写作"本地等价校验（未接远端，CI 待首推验证）"，等价物清单见 §一 DoD 表 CI 行；
- data/README 中的数据源计数为 2026-10-15 实测快照，非交付承诺；
- 测试计数（59）为 M0 末态实测，**文档不预写未来里程碑的数字**。
