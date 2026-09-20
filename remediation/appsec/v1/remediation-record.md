# AppSec v1 Remediation Record

[English](remediation-record.en.md) | 中文

- 分支：`remediation/v1`
- Finding：`F1`
- Finding 状态：`confirmed`
- 严重性：`Low`
- 冻结漏洞基线：`14a7b48ae30b833962752e4d65b7e03ade5664a1`
- Fixture：`fixture-256eb13b57860e22`
- 机器可读回归证据：[regression-evidence.json](regression-evidence.json)

## 问题

在冻结版本中，`GET /api/users/{user_id}` 对已存在的跨租户对象返回 `403 Forbidden`，对不存在对象返回 `404 Not found`。未经授权的已认证 actor 可以通过该差异判断一个跨租户 user ID 是否存在。

## 修复

`app/main.py` 继续执行原有授权策略。策略返回 `tenant_boundary` 时，客户端现在收到与未知对象相同的 `404 Not found`；同租户 owner restriction 仍返回 `403 Forbidden`。服务端审计日志继续保留 `tenant_boundary` 或 `unknown_user` 的内部原因，以支持调查和排错。

独立 scanner oracle 也已同步为批准后的 expected behavior：跨租户 detail denial 期望 `404 Not found`，同租户未授权 detail denial 仍期望 `403 Forbidden`。

## 为什么这样设计

该变更只规范化外部拒绝结果，不扩大任何 actor 的访问权限，不改变成功响应字段，也不隐藏服务端内部的审计原因。它直接消除 F1 的差异信号，同时保持最小修改范围。

## 回归结果

使用与冻结评估相同的 fixture：

| Case | 修复前 | 修复后 | Audit reason |
| --- | --- | --- | --- |
| 已知跨租户对象 | `403 Forbidden` | `404 Not found` | `tenant_boundary` |
| 不存在对象 | `404 Not found` | `404 Not found` | `unknown_user` |

- 状态码一致：是
- 通用错误体一致：是
- Protected profile 泄露：否
- 固定权限矩阵：54/54 passed
- Confirmed violations：0
- Functional anomalies：0

Claude 已给出 `remediation_verified` 建议，Security Engineer 已将本修复标记为 `remediation_accepted`。最终验收记录见 [remediation-acceptance.md](remediation-acceptance.md)。`appsec-v1-fixed` 标签已获准创建在修复代码提交上。
