# AppSec v1 Remediation Acceptance

English | [中文](remediation-acceptance.md)

- Finding: `F1`
- Finding status: `confirmed`
- Final severity: `Low`
- Claude verification: `remediation_verified`
- Security Engineer decision: `remediation_accepted`
- Accepted at: `2026-09-20T04:26:22.430Z`
- Vulnerable version: `14a7b48ae30b833962752e4d65b7e03ade5664a1`
- Fixed version: `84396352268b34a407c2ac2f27602e09c2d55eaa`

The Security Engineer accepts Claude's independent static remediation-verification recommendation and its recorded limitations. The F1 fix satisfies the approved expected behavior: for an unauthorized caller, an existing cross-tenant object and a nonexistent object have the same external status and generic body, neither returns a protected profile, and the server retains distinct internal audit reasons.

Severity is `Low` because exploitation requires an authenticated actor, reveals object existence only, does not enable a cross-tenant profile read, and discloses no name, email address, phone number, or credential.

Claude's original verification outputs are preserved under [claude-verification-v1/raw](claude-verification-v1/raw). Their sizes and SHA-256 digests are recorded in [verification-manifest.json](claude-verification-v1/verification-manifest.json). The raw outputs must remain unchanged.

Accepted limitations include the single actor/target combination in the dedicated regression, test-harness files omitted from Claude's allowlist, the fixed permission matrix's lack of a nonexistent-object case, and Claude's static review of supplied dynamic evidence rather than fresh execution during the verification session. These limitations do not block F1 remediation acceptance.

Creation of the annotated `appsec-v1-fixed` tag on the fixed-code commit is approved. The `assessment/v1-vulnerable` branch and `appsec-v1-vulnerable` tag must remain unchanged.
