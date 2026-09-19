# 分阶段 Reviewer Runner

[English](reviewer-runner.en.md) | 中文

状态：`runtime_foundation_implemented_not_authorized_for_claude`

本 runner 实现已批准的 bundle-only 两阶段交接，但不会自行调用 Claude、注入凭据、选择正式场景或授权开始评估。它生成的旧 Docker plan 仍是离线准备证据；正式命令、凭据与代理拓扑由独立的 [受控执行器](reviewer-execution.md) 管理，并在最终启动门批准前 fail closed。

## 状态机

| 状态 | 含义 | 允许的下一步 |
| --- | --- | --- |
| `phase1_prepared` | bundle allowlist 和哈希通过校验，并已复制进运行目录 | 将 reviewer JSON 输出写入隔离输出目录，然后封存 |
| `phase1_sealed` | 已验证输出形成只读副本并记录 SHA-256 | 在 reviewer 不可见的位置校验并暂存拟释放的第二阶段材料 |
| `phase2_staged` | 固定矩阵与脱敏结果已冻结，并生成完整性 manifest | Security Engineer 可以明确授权这些准确输入 |
| `phase2_authorized` | 授权记录绑定批准人、理由、第一阶段哈希和 staging manifest 哈希 | 释放已暂存输入 |
| `phase2_released` | 第二阶段复合输入与完整性 manifest 已生成 | 未来运行 reviewer 前再次验证哈希链 |

运行数据默认写入 Git 忽略的 `.local/reviewer-runs/`。

## 准备第一阶段

```text
python -m reviewer.runner prepare \
  --bundle .local/reviewer-bundles/<scenario-id> \
  --run-id <review-run-id>
```

准备过程会拒绝未知或多余文件、缺失哈希、内容变化、符号链接、不安全相对路径，以及缺少 v2.0 访问模型 manifest 的 bundle。验证通过后，bundle 被复制到 `phase1/input/`，所有输入文件标记为只读。

`phase1/docker-plan.json` 描述受限容器边界：

- 只有 `phase1/input/` 以只读方式挂载到 `/review/input`。
- 只有 `phase1/reviewer-output/` 可写挂载到 `/review/output`。
- 不挂载源仓库。
- 容器根文件系统只读。
- 删除 Linux capabilities，并启用 `no-new-privileges`。
- 限制 CPU、内存和进程数。
- 禁用网络与凭据注入。
- 以非 root UID/GID `10001:10001` 运行，并为临时 Claude 配置和 `/tmp` 创建受限 tmpfs。

镜像定义位于 `reviewer/runtime/`，固定基础镜像摘要、Claude Code 版本和 npm 包完整性。以下命令构建镜像并执行无凭据、无网络 smoke test：

```text
python -m scripts.reviewer_runtime_smoke
```

Smoke test 使用镜像 ID 而不是可变 tag 启动容器，检查版本、非 root 身份、输入只读、输出可写、根文件系统只读、临时配置可写、没有默认网络路由且不存在 Claude/Anthropic 凭据环境变量。结果写入 Git 忽略的 `.local/reviewer-runtime/`。这只证明运行时基础隔离，不是正式 Claude 命令或评估授权；每个 Docker plan 仍保留 `<approved-reviewer-command>`。

## 封存第一阶段

Reviewer submission 必须是 `phase1/reviewer-output/` 内的 JSON，并包含已批准 manifest 要求的 decision path、独立测试矩阵和 limitations/unexecuted-tests 列表。

```text
python -m reviewer.runner seal-phase1 \
  --run .local/reviewer-runs/<review-run-id> \
  --submission .local/reviewer-runs/<review-run-id>/phase1/reviewer-output/submission.json
```

Runner 将已验证 submission 复制到 `phase1/sealed-output.json`，标记为只读，并把 SHA-256 同时记录到 `phase1/seal.json` 和 run manifest。只读属性用于防止误改；哈希链才是篡改检测控制。

## 授权并释放第二阶段

先校验并暂存拟释放的准确材料。暂存区只供操作者使用，不会向 reviewer 开放：

```text
python -m reviewer.runner stage-phase2 \
  --run .local/reviewer-runs/<review-run-id> \
  --permissions fixtures/permissions.v1.json \
  --results reports/local/<run-id>/report.json
```

随后由 Security Engineer 明确授权，必须同时提供批准人和理由：

```text
python -m reviewer.runner authorize-phase2 \
  --run .local/reviewer-runs/<review-run-id> \
  --approved-by project_owner \
  --reason "Phase 1 output reviewed and frozen"
```

该本地记录是可审计的人工声明，不是密码学身份认证。它同时绑定第一阶段哈希和准确的 staging manifest 哈希。释放前，runner 会重新验证 bundle、第一阶段输出、seal、暂存输入、授权记录及全部引用哈希。

```text
python -m reviewer.runner release-phase2 \
  --run .local/reviewer-runs/<review-run-id>
```

第二阶段输入包含原 bundle、已封存第一阶段输出、固定权限矩阵、脱敏确定性结果和 release manifest。原始 bearer 值、凭据、用户资料值或 raw response body 等敏感结果字段会被拒绝。

## 完整性验证

```text
python -m reviewer.runner verify --run .local/reviewer-runs/<review-run-id>
```

验证会按当前状态检查可用的完整哈希链。准备后的 bundle、封存输出、暂存输入、授权记录或第二阶段文件有任何改动都会失败。

审批记录中的正式启动门槛仍未关闭。代码、fixture 与中性 scenario 已形成经过 attestation 验证的冻结候选，但尚未授权正式评估。[Claude 运行时准备审计](claude-runtime.md)记录整体状态；[受控执行器](reviewer-execution.md)已经把运行时、secret-file 凭据路径和[受限出口](reviewer-egress.md)组合验证。旧 Docker plan 继续强制 `--network none`，正式执行器则在最终启动门批准前拒绝运行。
