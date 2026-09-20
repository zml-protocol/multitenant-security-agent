# AppSec v1 Finding Adjudication Record

[English](adjudication-record.en.md) | 中文

- 状态：`adjudicated`
- 裁决人：Security Engineer / project owner
- 裁决时间：`2026-09-20T03:52:53.862Z`
- Reviewer 输出：[Claude v4 原始结果](raw/findings.md)
- 机器可读记录：[adjudication-record.json](adjudication-record.json)

本记录保存 Security Engineer 对 Claude v4 草稿的逐项决定。它不修改 Claude 的原始输出，也不表示已开始 remediation。

## F1：通过 404/403 差异判断跨租户对象是否存在

- Requirement mapping：`AUTHZ-OBJ-02`、相邻的 `ERROR-01`；user ID enumeration 当前属于 out of scope。
- Evidence summary：`app/main.py:112-119` 先全局查询对象；未知 ID 返回 404，已存在但跨租户的 ID 返回 403。`app/policy.py:11-12` 仍会拒绝跨租户读取。本次没有执行动态请求。
- Expected behavior：跨租户目标必须被拒绝，错误不得泄露 protected profile 或凭据。
- Observed behavior：静态路径存在 cross-tenant existence oracle，但未显示姓名、邮箱、电话等 protected profile 被返回，也没有运行时复现证据。
- **最终状态：`needs_more_evidence`**
- 裁决理由：代码路径支持存在性差异假设，但尚未动态证明；当前证据也没有直接证明 protected profile 泄露。
- 严重性：`not_assigned`
- Remediation decision：`deferred_pending_evidence`

### 最小补充证据计划

在后续获得单独批准的受控动态测试中，使用同一个低权限已认证 actor，对一个已知跨租户 user ID 和一个不存在的 user ID 各发送一次 `GET /api/users/{user_id}`。只记录状态码、通用错误体、request ID 和审计 decision/reason，不保存 protected profile 或 token。确认 403/404 差异是否可稳定复现后，再判断现有 scope 是否需要修改以及是否构成 finding。

## F2：列表租户过滤位于 route SQL，而非 policy 模块

- Requirement mapping：`AUTHZ-LIST-02`；`AUTHN-02` 提供服务器端 tenant 来源的上下文。
- Evidence summary：`app/policy.py:4-7` 检查 admin role；`app/main.py:108` 使用服务器端 `actor['tenant_id']` 过滤列表。
- Expected behavior：列表包含当前管理员租户的全部用户，且不包含其他租户用户。
- Observed behavior：当前查询满足该结果；Claude 提出的是未来维护风险，没有证明当前版本发生跨租户列表泄露。
- **最终状态：`rejected`**
- 裁决理由：当前 requirement 实际满足；该项属于架构和维护性 concern，不是当前 vulnerability。
- 严重性：`not_applicable`
- Remediation decision：`none_required_for_appsec_v1`

## O1：固定 seed PRNG 生成 fixture user ID

- Requirement mapping：没有直接 requirement violation；`AUTHN-01` 说明身份由 bearer token 而不是 user ID 建立；enumeration 当前属于 out of scope。
- Evidence summary：`app/seed.py:12-20` 使用固定 seed 生成可复现 user ID；`app/seed.py:36` 独立使用 CSPRNG 生成 bearer token。
- Expected behavior：fixture 可复现，认证仍依靠不可预测且由服务器校验的 token。
- Observed behavior：fixture ID 可预测，可能放大 F1 的存在性信号，但没有用作认证凭据。
- **最终 disposition：`informational`**
- 裁决理由：这是测试 fixture 属性，不在当前 enumeration scope，也没有直接违反认证或授权需求。
- Remediation decision：`none`

## O2：SQLite token digest 比较不保证 constant-time

- Requirement mapping：`AUTHN-01` 提供认证上下文；当前 requirement 没有规定数据库比较必须 constant-time。
- Evidence summary：`app/main.py:85` 对完整 SHA-256 digest 执行参数化精确查询；没有 timing measurement、认证绕过或 token 恢复证据。
- Expected behavior：只有有效 token 可以建立身份，未知 token 返回 401，token 和 digest 不得泄露。
- Observed behavior：理论上的 constant-time concern 存在，但远程现实可利用性很低，本次也没有动态证据。
- **最终 disposition：`informational`**
- 裁决理由：保留 defense-in-depth 记录，但不作为当前 vulnerability。
- Remediation decision：`none`

## 后续状态

当前没有进入 remediation 的 confirmed finding。F1 只能在 Security Engineer 另行批准最小动态测试后收集补充证据；F2、O1 和 O2 不触发 `remediation/v1` 修改。
