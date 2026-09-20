# F1 最小动态证据

[English](f1-minimum-dynamic-evidence.en.md) | 中文

- 目的：补充 F1 的运行时证据
- 范围：本地进程内 FastAPI `TestClient`
- 应用模式：默认 `secure` policy
- 请求数：2
- Actor：`a_user1`（`tenant_a`）
- 冻结 source commit：`14a7b48ae30b833962752e4d65b7e03ade5664a1`
- Fixture：`fixture-256eb13b57860e22`

## 执行方法

使用同一个低权限已认证 actor：

1. 请求一个已知属于 `tenant_b` 的用户对象。
2. 请求一个不存在的用户 ID。

证据只保留状态码、通用错误体、request ID 和脱敏审计字段。没有保留 bearer token、目标 user ID 或 protected profile。

## 结果

| Case | HTTP | 通用错误体 | Audit decision | Audit reason |
| --- | ---: | --- | --- | --- |
| 已知跨租户对象 | 403 | `Forbidden` | `deny` | `tenant_boundary` |
| 不存在对象 | 404 | `Not found` | `deny` | `unknown_user` |

`status_codes_differ=true`，`error_bodies_differ=true`，因此 cross-tenant existence oracle 已在受控本地运行时复现。

两次请求都被拒绝，没有返回姓名、邮箱、电话或其他 protected profile。该证据证明对象存在性可以被区分，但不证明跨租户 profile read。

## 裁决状态

Security Engineer 已根据本证据将 F1 更新为 `confirmed`，并授权进入 `remediation/v1`。严重性仍为 `pending_security_engineer`。
