# AppSec v1 Remediation Record

English | [中文](remediation-record.md)

- Branch: `remediation/v1`
- Finding: `F1`
- Finding status: `confirmed`
- Severity: `pending_security_engineer`
- Frozen vulnerable baseline: `14a7b48ae30b833962752e4d65b7e03ade5664a1`
- Fixture: `fixture-256eb13b57860e22`
- Machine-readable regression evidence: [regression-evidence.json](regression-evidence.json)

## Problem

In the frozen version, `GET /api/users/{user_id}` returned `403 Forbidden` for an existing cross-tenant object and `404 Not found` for a nonexistent object. An unauthorized authenticated actor could use the difference to determine whether a cross-tenant user ID existed.

## Fix

`app/main.py` continues to enforce the existing authorization policy. When the policy returns `tenant_boundary`, the client now receives the same `404 Not found` response as an unknown object. A same-tenant owner restriction still returns `403 Forbidden`. Server audit logs retain the internal `tenant_boundary` or `unknown_user` reason for investigation and troubleshooting.

The independent scanner oracle now reflects the approved expected behavior: a cross-tenant detail denial expects `404 Not found`, while an unauthorized same-tenant detail request still expects `403 Forbidden`.

## Design rationale

The change normalizes only the externally visible denial. It grants no additional access, changes no successful response field, and preserves internal audit reasons. This directly removes F1's distinguishing signal with a minimal implementation change.

## Regression result

Using the same fixture as the frozen assessment:

| Case | Before | After | Audit reason |
| --- | --- | --- | --- |
| Known cross-tenant object | `403 Forbidden` | `404 Not found` | `tenant_boundary` |
| Nonexistent object | `404 Not found` | `404 Not found` | `unknown_user` |

- Status codes equal: yes
- Generic error bodies equal: yes
- Protected-profile disclosure: no
- Fixed permission matrix: 54/54 passed
- Confirmed violations: 0
- Functional anomalies: 0

The `appsec-v1-fixed` tag has not been created. It may be created only after the Security Engineer accepts this remediation.
