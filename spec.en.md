# Multi-Tenant Cloud Application Security Testing and Response Agent: Requirements and Behavior Specification

English | [中文](spec.md)

Version: v0.1 | Date: 2026-09-19 | Status: requirements baseline; not yet fully implemented or deployed

This document consolidates confirmed requirements and explicitly marks recommended engineering defaults. It is the project specification, combining product requirements, the Agent behavior contract, and the acceptance plan. It is not evidence that the described work has already been completed.

## 1. Background, Goals, and Definition of Success

This is a personal lab project for an Alibaba Cloud Security Engineer interview. It starts from repetitive authorization validation in practical Web/API penetration testing and demonstrates cloud deployment, testing, reporting, remediation retesting, access monitoring, and incident response.

Goal priority: A. security test automation > B. Agent engineering and security > C. cloud security incident investigation. Version 1 includes the minimum exercise for C. Running in the cloud does not mean the project has validated cloud-infrastructure vulnerabilities or real large-scale DDoS protection.

Core value hypothesis: deterministic tools reduce the work of switching identities, substituting object IDs, and resending requests; the Agent selects supplemental validation when evidence is incomplete or contradictory and organizes the evidence. Evaluation determines whether the Agent adds value; the project does not assume a model is inherently better than a script.

Success criteria: execute the complete known authorization matrix; detect and independently remediate/retest all three seeded vulnerability classes; avoid false security-response conclusions; allow base testing to complete when the model fails; and complete one human-approved rate-limiting and restoration exercise.

## 2. Scope and Non-Goals

### Confirmed scope

- A single Alibaba Cloud ECS instance plus SLS logging; the Agent runs on the operator's computer by default.
- A multi-tenant user information application; tested business operations are GET reads only.
- Start from one known-good request, a test identity inventory, resource ownership, and authorization rules.
- A fixed test matrix, Agent-directed supplemental evidence, and evidence-backed reports.
- Three isolated vulnerable scenarios, a correct implementation, and remediation regression testing.
- Cloud log queries, dashboards, alerts, a synthetic incident exercise, and bounded real-traffic validation.
- Apply a predefined rate limit only after human approval; restoration also requires human approval.

### Excluded

- File upload, file scanning, antivirus, or business write/delete testing.
- Arbitrary-target scanning, brute-force user ID enumeration, or automatically generated attack code.
- Kubernetes, multi-node high availability, a managed database in the initial baseline, paid WAF/Anti-DDoS in the initial baseline, or real bandwidth-exhaustion testing.
- Automatic application remediation, automatic security-group or arbitrary cloud-configuration changes, or direct model execution of shell commands.
- A production identity platform, real user data, or production availability commitments.

## 3. Test Data and Authorization Rules

The initialization script randomly generates user IDs, names, and synthetic personal information. There are exactly two tenants, each with two ordinary users and one tenant administrator, for six users total. Email addresses use `example.com`; real personal information is prohibited.

Testing and remediation retesting preserve one data snapshot, fixture ID, and user mapping. A fixed random seed may generate reproducible non-sensitive data but must never generate real secrets or authentication credentials.

| Identity | Own profile | Other user in same tenant | User in another tenant | User list |
| --- | --- | --- | --- | --- |
| Ordinary user | Allow | Deny | Deny | Deny |
| Tenant administrator | Allow | Allow | Deny | Current tenant only |

A tenant administrator has no global platform authority. Test expectations are read from an independent test configuration and do not reuse the application authorization function as the test oracle.

## 4. Application Endpoints and Vulnerability Modes

| Endpoint | Behavior |
| --- | --- |
| `GET /api/me` | Current authenticated user's profile and identity baseline |
| `GET /api/users/{user_id}` | Return the target user according to the authorization rules |
| `GET /api/users` | Tenant administrators only; return users in the current tenant |

Recommended user fields: `user_id`, `tenant_id`, `role`, `name`, `email`, and `phone`. Error responses must not return protected personal data. Identity and tenant are obtained from server-validated credential mappings, never from client-declared tenant headers.

Recommended authentication default: the lab uses independently generated, high-entropy opaque bearer tokens mapped to users on the server; only the execution tool reads the credentials. If JWT is introduced later, signature, expiration, issuer, and audience validation must be specified separately. Authentication bypass is not a seeded vulnerability in this project.

| Mode | Seeded defect | Controls that remain intact |
| --- | --- | --- |
| secure | No seeded authorization defect | Enforce the complete authorization model |
| same_tenant_bypass | An ordinary user can read another user in the same tenant | Cross-tenant access remains denied |
| cross_tenant_bypass | The detail endpoint allows any authenticated actor to read a user in another tenant | An ordinary user still cannot read another same-tenant user, enabling independent attribution |
| list_role_bypass | An ordinary user can read the current tenant's user list | The list remains tenant-filtered |

The operator selects a mode through controlled deployment configuration. There is no public mode-switch endpoint, and the Agent does not switch modes. Vulnerable modes are limited to an isolated lab. Additional evaluation fixtures cover an HTTP 200 response with no protected data, timeouts, and 429 responses without adding new business endpoints.

## 5. Fixed Test Executor

FR-01: Accept a target base URL, known-good request template, identity aliases, test-user inventory, and versioned authorization rules. Before execution, verify that the target and endpoint are allowlisted.

FR-02: Each of six identities accesses all six user details, producing 36 detail cases; add six `/me` baseline cases and six list cases for 48 base cases total. Missing and invalid credential checks for all three endpoints are counted separately.

FR-03: Record the run ID, case ID, identity alias, expectation, redacted request, status, response summary, evidence reference, and duration for every call. Use correlation IDs to connect client evidence to server logs.

FR-04: If a forbidden request returns the target's protected data, classify it as a confirmed violation. HTTP 200 alone is not vulnerability evidence. A denial status containing protected data must also be detected. List responses require both role validation and ownership validation for every returned item.

FR-05: If an expected allowed request is denied, mark a functional/authentication anomaly and do not count it as a pass. A timeout, 429, 5xx, or missing evidence is inconclusive and cannot prove authorization is correct. A missing log entry also cannot prove the request did not execute.

FR-06: Base execution does not depend on a model. If the model is unavailable, deterministic results and a template report are still produced, explicitly stating that Agent analysis did not complete.

## 6. Agent Behavior Contract

### Inputs and responsibilities

Inputs are authorization rules, a non-sensitive user mapping, redacted test evidence, and tool definitions. The model cannot see raw tokens, cloud credentials, evidence from another run, or the vulnerability-mode ground-truth answer. The evaluator retains ground-truth labels separately.

For incomplete or contradictory evidence, the Agent may recheck the identity baseline, compare an allowed reference response, send supplemental requests within approved endpoints and known users, and query logs by correlation ID. A deterministic conclusion does not require another model call.

### Tools and execution boundaries

| Suggested tool | Purpose | Constraint |
| --- | --- | --- |
| `inspect_evidence` | Read existing evidence | Current run only; redacted |
| `verify_identity` | Query `/me` | Configured identity aliases only |
| `send_read_request` | GET an approved endpoint | Fixed target, path templates, and known IDs; no arbitrary URL |
| `query_access_logs` | Obtain server-side evidence | Bounded query templates, time window, and result count |
| `submit_assessment` | Submit a structured conclusion | Must cite valid evidence IDs |

Recommended engineering defaults: no more than five supplemental tool calls per anomaly; no more than thirty supplemental calls per run; ten-second request timeout; at most two requests per second and concurrency two; configurable budgets for model input, output, and total tokens. Reaching any limit stops supplemental evidence gathering and records the unresolved reason. Values may be adjusted after local validation, with the change recorded.

The tool layer injects credentials. Automatic cross-target redirects are disabled. Targets, protocols, methods, or unknown users proposed by the model are rejected. Local targets are also limited to explicitly configured local endpoints.

Responses and logs are untrusted data. Instructions embedded in them cannot change rules, access secrets, or trigger response actions. The tool layer enforces restrictions independently of prompts.

Conclusion categories are `confirmed_violation`, `no_violation_observed`, and `inconclusive`; functional/authentication anomalies are recorded separately. `no_violation_observed` applies only to the executed scope and is not a claim that the application is secure overall.

Record the selected action, a short rationale, summarized tool parameters, observations, and evidence. Do not store the model's private chain of thought.

## 7. Report Specification

Recommended outputs are a human-readable Markdown report and structured JSON. Include scope and environment, version/fixture ID, execution coverage, omissions and limitations, anomaly classes, finding details, expected and actual behavior, redacted reproduction, evidence IDs, impact, remediation recommendation, before/after comparison, model version, and tool-call cost.

A confirmed vulnerability must cite actual evidence. If severity is a preliminary human/model assessment, state its basis and do not invent an exact uncalculated CVSS score. Never fabricate requests, logs, or remediation results. Mask displayed fields while retaining enough user/tenant test IDs for verification. Secrets must never enter reports.

## 8. Logging, Monitoring, and Incident Exercise

NGINX and the application emit structured logs to SLS. Recommended fields: timestamp, request ID, run ID, route template, method, status, duration, response bytes, source IP, authenticated identity alias/tenant, target user ID, authorization decision, and reason. Never log Authorization, tokens, complete profile responses, or real personal information. Mark unauthenticated identity as `unknown` and do not trust identity claimed by a request.

Dashboards cover request rate, status codes, p95 latency, authorization denials, 429, and 5xx. Prioritize HTTP access logs and service metrics; do not claim full packet capture or network-layer DDoS detection.

Separate real access logs from synthetic attack logs by Logstore or an equivalent boundary, and mark synthetic events with `synthetic=true`. Synthetic alerts enter exercise incidents only and cannot directly trigger a real defensive action.

Recommended engineering defaults: no more than 300 total requests in a real-request exercise, peak no greater than five per second, concurrency no greater than two. Set a predefined rate limit low enough to observe 429 on a dedicated exercise scope. Run a normal low-rate probe simultaneously to detect collateral impact; calibrate final rates and thresholds against a healthy baseline. Stop immediately on sustained 5xx or clear health degradation.

Exercise sequence: healthy baseline → synthetic anomalous logs trigger an exercise alert → Agent queries evidence and proposes hypotheses/recommendations → operator approves a specific policy → restricted executor enables the predefined rate limit → low-volume validation checks 429, the healthy probe, and latency → human approves restoration → validate and produce an incident timeline.

The response executor is separate from the test tool. Approval binds the incident ID, policy ID, target, expiry, and exact action; approval and execution results are audited. Unapproved, denied, or expired requests cannot change configuration. Restoration uses the recorded prior configuration. A model cannot directly change security groups, execute shell commands, or write arbitrary NGINX configuration.

A 429 alone does not prove mitigation succeeded. Healthy probes, errors, and latency must also be checked. Reports distinguish synthetic alerts, real validation, and inferred conclusions and never claim a real distributed attack, traffic scrubbing, or capacity test was completed.

## 9. Architecture and Engineering Recommendations

Deployment: one ECS runs NGINX, the multi-tenant API, and local storage; SLS collects logs; the Agent, reporting, and controlled test client run locally; the model is called through an API. All tenants share an application instance and rely on application authorization for isolation.

Recommended implementation: Python, FastAPI, SQLite, NGINX, and Docker Compose. The Agent uses native model tool calling and an explicit execution loop. Framework and versions are verified during implementation and are not claimed as selected or installed merely because they appear here.

Restrict SSH and lab entry points to operator sources. Do not expose the database publicly. Vulnerable modes are enabled only in designated test windows. Manage model and cloud credentials separately. SLS queries use minimum read-only access, and the test Agent has no cloud administration authority. Configure TLS or a protected tunnel before sending real credentials.

Engineering defaults: seven-day log retention; retain only redacted raw evidence. Configure budget reminders plus log and tool-call limits. Cloud charges remain subject to the purchase page and actual usage; a reminder is not a hard spending stop.

## 10. Acceptance Scenarios

| ID | Given / When | Required result |
| --- | --- | --- |
| AC-01 | Run the base matrix in secure mode | All 48 cases have results and match the authorization rules; anomalies cannot count as passes |
| AC-02 | Enable each of the three vulnerable modes separately | Detect each expected violation with reproducible evidence and do not confuse its source |
| AC-03 | Retest remediation with the same data and tests | Violations disappear while previously valid access still works |
| AC-04 | 200-empty, disclosure-in-error, 429, and timeout fixtures | Do not infer a vulnerability from an empty 200; detect the disclosure; preserve inconclusive results |
| AC-05 | Ordinary user and administrator call the list | Check function authorization and tenant filtering; any cross-tenant item is a violation |
| AC-06 | Missing or invalid credentials | Deny correctly without returning protected data |
| AC-07 | Model unavailable or budget exhausted | Base tests and report still complete and identify incomplete supplemental analysis |
| AC-08 | Malicious instructions in content or out-of-bounds tool parameters | Do not expose credentials; execution layer rejects the request and records the rejection |
| AC-09 | Agent submits an invalid evidence reference | Validation fails and the claim cannot be published as a confirmed finding |
| AC-10 | Correlate one real test with logs | Find the log by correlation ID; logs and reports contain no secrets |
| AC-11 | Synthetic anomalous event | Trigger a clearly labeled exercise alert counted separately from real traffic |
| AC-12 | Rate-limit request is unapproved, denied, or expired | Configuration remains unchanged |
| AC-13 | Approved rate-limit action and restoration | Audit records exist; 429 and healthy probes are visible; restored behavior matches the prior configuration |

Coverage is executed planned matrix items divided by planned matrix items; unexecuted and inconclusive results are counted separately. Evaluation compares the script baseline with Agent-assisted results across false positives, false negatives, unresolved cases, calls, duration, and manual steps. Report numbers only for the finite fixtures and do not generalize a detection rate to all applications. Run at least three repetitions to observe model variance and report honestly if there is no improvement.

## 11. Deliverables, Implementation, and Time Boundary

Deliverables: this specification; application and fixed-test code; Agent and tools; evaluation fixtures; deployment instructions; SLS queries and alert configuration; sample report and remediation comparison; incident exercise record; and a three-minute demo narrative. At the original v0.1 baseline, only this specification existed.

Implementation order: local secure version and authorization matrix → isolated vulnerability modes and remediation validation → Agent supplemental evidence → cloud deployment and logging → human-approved response exercise → end-to-end acceptance and narrative.

The earlier estimate was 12–18 hours of effective work, not a guarantee. New-account activation, region capacity, and troubleshooting may add time. Prioritize the core A/B capabilities and minimum C exercise, limit interface decoration, and preserve time to prepare the interview narrative.

The planning cloud budget remains approximately USD 20–35 for 72 hours before tax, with an upper planning estimate around USD 36. This is neither a confirmed quote nor a hard spending cap. Verify the exact region, ECS SKU, model, and account availability before resource creation. After the demo, check and release unused instances, disks, public IPs, and logging resources.

## 12. Files, Versioning, and Secret Management

The original specification was downloaded from the conversation and persisted in the local project directory. At the original baseline, no GitHub repository, user-computer project implementation, or Alibaba Cloud resource had yet been created.

The recommended source of truth is the `multitenant-security-agent` directory on the operator's computer plus a private Git repository. Alibaba Cloud holds only deployment copies and runtime logs. Once a remote repository exists, it becomes the code version reference; do not treat a temporary worktree copy as the sole backup.

Recommended directories: `spec.md`, `app/`, `agent/`, `tests/`, `fixtures/`, `infra/`, `docs/`, and `reports/`. This is a plan, not a claim that every directory already exists.

Do not commit `.env`, API keys, cloud AccessKeys, test bearer tokens, or unredacted logs. It is acceptable to commit `.env.example`, synthetic test data, and redacted sample reports. Keep data seeding separate from credential generation.

## 13. Decision Record and Implementation Checks

Confirmed decisions: option 2; user information business domain; read-only operations; two tenants and six users; start from an existing known-good request; fixed matrix plus Agent supplemental evidence; human approval for rate limiting and restoration.

Recommended implementation defaults: the specific technology stack, authentication mechanism, tool limits, log fields, report format, and evaluation fixtures. These may change based on validation if the change is recorded and does not expand the core scope.

Implementation checks still required at the original baseline: local Python/Docker environment; Alibaba Cloud registration and payment; region, SKU, and full pricing; model tool-call availability; network access method; alert thresholds; and actual probe configuration. These do not require reopening the selected business direction.
