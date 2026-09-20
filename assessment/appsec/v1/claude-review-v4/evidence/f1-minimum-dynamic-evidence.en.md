# F1 Minimum Dynamic Evidence

English | [中文](f1-minimum-dynamic-evidence.md)

- Purpose: supplement F1 with runtime evidence
- Scope: local in-process FastAPI `TestClient`
- Application mode: default `secure` policy
- Requests: 2
- Actor: `a_user1` (`tenant_a`)
- Frozen source commit: `14a7b48ae30b833962752e4d65b7e03ade5664a1`
- Fixture: `fixture-256eb13b57860e22`

## Method

The same authenticated low-privilege actor performed two requests:

1. Request a known user object belonging to `tenant_b`.
2. Request a nonexistent user ID.

The evidence retains only status codes, generic error bodies, request IDs, and minimized audit fields. It retains no bearer token, target user ID, or protected profile.

## Results

| Case | HTTP | Generic error | Audit decision | Audit reason |
| --- | ---: | --- | --- | --- |
| Known cross-tenant object | 403 | `Forbidden` | `deny` | `tenant_boundary` |
| Nonexistent object | 404 | `Not found` | `deny` | `unknown_user` |

Both `status_codes_differ` and `error_bodies_differ` are true, so the cross-tenant existence oracle was reproduced in the controlled local runtime.

Both requests were denied. Neither returned a name, email address, phone number, or other protected profile. This evidence proves that object existence can be distinguished; it does not prove a cross-tenant profile read.

## Adjudication status

Based on this evidence, the Security Engineer updated F1 to `confirmed` and authorized entry into `remediation/v1`. Severity remains `pending_security_engineer`.
