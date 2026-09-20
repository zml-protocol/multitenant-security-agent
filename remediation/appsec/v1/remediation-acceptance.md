# AppSec v1 Remediation Acceptance

[English](remediation-acceptance.en.md) | 中文

- Finding：`F1`
- Finding 状态：`confirmed`
- 最终严重性：`Low`
- Claude verification：`remediation_verified`
- Security Engineer 决定：`remediation_accepted`
- 接受时间：`2026-09-20T04:26:22.430Z`
- 漏洞版本：`14a7b48ae30b833962752e4d65b7e03ade5664a1`
- 修复版本：`84396352268b34a407c2ac2f27602e09c2d55eaa`

Security Engineer 接受 Claude 的独立静态修复验证建议和已记录的限制。F1 的修复满足批准后的 expected behavior：对未经授权的调用者，跨租户已存在对象与不存在对象具有相同的外部状态码和通用错误体，同时不返回 protected profile；服务端仍保留不同的内部审计原因。

严重性定为 `Low`，因为该问题需要已认证 actor，只泄露对象存在性，没有形成跨租户 profile read，也没有泄露姓名、邮箱、电话或凭据。

Claude 原始验收输出保存在 [claude-verification-v1/raw](claude-verification-v1/raw)，其文件大小和 SHA-256 记录在 [verification-manifest.json](claude-verification-v1/verification-manifest.json)。原始输出不得修改。

已接受的限制包括：专项回归只覆盖一个 actor/target 组合；部分 test harness 文件未提供给 Claude；固定权限矩阵本身不包含 nonexistent-object case；Claude 静态审阅了先前提供的动态证据，但没有在验收 session 中重新执行测试。这些限制不阻止 F1 remediation acceptance。

批准在修复代码提交上创建 `appsec-v1-fixed` annotated tag。`assessment/v1-vulnerable` 分支和 `appsec-v1-vulnerable` 标签必须继续保持不变。
