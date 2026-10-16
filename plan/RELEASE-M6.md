# RELEASE-M6 发布留档

**日期**：2026-10-15（首发布）· **审计修复重发**：2026-10-16 · **仓库**：https://github.com/yuluo554/agent-rework-lens（公开）
**tag**：`v0.1.0-m6`（annotated）· **Release**：https://github.com/yuluo554/agent-rework-lens/releases/tag/v0.1.0-m6（draft=false 实测核验）

> **tag 指向（审计修复后）**：`v0.1.0-m6` 重打至**发布态提交**（含 `plan/RELEASE-M6.md` / `plan/WRAPUP-M7.md` / `plan/HANDOFF-M7.md`，README 为"已发布"态，plan/00 台账与 plan/06 M6/M7 DoD 已回填）。核验：`git cat-file -e v0.1.0-m6:plan/RELEASE-M6.md` 成功、`git show v0.1.0-m6:README.md` 状态行为"已发布"。**首发布时 tag 误指向 M5 收尾态（重写前 `536b7d0`，重写后同内容提交为 `996ca7e`；tag 树缺 M6/M7 留档、README 仍写"功能完整（M5）"）——该缺陷已由本次重打修正（见 §六）。**

## 一、发布前置清单（逐条实测）

| 项 | 结果 |
|---|---|
| 脱敏① 工作树 grep（本机用户名/目录前缀/邮箱/token 形态串） | **全 0**；`yuluo554` 仅出现于 LICENSE/README 署名、pyproject authors、plan 命名约定（合法署名位） |
| 脱敏② 历史 `git log -p` + `rev-list --objects --all` | **全 0**；唯一命中为 `C:\Users\<user>` 尖括号占位形态说明（豁免口径内，见 M1 台账） |
| 脱敏③ 合成数据白名单假名 | 合规：demo-project-alpha/beta、demo-user、demo-host、00000000-…-NN、/demo/{alpha,beta}/src；manifest sha256 冻结未动（`gen_synthetic --check` 退出码 0） |
| 脱敏④ plan/ 隐私纪律 | 无系列前作名称、无业务领域词（财税/发票/合同审计/政策计算等 grep 0 命中）；"审计/隐私"均为本工具自身正当表述 |
| 脱敏⑤ **提交邮箱（审计修复新增）** | **全部提交 author/committer 邮箱改为 `282769740+yuluo554@users.noreply.github.com`**；本地 `git log --format='%ae %ce' \| sort -u` 与远端 `gh api .../commits --jq '.[].commit.author.email'` 均只剩 noreply（见 §六） |
| 产物扫描 | 工作树 clean；无 .venv/__pycache__/报告产物/egg-info 入仓；.gitignore 覆盖完整（`release/` 已忽略） |
| 历史三连 | git status 干净 / log 逐条符合 / objects 与预期一致 |

## 二、CI 首跑（run 与 push 逐条配对）

| run id | 触发 | 结果 |
|---|---|---|
| 38739618483 | push（main 首推） | **三腿全绿**：py3.8·ubuntu-22.04 ✓（27s）/ py3.12·ubuntu-latest ✓（14s）/ py3.12·windows-latest ✓（36s） |
| 38739916516 | push（tag 分支） | 三腿全绿 |
| 38740360820 | push（main，M6 发布提交） | 三腿全绿 |
| 38742655059 | push（main，M7 收尾提交） | 三腿全绿 |

> 上表为**首发布时**的 run（对应重写前的 commit sha，重写邮箱后这些 sha 已不存在于远端，run 记录仍可在 GitHub Actions 历史页查看）；**审计修复重发后的 run id 见 §6.1**。

CI workflow `on: push + pull_request`，同一 commit 的 run 与 push 逐条对应；首跑即全绿（无诊断轮次）。
注记（非失败）：actions/checkout@v4、setup-python@v5 的 Node.js 20 deprecation 警告；ubuntu-latest 将于 2026-10-19 起迁移 Ubuntu 26。后续升级 actions 版本可消除，不影响 M6 结论。

## 三、Release 产物与 sha256

### 3.1 首发布（M5 收尾态 zipball，历史留档）

- 附件：`agent-rework-lens-v0.1.0-m6-source.zip`（228,532 字节，**首发布时**为 tag `v0.1.0-m6` 的 zipball，tag 当时指向 M5 收尾态）
- **zip sha256**：`2f4b397eddce48a0674efb7b5a8d2f0296a550930b61377d4e4d87691df54a10`
- 复验：下载附件解包 → `data/synthetic/manifest.json` 与仓库当时 HEAD 位级一致；抽样 fixture `case-claude_code-duplicate-01/session.jsonl` sha256 与 manifest 登记值一致（`f65cf846…b57a3f`）。

### 3.2 审计修复重发产物（耐久副本 + 可复算）

- **本地耐久副本**（仓库内、`.gitignore` 已忽略大二进制，不盲入 git）：
  `D:\ProgramData\zcode\10-16-agent-rework-lens\release\agent-rework-lens-v0.1.0-m6-source.zip`
  - 同目录 `release/SHA256SUMS.txt` 记录其 sha256（与本机副本同落，未入 git）。
- **可复算命令**（无需信任留档中硬编码的数字，任何时刻可重算）：
  ```bash
  gh release download v0.1.0-m6 --repo yuluo554/agent-rework-lens \
    --pattern 'agent-rework-lens-v0.1.0-m6-source.zip' --dir /tmp/arl-verify --clobber
  sha256sum /tmp/arl-verify/agent-rework-lens-v0.1.0-m6-source.zip
  # 与本机耐久副本对照：
  sha256sum "D:/ProgramData/zcode/10-16-agent-rework-lens/release/agent-rework-lens-v0.1.0-m6-source.zip"
  ```
- **自指说明（为何本文件不硬编码重发附件 sha256）**：重发附件为 tag `v0.1.0-m6` 的 zipball，其内容**包含本文件**——若在本文件内写死该 zipball 的 sha256，则改动本文件即改变 zipball 内容、sha256 随之失效（自指循环）。故**具体值不在 tag 树内硬编码**，改由：①上文可复算命令；②本机耐久副本 `release/SHA256SUMS.txt`；③本档"§6.3 发布后回填"（tag 之后的 main 提交，实测值）。首发布的旧附件（M5 收尾态 zipball）sha256 见 §3.1（历史事实，与本文件无自指关系）。

## 四、发布实录（网络坑实录）

- `gh repo create --public` 成功；`git push` 遇 github.com:443 间歇性连接重置（git 直连不稳，gh api 同刻可通）——重试循环（≤5 次 + sleep 12s）全部通过；每次以 `ls-remote`/`--json` 远端复核为准，不采信单次失败为最终结果。

## 五、诚实口径

- CI 覆盖 ubuntu/windows × 3.8/3.12 三组合，未覆盖 macOS；
- 干净环境验证（HANDOFF-M6 §一）为本机双解释器 + CI 三腿实证；
- 符号候选 Codex 源未启用（披露制，D-M5-2），已在报告与 README 声明。

## 六、审计修复（2026-10-16）—— 缺陷逐条与实测

> 来源：发布后独立审计（7 项，逐条已核实）。修复顺序：先做代码/文档修复并提交 → 再统一重写提交邮箱（重写改所有 hash）→ 再重打 tag → 最后推 main + tag。

| # | 缺陷 | 修复 | 实测证据 |
|---|---|---|---|
| 1 | 全部提交作者邮箱为真实 QQ 邮箱（隐私泄露，已推公开远端） | 用 `git filter-repo --email-callback` 把**全部**提交的 author/committer 邮箱改写为 `282769740+yuluo554@users.noreply.github.com` | 本地 `git log --format='%ae %ce' \| sort -u` 只剩 noreply；远端 `gh api repos/yuluo554/agent-rework-lens/commits --jq '.[].commit.author.email' \| sort -u` 只剩 noreply（见 §6.2） |
| 2 | tag `v0.1.0-m6` 指向 M5 收尾态（重写前 `536b7d0`），tag 树缺 `RELEASE-M6.md`/`WRAPUP-M7.md`/`HANDOFF-M7.md`，README 仍"M5 功能完整" | 删旧 tag，在**发布态提交**上重打 `v0.1.0-m6`；核对 Release 附件（tag zipball）并重传 | `git cat-file -e v0.1.0-m6:plan/RELEASE-M6.md` 成功；`git show v0.1.0-m6:README.md` 为"🚀 已发布"；`gh release view` draft=false + 附件 sha256 复验（见 §6.1） |
| 3 | plan/00 台账与里程碑表未回填（tag 树态"发布闭环 ⬜ 待 M6"、M6/M7"⬜ 待开工"、plan/06 M6/M7 DoD 全 `[ ]`） | 按末态全部回填 ✅（台账状态列与里程碑同步） | 工作树与 tag 树 plan/00 台账"发布闭环 ✅ M6"、plan/06 M6/M7 DoD 全 `[x]`、回写区含 M6/M7 |
| 4 | 粗匹配两级只测到一级（`high_similarity` 分支仅单测、bench 未对账） | 生成器新增 `duplicate` 的 `high_similarity` 分支样例（`make_compute_helpr` ↔ `make_compute_helper`，ratio≈0.97 ≥ `DUP_MATCH_THRESHOLD`）；manifest `coverage.min_count_by_type.duplicate` 2→3；新增探活 D（抬 `DUP_MATCH_THRESHOLD`→1.0 → duplicate-03 塌） | `arl bench`：12 样例、rework 4/4、误报 0/7、锚点 26/26、达标；`--check` 51 件位级一致；探活 D 红→恢复绿 |
| 5 | Release 产物本地副本仅在 `%TEMP%\arl-src\`（可被清理） | 仓库内 `release/` 建耐久副本 + `release/SHA256SUMS.txt`；留档给可复算下载命令（见 §三 3.2） | 副本 sha256 与 `gh release download` 下载件一致（见 §6.1） |
| 6 | 决策记录手写阈值数值（`plan/07` D-M3-1、`HANDOFF-M1.md` 等"3 / 3 / 0.9"） | 统一改为引用常量名（`REWORK_MIN_VERSIONS` / `REWORK_MIN_EDITS` / `DUP_MATCH_THRESHOLD`），并标注"数值以 config.py 单点为准" | `grep -rn '3 / 3 / 0.9\|N=3\|相似度 0.9' plan/ docs/ README.md` 0 命中（K1 口径） |
| 7 | `plan/01` §五 边界类型枚举不全（漏 `near_miss`） | §五 补"边界类型枚举以 plan/05 §4.2 与 manifest `coverage.min_count_by_type` 为准"并列出 4 类 | plan/01 §五 含 `missing_chain`/`single_edit`/`threshold_exact`/`near_miss` |

### 6.1 重发 CI（口径）

重写邮箱改所有 sha → 重发为新 push：**main 推**与**tag 推**各触发一次 CI（`on: push`），两者对**同一发布态提交**（tag 与 main 同 commit）。**实测 run id 见 §6.3**（tag 之后的 main 提交回填——run id 在推送前不可知，且重打 tag 会改 sha、使旧 run id 失效，故不在 tag 树内硬编码）。

### 6.2 邮箱重写与 tag 重打实测（回填）

**本地**：
```text
$ git log --format='%ae %ce' | sort -u
282769740+yuluo554@users.noreply.github.com 282769740+yuluo554@users.noreply.github.com
```
**远端**（`gh api repos/yuluo554/agent-rework-lens/commits --jq '.[].commit.author.email' | sort -u`）：
```text
282769740+yuluo554@users.noreply.github.com
```
全部提交（10 条原史 + 4 条审计修复）author/committer 邮箱均只剩 noreply；`git filter-repo --email-callback` 实跑，重写后 `git push --force origin main` 与 `git push --force origin refs/tags/v0.1.0-m6` 均成功（**SSH 通路**：本机 `https://github.com:443` 不可达，见 §四 网络注记）。

**tag 指向核验**：
```text
$ git rev-parse v0.1.0-m6^{commit}   → 发布态提交（含 plan/RELEASE-M6.md / plan/WRAPUP-M7.md / plan/HANDOFF-M7.md）
$ git cat-file -e v0.1.0-m6:plan/RELEASE-M6.md   → 成功（旧 tag 树此路径缺失）
$ git show v0.1.0-m6:README.md | sed -n 5p      → "**状态**：🚀 已发布 v0.1.0-m6…"（旧 tag 树为"功能完整（M5）"）
```

### 6.3 发布后回填（tag 之后的 main 提交，规避自指）

> 本节由 tag 之后的 main 提交回填：**重发 CI run id** + **重发 Release 附件 sha256**。二者在 tag 树内不可硬编码——run id 推送前未知、且改写本节会改 tag sha 使 run 失配；附件 sha256 若写入本节（本文件在 tag zipball 内）则自指循环。故 tag 树内本节为占位指针，实测值落在 **tag 之后的 main 提交**（即本段内容所在提交晚于 tag `v0.1.0-m6` 指向的提交）。

**重发 CI（均对 tag/main 同指的发布态提交 `a38bfa0`）**：

| run id | 触发 | 结果 |
|---|---|---|
| 38885116543 | push（main） | **三腿全绿**：py3.8·ubuntu-22.04 ✓ / py3.12·ubuntu-latest ✓ / py3.12·windows-latest ✓ |
| 38885125242 | push（tag `v0.1.0-m6`） | **三腿全绿**：py3.8·ubuntu-22.04 ✓ / py3.12·ubuntu-latest ✓ / py3.12·windows-latest ✓ |

**重发 Release 附件**（tag `v0.1.0-m6` 重打后 zipball，已替换旧附件）：

- 附件：`agent-rework-lens-v0.1.0-m6-source.zip`（248,011 字节；根目录 `yuluo554-agent-rework-lens-e01e3bc/`）
- **sha256**：`d7358f94cd4768c4eb18cb04ee4d4e8ee48f162abbbf492a6b0f835d924bdc6a`
- 复验：`gh release view v0.1.0-m6 --json assets` 的 `digest` 与下载件 sha256 一致；解包含 `plan/RELEASE-M6.md`（旧附件不含，证明确已换成新 tag zipball）。
- 本机耐久副本同值：`release/agent-rework-lens-v0.1.0-m6-source.zip`（`release/SHA256SUMS.txt` 记录，二者均不入 git）。

