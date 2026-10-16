# release/ · 发布产物耐久副本

本目录保存 GitHub Release 产物的**本机耐久副本**与 sha256 校验单（`.gitignore` 只放行本文件与 `SHA256SUMS.txt`，大二进制 zip 不入 git）。

## 为什么在这里

原发布时产物副本只落在临时目录（`%TEMP%\arl-src\`），可被系统清理，使"本地留有产物副本可复验"这条 DoD 不成立。现于仓库内建耐久副本，并在 `plan/RELEASE-M6.md` §三/§六 留档。

## 内容

| 文件 | 说明 |
|---|---|
| `agent-rework-lens-v0.1.0-m6-source.zip` | tag `v0.1.0-m6` 源码 zip（Release 附件同名件）；**大二进制，不入 git** |
| `SHA256SUMS.txt` | 上述 zip 的 sha256 校验单（入 git） |

## 复验

```bash
# 本地耐久副本
sha256sum "D:/ProgramData/zcode/10-16-agent-rework-lens/release/agent-rework-lens-v0.1.0-m6-source.zip"

# 与远端 Release 附件对照（可复算，无需信任留档中的数字）
gh release download v0.1.0-m6 --repo yuluo554/agent-rework-lens \
  --pattern 'agent-rework-lens-v0.1.0-m6-source.zip' --dir /tmp/arl-verify --clobber
sha256sum /tmp/arl-verify/agent-rework-lens-v0.1.0-m6-source.zip
```

> 注：Release 附件由 tag 树派生，其 sha256 会随 tag 重打而变，故**不写入 tag 树内的文档**（否则自指失效）；以 `SHA256SUMS.txt`（本地耐久）与 `gh release download` 复算为准。
