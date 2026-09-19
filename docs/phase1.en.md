# Phase 1 Implementation, Verification, and Interview Narrative

English | [中文](phase1.md)

This document describes the completed local phase. `spec.en.md` preserves the original requirements baseline. No cloud resources were created, no paid model was called, and nothing was pushed to a remote repository.

## Stage 1: A Reproducible Application and Identity Boundary

The application uses FastAPI and SQLite. It has fixed tenants A and B, with two ordinary users and one administrator in each tenant. A data seed generates user IDs and synthetic names, email addresses, and phone placeholders; `fixture_id` is a digest of the data. High-entropy bearer tokens are independently generated with `secrets.token_urlsafe(32)` and cannot be derived from the data seed. The database stores SHA-256 token digests, while client credentials exist only in a local file ignored by Git.

The server maps tokens to users, roles, and tenants. It does not trust `X-Tenant-ID`, `X-Role`, or `X-User-ID`. SQLite is opened read-only, all queries are parameterized, and every query connection is closed. The only business endpoints are `/api/me`, `/api/users/{user_id}`, and `/api/users`. Successful responses select only public business fields and exclude token digests; denied responses contain generic errors only.

Verification covers missing and invalid authentication, spoofed identity headers, unknown IDs, SQL-injection-shaped IDs, rejection of write methods, and an unchanged database. The lab demonstrates authorization boundaries; it does not claim production authentication, token lifecycle management, or key management.

Interview explanation: “I separate authentication from resource authorization. The server first establishes the subject through its credential mapping, then decides whether that subject may read the target object. A tenant claim supplied by the client cannot act as an authorization fact.”

## Stage 2: Independent Authorization Matrix and Vulnerability Isolation

`fixtures/permissions.v1.json` explicitly lists the objects and lists each identity may read. The test executor neither imports the application authorization function nor reads the vulnerability mode. The normal request template permits only GET and a fixed detail path; the identity and target must be configured and describe an allowed baseline request. Out-of-scope configuration is rejected before a network request is made.

The base matrix has 48 cases: 6×6 detail cases, 6 `/me` cases, and 6 list cases. There are also 3×2 missing/invalid credential checks, counted separately. The application and tests share known test data but do not share authorization logic.

| Mode | Defective control | Expected violation calculation | Boundary that remains intact |
| --- | --- | --- | --- |
| secure | None | 0 | Full authorization model |
| same_tenant_bypass | Same-tenant detail object authorization | 4 ordinary users × 2 other same-tenant users = 8 | Cross-tenant access denied; lists still require an administrator |
| cross_tenant_bypass | Detail tenant boundary | 6 actors × 3 users in the other tenant = 18 | Ordinary same-tenant access to another user remains denied; lists are unchanged |
| list_role_bypass | List role check | 4 ordinary users × 1 list = 4 | The list remains tenant-filtered; detail access is unchanged |

Tests compare the exact set of violating `case_id` values, not only the total count. After each vulnerable mode, secure mode reuses the same database, `fixture_id`, and credentials, and all 54 checks must pass. This is an operator-controlled restoration and regression exercise, not automatic production remediation by an Agent.

Interview explanation: “I break one authorization condition at a time so that the result has an attributable cause. Tenant isolation and object authorization are separate conditions; passing a role check must never let an administrator skip the tenant boundary.”

## Stage 3: Evidence Assessment, Real HTTP, and Log Correlation

The assessor searches responses for the unique synthetic name, email, and phone values from the known snapshot, then determines whether the matched object is allowed for the current request. If a 401, 403, or 500 response contains proven protected data, it is still a violation. A 5xx response, 429, timeout, redirect, or incomplete response with no leak evidence is inconclusive. This ordering prevents an error status from hiding an observed disclosure.

An allowed read must return the complete expected object; a list must contain exactly all allowed objects. If an expected allowed request is denied or incomplete, it is additionally marked as a functional anomaly. A denied request passes only when it returns the expected generic denial. An empty HTTP 200 response is neither a vulnerability nor a pass. Unknown data and disclosures transformed through an unrecognized encoding are not claimed as generally detectable in this phase.

Each result records a run ID, case ID, request ID, evidence ID, identity alias, expectation, status, duration, fixed request path, matched records, and matched field names. Raw tokens, response text, and profile values do not enter reports. The server logs an allowlisted field set only and excludes raw URLs, query strings, authorization headers, and response bodies. An externally supplied correlation ID must be a UUID; otherwise, the server generates a new one so arbitrary strings cannot enter the audit log.

`scripts.smoke` runs a real local Uvicorn service and executes the secure matrix at no more than two requests per second. It checks every request ID, run ID, and status against the server log, verifies that credentials and profile values are absent, then stops the process it started. It will not take over a service already using port 8000.

Interview explanation: “A 200 is only a transport result; an authorization issue needs data evidence. A 403 can also leak. My report separates confirmed violations, no violation observed, and inconclusive results, and uses correlation IDs to connect client evidence with server authorization logs.”

## Verification Record and Boundaries

- Environment: Windows, Python 3.13.5; exact dependency versions are recorded in `requirements.txt`.
- Automated tests: 34 passing tests covering the complete matrix, all three vulnerable modes and secure retests, authorization bypass counterexamples, template boundary enforcement, abnormal result classification, log correlation, and redaction.
- Demo evidence: `reports/local/demo/comparison.json` and each scenario report. All scenarios use one fixture ID; secure mode has 0 violations, the vulnerable modes have 8/18/4, and all three remediation retests return to 0.
- Real HTTP evidence: `reports/local/http-secure/report.json` records 54 passing checks: 48 matrix cases plus 6 authentication cases. Logs are in `.local/smoke-access.log`.
- Starlette TestClient currently emits two third-party deprecation warnings about HTTPX/AnyIO. Functional tests pass; the warnings are not hidden.
- The Codex process could not find a Docker CLI during this run, so Phase 1 was verified with native Python. Container build or Docker verification is not claimed. Container and NGINX deployment remain for a later phase.
- Agent evidence collection, model failure/budget handling, prompt-injection evaluation, SLS, cloud deployment, and human-approved rate limiting and restoration have not been implemented. Reports explicitly identify Agent analysis as unimplemented.

For a three-minute demonstration, first show the authorization table, then run `scripts.demo` to display 0/8/18/4 and the three returns to zero. Finally, open one violating JSON evidence item and explain the actor, target, expectation, matched fields, and post-remediation comparison. The real HTTP check takes about 27 seconds and can be generated before the presentation.
