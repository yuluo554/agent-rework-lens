# HANDOFF-M7（M6 发布完成 → M7 收尾固化交接）

**生成**：2026-10-15（M6 发布对话）· **续接方式**：新对话输入
`/goal 读取 "<项目绝对路径>\plan\HANDOFF-M7.md" 继续完成任务`（绝对路径仅出现在用户侧命令，库内一律相对路径）

---

## 一、M6 已完成（全 DoD 打勾，plan/06 M6 段 + plan/RELEASE-M6.md 留档）

| DoD 项 | 证据 |
|---|---|
| 脱敏扫描全 0 | 工作树 grep（用户名/目录前缀/邮箱/token 形态串）0 命中；历史 8 commit / 229 对象 / 142 路径扫描 0 命中（唯一命中 `C:\Users\<user>` 为 M1 台账尖括号占位豁免）；fixtures 白名单假名合规 + manifest sha256 冻结（`gen_synthetic --check` 0）；plan/ 无系列前作与业务领域词 |
| 建仓 + 首推 | 公开仓 https://github.com/yuluo554/agent-rework-lens（用户确认后建仓）；main 首推成功（网络不稳，重试循环 + ls-remote 复核） |
| CI 三腿全绿 | run 38739618483（push 触发，逐条配对）：py3.8·ubuntu-22.04 ✓ 27s / py3.12·ubuntu-latest ✓ 14s / py3.12·windows-latest ✓ 36s；首跑即绿，无诊断轮次 |
| tag + Release | tag `v0.1.0-m6`（annotated，指向 536b7d0）；Release draft=false 实测；附件 `agent-rework-lens-v0.1.0-m6-source.zip`（228,532 B）sha256 `2f4b397e…f54a10`，解包复验 manifest/fixture 与仓库 HEAD 位级一致 |
| 留档 | plan/RELEASE-M6.md 入库（命令+结果+run id+网络坑实录）；README 状态行转"🚀 已发布 v0.1.0-m6" |

**M6 决策**（续入 plan/07 时建议编号 D-M6-1..2）：
- **D-M6-1** push 网络对策：git 443 间歇重置（gh api 同刻可通）→ 一律"重试 ≤5 次（sleep 12s）+ 远端 ls-remote/--json 复核为准"，单次失败不作最终结论；
- **D-M6-2** CI 注记不阻塞：checkout@v4/setup-python@v5 的 Node 20 deprecation 警告与 ubuntu-latest→26 迁移提示记入 RELEASE-M6 §二，不影响结论；后续升级 actions 版本可消除。

## 二、下一棒待办（M7 · 收尾固化，详见 plan/06 M7 段）

1. README 状态/计数与末态一致复核（150 项测试口径、退出码 0/1/2/3）；
2. 缓议项清零：盘点 plan/07 各"缓议/跳过"项，逐条给结论（做/跳过），跳过须显式留档理由（如 Codex 符号候选 D-M5-2、K8 双通路以外的入口）；
3. GitHub 元信息核验：description（已设"AI 代码返工体检器…"）、topics 补齐（建议：claude-code、codex、static-analysis、ai-agent、developer-tools，≤20 个按需取舍）、release 资产在位；
4. 品牌隔离复查（系列前作零引用终检）+ 全仓计数一致（README/plan/报告内测试数口径）；
5. HANDOFF-M8（或收尾完结档）落盘 + commit + push（沿用 D-M6-1 重试纪律）。

## 三、既定口径（K 编号沿用 HANDOFF-M6 §三，无新增变更；K12 dev extras 仍只有 pytest）

## 四、本机环境坑（M6 新增 + 沿用）

```bash
# github.com 443 间歇重置（git 不稳、gh api 同刻可通）：一律重试循环 + 远端复核
for i in 1 2 3 4 5; do git push ... ; git ls-remote ... && break; sleep 12; done

# 测试/校验（沿用）
py -3.12 -X utf8 -m pytest        # 150 项
py -3.8  -X utf8 -m pytest
py -X utf8 tools/gen_synthetic.py --check
git status && git log --oneline | head -3
```

其余坑沿用 HANDOFF-M6 §四（py -X utf8、临时 home 显式传参、fixtures 冻结、Windows Path.is_absolute）。

## 五、M7 DoD checklist（逐项验收）

- [x] README 状态/计数与末态一致；缓议项清零并留档（WRAPUP-M7 §二/§四）
- [x] GitHub 元信息（description/topics/release）核验（WRAPUP-M7 §一）
- [x] 品牌隔离复查 + 全仓计数一致（WRAPUP-M7 §三/§四）
- [x] 收尾交接档落盘 + commit + push（plan/WRAPUP-M7.md，完结档）

## 六、诚实口径备忘

- CI 已实跑三腿全绿（run 38739618483），但未覆盖 macOS；Node 20 deprecation 注记见 RELEASE-M6 §二；
- Release 附件为 zipball（源码包），非构建产物——本项目零第三方依赖，无需 wheel/sdist 发布（若 M7 决定补 PyPI 属新范围，须显式决策）；
- 测试计数 150 为 M5 末态实测，M6 未动代码路径（仅 README/plan 文档改动），M7 若加测试须同步口径。
