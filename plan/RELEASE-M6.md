# RELEASE-M6 发布留档

**日期**：2026-10-15 · **仓库**：https://github.com/yuluo554/agent-rework-lens（公开）
**tag**：`v0.1.0-m6`（annotated，指向 commit 536b7d0 = M5 收尾态）· **Release**：https://github.com/yuluo554/agent-rework-lens/releases/tag/v0.1.0-m6（draft=false 实测核验）

## 一、发布前置清单（逐条实测）

| 项 | 结果 |
|---|---|
| 脱敏① 工作树 grep（本机用户名/目录前缀/邮箱/token 形态串） | **全 0**；`yuluo554` 仅出现于 LICENSE/README 署名、pyproject authors、plan 命名约定（合法署名位） |
| 脱敏② 历史 `git log -p` + `rev-list --objects --all`（8 commit / 229 对象 / 142 唯一路径） | **全 0**；唯一命中 242d8a5 的 `C:\Users\<user>` 为尖括号占位形态说明（豁免口径内，见 M1 台账） |
| 脱敏③ 合成数据白名单假名 | 合规：demo-project-alpha/beta、demo-user、demo-host、00000000-…-NN、/demo/{alpha,beta}/src；manifest sha256 冻结未动（`gen_synthetic --check` 退出码 0） |
| 脱敏④ plan/ 隐私纪律 | 无系列前作名称、无业务领域词（财税/发票/合同审计/政策计算等 grep 0 命中）；"审计/隐私"均为本工具自身正当表述 |
| 产物扫描 | 工作树 clean；无 .venv/__pycache__/报告产物/egg-info 入仓；.gitignore 覆盖完整 |
| 历史三连 | git status 干净 / log 8 条逐条符合 / objects 229 个与预期一致 |

## 二、CI 首跑（run 与 push 逐条配对）

| run id | 触发 | 结果 |
|---|---|---|
| 38739618483 | push（main 首推） | **三腿全绿**：py3.8·ubuntu-22.04 ✓（27s）/ py3.12·ubuntu-latest ✓（14s）/ py3.12·windows-latest ✓（36s） |

CI workflow `on: push + pull_request`，同一 commit 的 run 与 push 逐条对应；首跑即全绿（无诊断轮次）。
注记（非失败）：actions/checkout@v4、setup-python@v5 的 Node.js 20 deprecation 警告；ubuntu-latest 将于 2026-10-19 起迁移 Ubuntu 26。后续升级 actions 版本可消除，不影响 M6 结论。

## 三、Release 产物与 sha256

- 附件：`agent-rework-lens-v0.1.0-m6-source.zip`（228,532 字节，zipball v0.1.0-m6）
- **zip sha256**：`2f4b397eddce48a0674efb7b5a8d2f0296a550930b61377d4e4d87691df54a10`
- 复验：下载附件解包 → `data/synthetic/manifest.json` sha256 `8995db2e…a10b4f` 与仓库 HEAD 位级一致；抽样 fixture `case-claude_code-duplicate-01/session.jsonl` sha256 与 manifest 登记值一致（`f65cf846…b57a3f`）。

## 四、发布实录（网络坑实录）

- `gh repo create --public` 成功；`git push` 遇 github.com:443 间歇性连接重置（git 直连不稳，gh api 同刻可通）——重试循环（≤5 次 + sleep 12s）全部通过：main 首推 3 次内成功、tag 第 2 次、zipball 下载第 1 次、release upload 第 1 次；每次以 `ls-remote`/`--json` 远端复核为准，不采信单次失败为最终结果。

## 五、诚实口径

- CI 覆盖 ubuntu/windows × 3.8/3.12 三组合，未覆盖 macOS；
- 干净环境验证（HANDOFF-M6 §一）仍为本机双解释器 + 本次 CI 三腿实证；
- 符号候选 Codex 源未启用（披露制，D-M5-2），已在报告与 README 声明。
