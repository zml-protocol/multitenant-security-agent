# AppSec v1 Finding Adjudication Record

[English](adjudication-record.en.md) | 中文

- 状态：`adjudicated_remediation_authorized`
- 裁决人：Security Engineer / project owner
- 裁决时间：`2026-09-20T03:52:53.862Z`
- F1 重新裁决时间：`2026-09-20T04:02:28.759Z`
- Reviewer 输出：[Claude v4 原始结果](raw/findings.md)
- 机器可读记录：[adjudication-record.json](adjudication-record.json)

本记录保存 Security Engineer 对 Claude v4 草稿的逐项决定。它不修改 Claude 的原始输出，也不表示已开始 remediation。

## F1：通过 404/403 差异判断跨租户对象是否存在

- Requirement mapping：`AUTHZ-OBJ-02`、相邻的 `ERROR-01`；user ID enumeration 当前属于 out of scope。
- Evidence summary：`app/main.py:112-119` 先全局查询对象；受控动态测试使用同一个低权限 actor，稳定复现了跨租户已存在对象返回 403、未知对象返回 404。详细证据见 [F1 最小动态证据](evidence/f1-minimum-dynamic-evidence.md)。
- Expected behavior：对未经授权的调用者，跨租户已存在对象与不存在对象必须具有相同的外部响应；不得通过状态码、通用错误体或其他响应属性确认对象是否存在。
- Observed behavior：跨租户已存在对象返回 `403 Forbidden`，不存在对象返回 `404 Not found`。两者均未泄露 protected profile，但外部表现可区分。
- **最终状态：`confirmed`**
- 裁决理由：静态路径假设已经由同一冻结 source commit 和 fixture 上的最小动态测试复现，证明未经授权的 actor 可以区分跨租户对象是否存在。
- 严重性：`Low`
- Remediation decision：`accepted`
- Claude verification：`remediation_verified`
- 修复提交：`84396352268b34a407c2ac2f27602e09c2d55eaa`

### 修复验收标准

使用同一个低权限已认证 actor 请求跨租户已存在对象和不存在对象时，两次响应必须具有相同的 HTTP 状态码和通用错误体；两次请求都不得返回 protected profile。服务端审计日志仍可在不向客户端披露的情况下保留内部拒绝原因。

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

F1 已确认、修复并由 Security Engineer 接受，最终严重性为 `Low`。F2、O1 和 O2 不触发代码修改。冻结的 `assessment/v1-vulnerable` 分支与 `appsec-v1-vulnerable` 标签不得改变。
