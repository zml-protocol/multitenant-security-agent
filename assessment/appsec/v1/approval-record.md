# AppSec Assessment v1 审批记录

[English](approval-record.en.md) | 中文

这是工作流一的唯一正式确认位置。请先阅读关联文件，并将不准确的内容直接改回源文件；不要只在本记录中写例外。所有决定确认、代码与 fixture 冻结、版本信息填写完整后，才允许 Claude 开始正式评估。

## 关联文件

- [Assessment Brief](assessment-brief.md)：业务、actor、asset、trust boundary、范围、测试约束和证据标准。
- [Security Requirements](security-requirements.json)：Claude 和确定性工具使用的机器可读安全需求。
- [Reviewer Input Manifest](reviewer-input-manifest.json)：Claude 可以读取的输入、禁止读取的内容和必须交付的输出。
- [权限矩阵](../../../fixtures/permissions.v1.json)：六个身份的对象和列表预期。
- [正常请求模板](../../../fixtures/request-template.v1.json)：评估起点请求。

## 1. 审批元数据

| 字段 | 值 |
| --- | --- |
| approval_status | `requirements_approved` |
| approver | `project_owner` |
| approved_at_utc | `2026-09-19T18:42:29Z` |
| requirement_version | `appsec-v1.0` |
| git_commit | `14a7b48ae30b833962752e4d65b7e03ade5664a1` |
| fixture_id | `fixture-256eb13b57860e22` |
| assessment_scenario_id | `scenario-7f3a` |
| candidate_bundle_id | `bundle-6a1a247aca19153c0d22` |
| candidate_generated_at_utc | `2026-09-19T20:44:40.966113Z` |
| candidate_validated_at_utc | `2026-09-19T22:54:07.417730Z` |
| candidate_status | `validated_waiting_formal_start_approval` |
| candidate_attestation | `formal-candidate-attestation.json` |
| candidate_attestation_sha256 | `8a2d419e75754557c8ef61e03dd52b8acd8882d92d9bd53bde764b73e86272bb` |
| formal_start_approval_package | `formal-start-approval-package.json` |
| formal_start_approval_package_sha256 | `fe0b63ffdd00aa5c3b7d44f95615e2aef7cc7570092fe7eefe4add17c8f0059b` |
| bundle_manifest_sha256 | `69049b3e03d58c6742bcd475bdc090465aef3b510c2f6ae4134efad3507fc7be` |
| approved_auth_budget_subject_sha256 | `a764deb46e1b106be04a34548f6b179a22e0c2dfcefa34f2650606b28f5df3b4` |

### 冻结 Git 引用

| 引用 | 目标 commit | 修改规则 |
| --- | --- | --- |
| `assessment/v1-vulnerable` | `14a7b48ae30b833962752e4d65b7e03ade5664a1` | 冻结；不得提交、删除、force push 或移动引用 |
| `appsec-v1-vulnerable` | annotated tag 解引用后为 `14a7b48ae30b833962752e4d65b7e03ade5664a1` | 不可变的漏洞应用版本标记 |
| `remediation/v1` | 初始为 `14a7b48ae30b833962752e4d65b7e03ade5664a1` | 只有 Security Engineer 确认 finding 后才允许写入 |
| `appsec-v1-fixed` | 尚未创建 | 仅在修复回归和人工验收完成后创建 |

GitHub 对 repository rulesets 和经典 branch protection 都返回 HTTP 403，原因是当前免费计划下的 private repository 不支持这些保护。仓库没有改为 public，也没有创建付费计划。在平台强制保护可用前，使用 annotated tag、禁止修改的流程规则和显式远端 SHA 校验作为冻结控制。

当前电脑还安装了本地 `.git/hooks/pre-push` guard，用于拒绝删除或移动 `assessment/v1-vulnerable` 和 `appsec-v1-vulnerable`。测试已确认：引用保持不变时允许通过，删除冻结分支或标签时会被阻止。该 hook 只是本地纵深防御控制；它不进入版本管理，不能阻止其他 clone 发起的推送，也不能替代服务端保护。

每次审核或部署前，不切换冻结分支，直接验证远端引用：

```text
git ls-remote origin refs/heads/assessment/v1-vulnerable refs/tags/appsec-v1-vulnerable "refs/tags/appsec-v1-vulnerable^{}"
```

分支值和 tag 解引用值必须都等于 `14a7b48ae30b833962752e4d65b7e03ade5664a1`。如不一致，立即停止评估或部署，并由 Security Engineer 审核。

状态只能按以下顺序变化：

`pending` → `requirements_approved` → `ready_for_claude_review`

- `requirements_approved`：以下第 2–7 节全部确认，但代码/fixture/场景可能尚未冻结。
- `ready_for_claude_review`：第 8 节也完成，并填写 Git commit、fixture ID、场景 ID 和 UTC 时间。

## 2. 业务、Actor 与数据

- [x] 业务是共享应用实例中的多租户用户资料读取服务。
- [x] 固定两个租户；每租户两个普通用户和一个租户管理员。
- [x] 普通用户只能读取自己；租户管理员能读取本租户用户，但不是全局管理员。
- [x] `name`、`email`、`phone` 是需要保护的合成资料；即使不是真实个人数据，越权读取仍按真实 finding 处理。
- [x] bearer token 是 Secret，不进入代码、模型上下文、日志或报告；服务端只保存摘要。
- [x] 脱敏后的 `user_id`、`tenant_id` 和 `role` 可以出现在评估证据中。
- [x] 授权判断必须使用服务端权威的身份、租户和角色信息；客户端提供的声明不得覆盖这些值。

如有修改：直接编辑 `assessment-brief.md` 第 1、3、4 节及 `security-requirements.json`，然后重新审核本节。

## 3. Security Requirements 与 Expected Behavior

| Requirement | 需要确认的决定 | 决定 |
| --- | --- | --- |
| AUTHN-01 | 三个业务接口都必须使用服务端映射的不透明 bearer token；缺失、格式错误或无效凭据返回 401 且不泄露资料 | `approved` |
| AUTHN-02 | 客户端提交的 tenant、role、user 声明不能改变身份或增加权限 | `approved` |
| AUTHZ-ME-01 | `/api/me` 只能返回当前认证用户被允许公开的资料字段 | `approved` |
| AUTHZ-OBJ-01 | 普通用户只能读取自己的详情；同租户他人和跨租户都拒绝 | `approved` |
| AUTHZ-OBJ-02 | 租户管理员可读取本租户详情；所有跨租户目标都拒绝 | `approved` |
| AUTHZ-LIST-01 | `/api/users` 只允许租户管理员调用 | `approved` |
| AUTHZ-LIST-02 | 管理员列表必须包含当前租户的所有用户，且不能包含其他租户用户 | `approved` |
| DATA-01 | 成功响应只能包含明确批准的公开字段，且不得暴露认证 token、凭据摘要、内部授权字段或其他敏感内部数据 | `approved` |
| ERROR-01 | 401、403、404、5xx 等错误都不能包含凭据或受保护资料 | `approved` |
| AUDIT-01 | 每个测试可用 run/request ID 关联，日志与报告不保存秘密或完整资料 | `approved` |
| TOOL-01 | Reviewer 工具必须强制限制已批准目标、允许的 HTTP 方法、范围内路由、批准的测试身份、已知测试对象 ID、重定向限制和请求预算 | `approved` |

将每行决定从 `pending` 改为 `approved` 或 `change_requested`。如果选择 `change_requested`，先修改 `security-requirements.json` 和相关 brief，再把本表同步到最终内容。

## 4. 接口范围与明确排除项

- [x] 范围内仅有 `GET /api/me`、`GET /api/users/{user_id}`、`GET /api/users`。
- [x] `user_id` 只能来自批准的六用户 fixture，不允许枚举未知 ID。
- [x] 本次不测试业务写操作、token 猜测、口令攻击、社会工程、持久化或破坏性行为。
- [x] 本次不测试主机、Docker、Alibaba Cloud 或网络基础设施。
- [x] 本次结果不用于得出性能、DDoS、容量或应用整体安全结论。

## 5. Claude Reviewer 权限与职责分离

- [x] 第一阶段中，Claude 只能读取已冻结生成 bundle 的 `readable_files`；该 bundle 是其唯一可访问工作区。
- [x] Claude 无法访问源仓库及其父目录；manifest allowlist 由执行环境强制实施，不能只依赖 prompt 约束。
- [x] Claude 不能读取原始 token、SQLite 数据库、`.env`、历史本地报告或操作者场景答案。
- [x] 第一轮不向 Claude 提供现有测试代码和漏洞 truth label，避免把现成答案当作独立评审结果。
- [x] 只有第一阶段输出已封存且 Security Engineer 明确授权第二阶段后，才释放固定权限矩阵和脱敏确定性结果；之后不得回写第一阶段输出。
- [x] Claude 可以追踪代码路径、提出和执行受限 negative tests、收集证据并起草 finding。
- [x] Claude 不能修改安全需求、应用代码、最终 finding 状态或严重性。
- [x] Codex 负责实现和修复，但不能把应用授权函数作为独立 oracle，也不能批准自己的修复。
- [x] Security Engineer 最终判断 finding 的真实性、影响、严重性和 remediation 是否接受。

## 6. 执行与证据边界

- [x] 目标固定为 `http://127.0.0.1:8000`，不使用环境代理，不跟随跨目标重定向。
- [x] 基础矩阵最多每秒两次请求、并发不超过二、单请求超时十秒。
- [x] 凭据由工具层按 alias 注入，不进入 Claude 上下文。
- [x] 原始响应不写入报告；报告只保存脱敏摘要和 evidence ID。
- [x] 429、超时、5xx、重定向、fixture 不匹配和证据缺失都判为 `inconclusive`。
- [x] HTTP 200 本身不是漏洞证据；错误状态中的受保护数据仍可构成确认违规。

## 7. Finding、修复与回归规则

- [x] Confirmed finding 必须引用实际 run ID、case ID、request ID、evidence ID 和 requirement ID。
- [x] Claude 只能提交 finding 草稿和有依据的影响分析，不能最终确认严重性或生成未经计算的精确 CVSS。
- [x] Security Engineer 对每个 finding 选择 `confirmed`、`rejected` 或 `needs_more_evidence`。
- [x] 只有 `confirmed` finding 才进入 Codex remediation。
- [x] 修复复测复用同一 fixture、身份映射、权限版本和用例。
- [x] 关闭 finding 前必须同时证明违规消失和原本合法访问仍然成功。

完成第 2–7 节后，将 `approval_status` 改为 `requirements_approved`。这表示需求已确认，还不表示可以开始正式 Claude 评估。

## 8. 正式评估启动门槛

最终启动批准包已经准备完成，见 [说明](../../../docs/formal-start-approval.md)和 `formal-start-approval-package.json`。批准包仍为 `prepared_not_approved`，以下两项仍须由 Security Engineer 明确确认。

- [x] 当前 requirement version 已去掉 `-draft`，JSON 与本记录一致。
- [x] 评估代码已冻结，并填写了完整 Git commit SHA。
- [x] 评估 fixture 已冻结，并填写了 fixture ID。
- [x] 漏洞场景已去除明显的 `*_bypass` 答案标签，并填写了中性 scenario ID。
- [ ] 评估期间不修改代码、requirements、fixture 或 reviewer manifest。
- [ ] approver 和 `approved_at_utc` 已填写。
- [x] 已再次确认 Claude 不会获得 raw credentials 或 ground-truth label。

全部完成后，将 `approval_status` 改为 `ready_for_claude_review`。这一状态才授权进入 Claude 的正式 decision-path review 和独立测试矩阵阶段。

## 9. 变更记录

| UTC 时间 | 修改人 | 变更 | 是否需要重新审批 |
| --- | --- | --- | --- |
| `2026-09-19T18:42:29Z` | `project_owner` | 批准 AppSec requirements v1.0（第 2–7 节） | 否（初始批准） |
| `2026-09-19T19:41:06Z` | `project_owner` | 批准 bundle-only 两阶段 reviewer 访问模型 v2.0 | 否（已在本记录中批准） |
| `2026-09-19T19:56:57Z` | `project_owner` | 授权实现隔离 runner 计划、第一阶段封存和第二阶段释放门禁；仍未授权执行 Claude | 否（实现已批准模型） |
| `2026-09-19T20:44:40.966113Z` | `codex` | 基于已记录的干净 commit、新 fixture 和随机选择的中性场景生成正式冻结候选；启动门槛仍未勾选 | 否（仅生成候选） |
| `2026-09-19T21:09:33Z` | `codex` | 记录漏洞/修复 Git 引用及 GitHub Free 私有仓库保护限制；未移动任何引用，启动门槛仍保持开放 | 否（仅记录冻结控制） |
| `2026-09-19T21:12:15Z` | `codex` | 为冻结分支和漏洞标签安装并测试本地 pre-push guard；服务端保护仍不可用 | 否（本地纵深防御控制） |
| `2026-09-19T21:22:29Z` | `codex` | 完成 Claude reviewer 运行时准备审计；未安装或执行 Claude，未读取凭据内容，正式启动门槛保持开放 | 否（只记录运行准备状态） |
| `2026-09-19T21:41:52Z` | `codex` | 实现并通过固定 Claude Code 2.1.278 Linux reviewer 镜像的无凭据、离线隔离 smoke test；未认证或调用模型，正式启动门槛保持开放 | 否（实现已批准的运行时基础） |
| `2026-09-19T21:53:33Z` | `codex` | 实现并通过未启用的代理唯一出口 smoke test；只允许 `api.anthropic.com:443` TLS 握手，未发送 API 请求、注入凭据或调用模型，正式 runner 仍保持离线 | 否（实现已批准的出口基础） |
| `2026-09-19T22:03:20Z` | `codex` | 固化未批准的专用 Anthropic workspace API key 来源、`claude-sonnet-5` 与单次运行预算提案，并通过 synthetic sentinel 本地泄漏验证；未使用真实凭据、网络或模型 | 否（实现已批准的凭据与预算门禁设计） |
| `2026-09-19T22:22:24Z` | `project_owner` | 批准项目专用可撤销 Anthropic workspace API key、`claude-sonnet-5`、100k/20k token 规划边界、12 次模型 API 调用审批边界、12 agentic turns、30 次工具调用、900 秒和单次 `$1.00` 上限；不批准模型执行 | 否（运行方案批准，正式启动门仍开放） |
| `2026-09-19T22:27:14Z` | `codex` | 实现固定 Claude 命令和 fail-closed supervisor，并通过 synthetic secret、managed settings 文件、proxy allowlist、非 allowlist 拒绝和直连阻断的组合 smoke；未调用模型或产生费用 | 否（执行控制与无费用验证） |
| `2026-09-19T22:27:21Z` | `codex` | 验证正式候选并生成 attestation，绑定冻结 commit、fixture、scenario、bundle、profile hash 和本地镜像 ID；启动门 7 项中 5 项已有证据，正式执行仍未授权 | 否（候选验证） |
| `2026-09-19T22:29:53Z` | `codex` | `claude doctor` 发现并修复 reviewer 镜像缺少 `bubblewrap`/`socat` 的真实启动问题；重建后 doctor 与组合 smoke 通过，未使用真实凭据或模型 | 否（运行时修复与重新验证） |
| `2026-09-19T22:33:53Z` | `codex` | 使用修复后的 reviewer image `sha256:d496…642a` 重新生成正式候选 attestation；旧 attestation 被替换，正式启动状态不变 | 否（候选重新绑定） |
| `2026-09-19T22:37:07Z` | `codex` | 在固定命令中显式禁止 MCP、slash commands 和 Chrome，并重新绑定最终 command hash；正式执行仍未授权 | 否（执行面收紧与候选重新绑定） |
| `2026-09-19T22:38:01Z` | `codex` | 将 controller、runtime wrapper/settings 和 egress proxy 的逐文件 SHA-256 加入 attestation，绑定未提交工作区中的准确控制面实现 | 否（候选完整性强化） |
| `2026-09-19T22:55:58Z` | `codex` | 准备最终启动批准包，绑定候选证明、固定预算和 14 个原子开关变更；补充批准状态一致性校验、跨平台 LF 哈希稳定性和官方 Workspace/key 操作说明，所有开关仍关闭 | 否（只准备批准对象，未授权或执行模型） |

正式批准后，任何影响 actor、asset、trust boundary、scope、expected behavior、工具权限或 finding 标准的改动，都必须新增记录并重新审批。仅修正文案拼写且不改变含义时，可以记录为无需重新审批。
