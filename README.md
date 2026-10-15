# agent-rework-lens

> **AI 代码"重复造轮子 + 返工"体检器** —— 扫描本机 Claude Code / Codex 会话日志，回答：**这次会话里 agent 有几成 Edit/Write 是在重写项目里已存在的工具函数？哪些文件被反复改回（返工）？** 纯本地、零模型、零上传。

**状态**：🚧 开发中（M0 骨架）——`version` / `sources` / `selftest` 已可用；`scan` 于 M2 起启用（当前以退出码 4 明确拦截，**不产出假报告**）。路线图见 [plan/06-里程碑.md](plan/06-里程碑.md)。

## 它回答什么

1. **返工**：哪些文件在会话中被反复改回？（版本快照链 v1→v2→v3 / 同一文件多次 Edit）
2. **重复造轮子**：会话内新写的符号里，有多少与项目已有 util/符号**粗匹配**？（候选信号，**非判决**）
3. **Read:Edit 比**：这次会话读了多少才动笔写？

全部指标为**确定性计数与结构性事实**（版本链、Edit 次数、Read:Edit 比、符号名粗匹配）——没有 LLM、没有 AI 评分、没有网络请求。这两块数据（本机版本快照链 + 持久测量基线）是 LLM 聊天拿不到的。

## 隐私声明（红线）

- **纯本地**：不发送任何数据、无遥测、无网络请求；
- **只读**：不修改你的代码，不修改你的日志；
- 真实会话日志含代码与 prompt —— 本仓库的演示与基准一律使用**合成会话日志**（假项目名 / 假路径），**真实日志绝不入仓**。

## 快速开始

```bash
git clone <repo-url> && cd agent-rework-lens
python -m venv .venv
# Windows (Git Bash):  . .venv/Scripts/activate
# Linux / macOS:       source .venv/bin/activate
python -m pip install -e ".[dev]"      # 与 CI 使用同一 extras 集合
arl sources                            # 列出本机发现的日志源与文件数
arl selftest                           # 内置自检
```

`python -m agent_rework_lens` 与 `arl` 等价（两条通路均受支持）。

## 退出码

| 码 | 含义 |
|---|---|
| 0 | 成功 |
| 1 | 内部错误（未预期异常） |
| 2 | 用法错误 / 未知命令 |
| 3 | 未发现可分析日志（明确提示，不伪造空报告） |
| 4 | 阶段未就绪（开发中骨架期的明确拦截；M2 起逐项退役） |

## 指标口径

- 所有**阈值与口径定义集合只在 [`src/agent_rework_lens/config.py`](src/agent_rework_lens/config.py) 一处定义**——报告、基准、生成器与文档一律引用，不写第二份数值；
- 完整口径（Read:Edit 比的分子/分母、返工判据、粗匹配归一化规则）随 M3/M4 定稿进本 README 与 [plan/04-模块详设.md](plan/04-模块详设.md)。

## 文档

| 文档 | 内容 |
|---|---|
| [plan/00-README总览.md](plan/00-README总览.md) | 项目总览 / 决策记录 / 里程碑 |
| [plan/01-题目文档.md](plan/01-题目文档.md) | 项目题全文（痛点锚点 / 任务 / 评分 / 边界） |
| [plan/02–07](plan/06-里程碑.md) | 需求解读 / 架构 / 模块详设 / 数据计划 / 里程碑 / 交付对标 |
| [data/README.md](data/README.md) | 数据台账（字段核对记录 / 合成数据纪律） |
| `docs/TECHNICAL-REPORT.md` | 技术报告（M5） |

## License

MIT © 2026 yuluo554
