# Findings 草稿（仅限静态代码审查）

[English](findings.en.md) | 中文

状态：`draft_for_security_engineer_review` —— **非最终结论**。以下所有严重性、影响和有效性判断均为初步草稿，必须由 Security Engineer 做出 confirmed / rejected / needs-more-evidence 的最终裁决。本文档生成过程中未修改任何应用代码；未对任何目标执行动态 HTTP 请求，以下所有"预期状态/原因"均通过静态追踪源代码得出。

Bundle: `bundle-6a1a247aca19153c0d22` · Scenario: `scenario-7f3a`（仅作为不透明的溯源信息处理，不作为漏洞提示）· 需求版本：`appsec-v1.0` · Fixture：`fixture-256eb13b57860e22`

## 1. 认证决策路径

三条业务路由（`/api/me`、`/api/users`、`/api/users/{user_id}`）均依赖 `authenticate()`（`app/main.py:81-89`）：

1. `app/main.py:82-84` —— 读取 `Authorization` header，要求恰好两段（大小写不敏感的 `bearer` scheme + token），否则 `deny(401, "missing_or_malformed_credential")`。
2. `app/main.py:85` —— 对呈现的 token 做 SHA-256，通过参数化查询匹配唯一的 `token_hash` 列（`app/seed.py:44`）。
3. `app/main.py:86-87` —— 未命中 → `deny(401, "invalid_credential")`。
4. `app/main.py:88-89` —— 命中的行成为 `request.state.identity` / 后续所有决策使用的 `actor`。`app/main.py` 中没有任何路由从 header、query 参数或 body 中读取 tenant_id/role/user_id 来推导身份（AUTHN-02：客户端声明的身份在结构上不可能被采信，而不仅是策略层面禁止）。

## 2. 授权决策路径

**`GET /api/me`**（`app/main.py:97-100`）：返回 `public(actor)`，始终是调用者自己的记录，无需对象级检查。

**`GET /api/users`**（列表，功能级授权）：
- `app/main.py:104` 调用 `policy.authorize_list(actor)`。
- `app/policy.py:4-7`：仅检查角色 —— `role != "admin"` → `(False, "admin_required")`；否则 `(True, "tenant_administrator")`。
- `app/main.py:105-107`：`deny(403, reason)` / `allow(reason)`。
- `app/main.py:108`：返回列表的租户范围**仅**由原始 SQL `WHERE tenant_id = ?`（绑定 `actor["tenant_id"]`）强制执行 —— 该范围控制逻辑位于 `policy.py` 之外（见 Finding F2）。

**`GET /api/users/{user_id}`**（对象级授权）：
- `app/main.py:112`：仅按 `user_id` 查询目标，**没有租户谓词** —— 存在性判断先于授权判断执行。
- `app/main.py:113-114`：全库均无此行 → `deny(404, "unknown_user")`。
- `app/main.py:117` → `app/policy.py:11-15`：
  - `11-12`：`actor.tenant_id != target.tenant_id` → `(False, "tenant_boundary")`，**无条件执行，包括对 admin**——这正是租户 A 的 admin 永远无法读取租户 B 的原因。
  - `13-14`：否则 `actor.user_id == target.user_id` 或 `actor.role == "admin"` → `(True, "self_or_tenant_administrator")`。
  - `15`：否则 → `(False, "owner_required")`。
- `app/main.py:118-121`：`deny(403, reason)` / `allow(reason)` → `public(target)`。

经代码确认的辅助控制项：响应字段白名单（`app/main.py:94-95`）与 `approved_public_fields` 完全一致；`deny()`（`app/main.py:76-79`）对每种状态码始终返回固定的通用响应体；审计中间件（`app/main.py:43-74`）仅记录 id/路由/方法/状态/大小/耗时/alias/tenant/target/decision/reason，从不记录 `Authorization` header、原始 token 或完整资料字段；`X-Request-ID`/`X-Run-ID`（`app/main.py:20-24`）仅在能解析为 UUID 时才被采用，且从不影响授权决策；OpenAPI/docs 路由已禁用（`app/main.py:41`）。

## 3. 独立正/负向测试矩阵

本矩阵完全独立于 `assessment/security-requirements.json` 中引用的固定矩阵（`matrix_reference: ../../../fixtures/permissions.v1.json`）生成 —— 该文件位于 bundle 根目录之外，且属于明确排除类别（"existing test and scanner code"），符合信任边界 #4（"测试预期不得从应用授权函数推导"）。完整的 25 个用例（TC-01…TC-25，含 requirement ID、actor、预期状态/原因、依据）记录在 `findings.json → test_matrix`。要点：

- **TC-13（关键负向用例）**：`a_admin` 请求 `b_admin` 的对象必须是 `403 tenant_boundary`，绝不能是 `200` —— 这是 `app/policy.py:11-12` 先于 `13-14` 角色判断执行所保证的关键"admin 跨租户提权"防线。
- **TC-15**：TC-11（`a_user1` → 已存在的 `b_user1`，预期 `403 tenant_boundary`）与 TC-14（`a_user1` → 不存在的随机 UUID，预期 `404 unknown_user`）的差异对比 —— 该配对是下方 Finding F1 的证据基础。
- **TC-19**：Finding F2 的回归防护用例 —— 确认即便租户范围逻辑写在 SQL 而非 `policy.py` 中，客户端自报的 tenant 声明也无法覆盖服务端范围。
- **TC-25 / TOOL-01**：无法执行也无法静态确认 —— `readable_files` 中不包含 reviewer/执行工具的源码。

**以上 25 个用例均未执行。** 本阶段仅限静态审查；针对固定矩阵与脱敏结果摘要的执行留待 `assessment/reviewer-input-manifest.json` 定义的第二阶段（"difference_review"）。

## 4. Findings 草稿

### F1 —— `GET /api/users/{user_id}` 的跨租户对象存在性 oracle
- **证据**：`app/main.py:112`（无租户限制的查询）→ `113-114`（授权前先判断 404）→ `117-119` / `app/policy.py:11-12`（只有找到行之后才可能到达 403 `tenant_boundary`）。
- **影响草稿**：任何已认证的 actor —— 即便是没有列表权限的普通用户 —— 都能通过 `403` 与 `404` 的差异，在跨租户范围内区分"该 user_id 在系统中存在"与"不存在"，而无需被授权查看该记录。该行为本身不泄露 `name`/`email`/`phone`，因此单独尚不满足评估简报中 `confirmed_violation` 的门槛，但削弱了租户边界的保密性，并构成探测原语（若叠加 Observation O1 则风险上升）。
- **根因（草稿）**：存在性判断先于且独立于授权判断执行，且两条拒绝分支对调用者可区分。
- **修复方向（草稿）**：见 `remediation-advice.md`。
- **裁决**：待 Security Engineer 做出 confirmed / rejected / needs-more-evidence 决定。

### F2 —— 列表接口的租户范围控制位于集中式策略模块之外
- **证据**：`app/policy.py:4-7`（仅角色判断，无租户参数）对比 `app/main.py:108`（租户过滤仅存在于 SQL 中）。
- **影响草稿**：当前代码满足 `AUTHZ-LIST-02`，但该强制执行点并非承载其余所有 allow/deny 规则的同一模块，因此缺乏专门的策略层测试面，未来路由变更时可能被无声地移除。
- **根因（草稿）**："这个动作是否被允许" 与 "允许的对象范围是什么" 之间存在职责分离缺口。
- **修复方向（草稿）**：见 `remediation-advice.md`。
- **裁决**：待 Security Engineer 做出 confirmed / rejected / needs-more-evidence 决定。

### Observations（范围外观察，按简报第 7 节要求仅记录、不扩大测试范围）
- **O1**：`app/seed.py:12-13,20` 使用固定种子的非密码学 PRNG（`random.Random(42)`）生成 `user_id`，而 bearer token 使用 CSPRNG（`secrets.token_urlsafe(32)`，第 36 行）。仅作为信息记录 —— `assessment-brief.en.md` 第 6 节明确将"用户 ID 枚举"列为范围外，且 `app/policy.py`/`app/main.py` 从未将 `user_id` 当作凭据使用。仅在该 fixture 模式被用于测试场景之外时才会放大 F1 的风险。
- **O2**：`app/main.py:85` 通过 SQL 字符串相等比较 SHA-256 摘要，不保证常数时间比较。实际可利用性评估为极低。仅作信息记录。

## 5. 未观察到违规（仅基于静态审查）
`AUTHN-01`、`AUTHN-02`、`AUTHZ-ME-01`、`AUTHZ-OBJ-01`、`AUTHZ-OBJ-02`、`AUTHZ-LIST-01`、`AUTHZ-LIST-02`（现状代码）、`DATA-01`、`ERROR-01`、`AUDIT-01` —— 具体代码依据见 `findings.json → no_violation_observed`。按照简报的证据标准，单纯的源码分支本身并不能证明"不存在漏洞"；以上均为静态审查结论，并非动态执行确认（见 `limitations.md`）。

## 6. 本次静态审查不适用/无法验证
`TOOL-01` —— 涉及外部执行工具层，其源码不在 `readable_files` 之内，本次审查无法确认或证伪。

---
*本文件与 `remediation-advice.md` 均为提交 Security Engineer 审阅的草稿。Claude 不做最终有效性、严重性或修复决定，也未修改任何应用代码。*
