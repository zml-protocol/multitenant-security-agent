# Project Vision and Dual-Workflow Roadmap

English | [中文](project-vision.md)

This document defines the long-term goal. `spec.en.md` v0.1 is the initial requirements baseline, and `docs/phase1.en.md` describes the completed first local phase. Neither represents the entire final architecture.

## Core Goal

Build a controlled, repeatable, and auditable security lab on Alibaba Cloud, using one multi-tenant application to complete two end-to-end workflows:

1. A white-box, human-in-the-loop AppSec AI-assisted Security Assessment.
2. DDoS / Network Security Incident Response.

The project is not intended to prove that AI can independently find every vulnerability, nor does it allow a model to control production or cloud security configuration directly. It demonstrates how a Security Engineer defines the problem, constrains tools, verifies evidence, approves actions, and remains responsible for final decisions, while extending Web/API security experience into cloud security, network security, and DDoS detection and response.

The project owner must ultimately be able to explain every trust boundary, control point, evidence chain, decision basis, mitigation, recovery validation, and limitation without relying on an Agent to provide the explanation in real time.

## Workflow 1: AppSec AI Agent Flow

This simulates a formal white-box Product Security Assessment rather than an automated black-box scan.

### Roles and Responsibilities

| Role | Responsibilities | Responsibilities it must not replace |
| --- | --- | --- |
| Security Engineer (project owner) | Defines business context, scope, actors, assets, trust boundaries, security requirements, and expected behavior; reviews evidence; decides whether a finding is valid and determines impact and severity; approves remediation; accepts regression results | Must not delegate final risk decisions to a model |
| Claude (independent reviewer) | Reads code; traces authentication and authorization decision paths; generates a test matrix from independent requirements; executes or proposes negative tests; collects and cites evidence; drafts findings | Must not change the requirements, directly approve a fix, or independently decide final severity |
| Codex (implementer) | Implements the application and test tools; fixes confirmed findings; adds regression tests; maintains deployment and repeatable experiments | Must not use its own implementation logic as an independent test oracle or accept risk for the Security Engineer |

Claude and Codex retain separate reviewer and implementer responsibilities. Their outputs are reviewable material, not authoritative conclusions.

### Complete Flow

1. The Security Engineer writes an assessment brief covering the business, data classification, actors, assets, entry points, trust boundaries, threats, explicit scope, and prohibited actions.
2. Security requirements and expected behavior are versioned as an independent test oracle.
3. Claude reads the code and produces an authentication/authorization decision path identifying identity sources, tenant context, policy decisions, object queries, and response points.
4. Claude generates positive and negative test cases from the requirements rather than from the application authorization function.
5. Tests run within a fixed target, known identities, read-only or controlled operations, and a request budget, recording run IDs, case IDs, request IDs, and redacted evidence.
6. Results distinguish confirmed findings, functional anomalies, inconclusive results, and no violation observed. An HTTP status alone is not authorization evidence.
7. Claude drafts a finding with the requirement, prerequisites, reproduction, evidence, impact, possible root cause, recommendation, and limitations.
8. The Security Engineer verifies the evidence, confirms or rejects the finding, and decides its impact and severity.
9. Codex implements remediation and necessary regression tests within the confirmed scope.
10. The same fixture, identity map, authorization version, and cases are rerun, verifying that the violation disappears and legitimate behavior still works.
11. The Security Engineer completes the assessment report and the risk acceptance or closure record.

### Final Evidence Package

- Assessment brief and data-flow/trust-boundary diagram.
- Authentication/authorization decision path.
- Independent, versioned security requirements and test matrix.
- Redacted raw-evidence references, draft findings, and human decision records.
- Remediation diff, regression results, and before/after comparison.
- Agent tool boundaries, call budgets, failure modes, and audit records.

## Workflow 2: DDoS / Network Security Incident Response Flow

The same application is deployed to Alibaba Cloud and gradually evolves into a lab using ALB, ECS, RDS, and SLS, with WAF, Anti-DDoS, and ActionTrail added by phase when justified. Every test targets owned and explicitly authorized resources and has limits for traffic, duration, concurrency, and stop conditions.

### Scenario Levels

| Scenario | Preferred implementation | Primary observations |
| --- | --- | --- |
| HTTP Flood | Controlled, low-intensity load test against the owned environment, with a simultaneous healthy probe | L7 request rate, URI/source patterns, ALB/WAF/application status, 429/5xx, latency, and business impact |
| SYN/UDP Flood | Prefer synthetic telemetry, prepared logs, or an approved cloud-provider exercise; any real packet test requires separate review and strict bounds | L4 protocol, connection/packet rate, loss, host and perimeter metrics, and what an absence of L7 logs means |
| Compromised ECS outbound attack | Synthetic logs or controlled egress simulation in an isolated target; never attack an Internet third party | Abnormal outbound connections, process/host indicators, VPC/host logs, credential and configuration changes, containment, and evidence preservation |

SYN/UDP and outbound scenarios cannot be concluded from HTTP access logs alone. The design must identify which observations come from real traffic, synthetic telemetry, or an analytical hypothesis.

### Complete Flow

1. Establish a healthy baseline: request rate, connections, errors, p50/p95/p99, resource use, database connections, and healthy probes.
2. Detect an anomaly through an alert or synthetic event, recording the incident ID, timeline, and triggering rule.
3. Collect currently available telemetry from ALB, WAF, Anti-DDoS, SLS, ECS, RDS, VPC/network sources, and ActionTrail, recording each source and gap.
4. Decide whether the anomaly is L4, L7, an application failure, a configuration change, or inconclusive. No single metric is sufficient by itself.
5. Analyze the pattern: target, protocol/method, URI, source distribution, rate, connection behavior, timing, and business impact.
6. Within bounded read-only tools, an AI Agent correlates evidence, proposes hypotheses and candidate mitigations, cites real evidence IDs, and states uncertainty.
7. The Security Engineer reviews impact, collateral risk, rollback conditions, and the exact action, then provides human approval.
8. A restricted executor performs only predefined actions bound to the incident ID and expiry. A model cannot execute arbitrary shell commands or directly edit cloud configuration.
9. Validate attack-side metrics, healthy probes, errors, latency, capacity, and business behavior together. Seeing a 429 alone does not prove recovery.
10. Human approval is required for restoration or rollback, followed by confirmation that configuration returned to the expected state.
11. Produce a post-incident report covering detection, evidence, analysis, decisions, mitigation, recovery, timeline, gaps, and follow-up work.

### Safety and Authenticity Principles

- Never send attack traffic to third parties, perform unauthorized scanning, exhaust real Internet bandwidth, or simulate an Internet outbound attack against another party.
- Every real load test has a target allowlist, maximum request count, RPS, concurrency, duration, stop conditions, and healthy probe.
- Synthetic data is marked `synthetic=true` and counted separately from real access logs.
- Complete local and offline validation before creating paid resources; verify current Alibaba Cloud pricing, region, quota, and logging cost before creation.
- Cloud actions use least privilege, short-lived credentials, and auditing. The test Agent and response executor remain separate.
- State capability boundaries explicitly: application logs cannot prove network-layer DDoS detection, and a single-node lab cannot prove production capacity or protection effectiveness.

## Phased Implementation Roadmap

| Phase | Goal | Completion criterion |
| --- | --- | --- |
| 1 | Local multi-tenant application, fixed authorization matrix, and three isolated vulnerable modes | Complete: secure mode passes 54 checks; vulnerable modes consistently produce 8/18/4 findings and are retested with the same fixture |
| 2 | Formal AppSec assessment artifacts and an independent reviewer workflow | Complete assessment brief, decision path, Claude test matrix, human finding decisions, Codex remediation, and regression evidence |
| 3 | Local containerization, NGINX/application logging, observability, and read-only Agent tools | Pass log-correlation, prompt-injection/tool-boundary, unavailable-model, and budget scenarios |
| 4 | Alibaba Cloud foundation | Repeatable minimum ALB/ECS/RDS/SLS architecture with documented network, identity, secret, backup, and cost controls |
| 5 | L7 incident flow | Complete the controlled HTTP Flood workflow from detection through post-incident report, with auditable human approval and recovery |
| 6 | L4 and compromised-host exercises | Complete SYN/UDP and outbound scenarios through synthetic or approved isolated methods and explain telemetry differences and investigation limits |
| 7 | Protection components and final demonstration | Add WAF, Anti-DDoS, and ActionTrail as justified; produce dual-workflow demos, architecture diagrams, reports, and three-minute/deep-dive narratives |

Each phase defines acceptance criteria before implementation. Cloud components are selected according to the security question they answer, with a record of why the telemetry or control is needed, rather than to accumulate product names.

## Project Narrative

The project is not intended to say, “I let AI do security for me.” Its intended message is:

> I can translate security requirements into executable and auditable validation; coordinate different Agents within explicit roles and tool boundaries; keep humans responsible for verifying evidence and approving remediation and response; and apply the same evidence discipline from AppSec to cloud and network incident response.
