# Reviewer Bundle 隔离设计

[English](reviewer-bundle.en.md) | 中文

状态：`staged_runner_implemented_not_authorized`

本文描述工作流一中用于 Claude 独立白盒评估的隔离输入。实现已经通过本地测试，但尚未满足 `ready_for_claude_review` 启动门槛，当前生成的 bundle 一律标记为 `draft_not_for_claude`。

## 为什么需要 Bundle

原始实验仓库同时包含安全实现、三个预置缺陷、固定矩阵、测试答案和操作者报告。如果 Claude 直接读取整个仓库，它可以从 `*_bypass` 名称、其他场景分支或测试断言中读取答案，不能证明其 decision-path review 和测试矩阵是独立完成的。

重构后，`app/main.py` 只负责认证、数据读取、响应和审计，并调用统一的 `authorize_list` 与 `authorize_detail` policy 接口。默认 `app/policy.py` 是安全实现。四个评估实现使用中性 scenario ID 管理；显式标签与预期违规数只存在于操作者侧，绝不复制到 reviewer bundle。

## Bundle 内容

每个 bundle 只包含一个中性场景：

- `app/main.py`、`app/seed.py` 和选中的单一 `app/policy.py`。
- 已批准的中英文 assessment brief、机器可读 security requirements 和 reviewer input manifest v2.0。
- 正常请求模板。
- 脱敏 fixture：仅包含 alias、user ID、tenant ID 和 role。
- 中英文 bundle 说明。
- `bundle-manifest.json`：bundle ID、scenario ID、源 commit、工作区是否干净、requirement version、fixture ID、允许读取文件及每个文件的 SHA-256。

明确不包含：

- bearer token、credential 文件、SQLite 数据库或 `.env`。
- name、email、phone 的实际 fixture 值。
- 操作者 scenario 映射、显式漏洞标签和其他 policy 实现。
- `tests/`、`scanner/`、历史报告和历史证据。

## 中性场景与操作者 Truth

中性 ID 没有安全含义。操作者侧映射保存在 `evaluation/operator-truth.json`，供 demo 和 evaluator 使用。该文件和 `evaluation/operator.py` 不进入 bundle。Reviewer 工具最终必须以 bundle manifest 为读取 allowlist，不能给 Claude 任意仓库文件访问权限。

中性 ID 本身不是秘密；需要隔离的是 ID 到场景答案和预期 finding 的映射。

## 构建与完整性

构建命令形式如下；正式场景 ID 要在后续人工选择后提供：

```powershell
.\.venv\Scripts\python.exe -m reviewer.bundle --scenario-id <neutral-scenario-id>
```

默认输出到被 Git 忽略的 `.local/reviewer-bundles/<scenario-id>/`。构建器拒绝：

- 使用 `secure` 或显式漏洞标签代替中性 ID。
- 未知 scenario ID。
- 覆盖已有 bundle，因为这会破坏证据可追溯性。
- bundle 内容出现操作者标签或本地 raw token。

manifest 为所有允许读取文件记录 SHA-256。`bundle_id` 由 scenario ID、源 commit、requirement version、fixture ID 和文件哈希确定。创建时间和工作区 dirty 状态单独记录；正式冻结时必须从干净、已提交的工作区重新构建。

manifest 只是 allowlist 和完整性记录，不是操作系统访问控制。`.local/reviewer-bundle-samples/` 里的 bundle 只供人工审核。正式运行 Claude 时，必须把冻结 bundle 复制到隔离工作区，或作为唯一目录只读挂载到受限容器/执行环境；Claude 进程不能访问源仓库及其父目录。仅靠 prompt 约束文件读取不满足本项目的工具边界要求。

## 两阶段 Reviewer 访问

建议正式 reviewer 工具使用两阶段披露：

1. Decision-path 与独立矩阵阶段：只提供当前 bundle。Claude 先提交并封存 decision path 和测试矩阵。
2. Difference review 阶段：经 Security Engineer 明确授权后，再提供固定权限矩阵与脱敏确定性测试结果，用于比较遗漏和差异、提出补充测试、建立 evidence index 并起草 finding；不允许回写第一阶段结果。

正式 `reviewer-input-manifest.json` v2.0 定义了 bundle-only 访问和两阶段披露边界。它会复制进每个生成的 bundle，使 reviewer 在无法访问源仓库的前提下获得已批准规则。本地 runner 现已实现 bundle 校验与隔离复制、受限离线 Docker 计划、第一阶段输出封存，以及绑定完整性与人工授权记录的第二阶段释放门禁。详见 [Reviewer Runner](reviewer-runner.md)。本次实现不授权启动 Claude，也不选择正式场景。

## 已验证行为

- 四个中性 scenario bundle 经相同固定矩阵执行，结果仍为 0、8、18、4 个确认违规。
- 每个 bundle 只有一个 policy 实现，且不含显式漏洞标签。
- 脱敏 fixture 不含 name、email、phone 或 token。
- 每个 manifest 文件哈希都与实际内容一致。
- 未知 ID、显式标签和重复输出目录会被拒绝。

这些验证只证明打包和隔离实现符合当前设计，不等于 Claude 已完成评估，也不等于任何 finding 已由 Security Engineer 确认。
