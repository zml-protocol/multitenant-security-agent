# 修复建议草稿

[English](remediation-advice.en.md) | 中文

状态：`draft_recommendation_for_security_engineer_and_codex` —— 本文件仅为 Claude 基于证据的初步建议，**不是**已批准的修复方案，不带最终严重性判断，也不授权 Codex 立即执行；Security Engineer 必须先确认每项 finding 及其严重性。Claude 未修改、也不会修改任何应用代码。

## 针对 F1 —— `GET /api/users/{user_id}` 的跨租户对象存在性 oracle

**可能的根因修复方向（供 Codex / Security Engineer 选择并验证）：**

1. **让存在性判断本身具备租户/权限感知。** 目前是先 `SELECT * FROM users WHERE user_id = ?`（`app/main.py:112`）再单独做归属/租户判断；可以改为：当查到的行触发 `policy.authorize_detail` 的 `tenant_boundary` 拒绝原因时，对外返回与 `unknown_user`（如 `404`）**相同的状态码/响应体**，而不是可区分的 `403`，使"存在但不属于你"与"不存在"对无权知晓两者的调用者而言不可区分。可将可区分的 `403 owner_required` 保留给同租户内的拒绝场景（该场景下"存在"这一事实本就在 actor 的租户范围内，泄露面更小；具体披露策略由 Security Engineer 决定）。
2. 或者：内部审计日志（`request.state.reason`）继续区分 `tenant_boundary` 与 `unknown_user` 两种原因以保留丰富的审计信息（满足 `AUDIT-01`），但在对外的 HTTP 状态码/响应体层面将二者统一，从而消除外部可观测的 oracle。
3. 无论选择哪种方向，都应新增回归测试，断言：同一个无权限 actor 分别请求 (a) 真实存在的跨租户 user_id 和 (b) 随机不存在的 UUID 时，响应状态码/响应体逐字节一致。

**不应做的事**：不要削弱现有的 `tenant_boundary` 检查本身（`app/policy.py:11-12`）——该检查目前正确阻止了 admin 跨租户读取；本项修复针对的是"响应是否可区分"，而不是底层 allow/deny 逻辑。

## 针对 F2 —— 列表接口的租户范围控制位于策略模块之外

**可能的根因修复方向：**

1. 在 `app/policy.py` 中新增一个显式的范围生成函数，例如 `def scope_list(actor): return {"tenant_id": actor["tenant_id"]}`（或返回可直接使用的 SQL 谓词/参数），让 `app/main.py:108` 调用该辅助函数，而不是直接内联 `actor["tenant_id"]`。这样租户范围规则就与 `authorize_list`/`authorize_detail` 处于同一模块，可见且可测试。
2. 针对 `app/policy.py` 直接编写单元测试，独立于 SQL 层断言：任意 actor 得到的范围绝不包含其他租户 —— 这样未来对 SQL/路由的重构如果无声地移除了租户过滤，会导致策略层测试失败。
3. 当前行为（非 admin 拒绝、按租户过滤）保持不变；这是结构性/可维护性建议，不改变现有决策路径的行为。

## 针对 Observation O1（fixture user_id 可预测性）

不属于应用代码缺陷。建议提示给 fixture/工具负责人：如果 `app/seed.py` 中固定种子的 `random.Random(seed)` 这种生成模式被复用到需要"不可预测性"的标识符上（而非仅用于可复现的测试数据），应替换为 CSPRNG（如同现有 token 生成正确使用的 `secrets.token_urlsafe`，`app/seed.py:36`）。

## 针对 Observation O2（非常数时间的哈希比较）

仅作为可选的纵深防御：如 Security Engineer 希望进一步加固，可在现有数据库索引查找之外，额外使用 `hmac.compare_digest()` 对摘要做比较。鉴于评估的实际可利用性极低，此项为可选项。

## 适用于任何修复的通用提醒

- 任何修复都必须保留 `fixture_id`（`fixture-256eb13b57860e22`），以便同一评估/回归可以针对相同数据重新运行，见 `assessment-brief.md` 第 4 节资产表。
- 任何修复都不得在成功或错误响应中引入 `approved_public_fields` 之外的新字段，也不得削弱 `AUDIT-01`（日志中不得出现凭据或完整资料字段）。
- Codex 必须提供同一 fixture 的回归证据，证明修改后合法访问（如 TC-09、TC-12、TC-17、TC-18）仍然正常，见 `assessment-brief.md` 第 9 节。
- 以上均非最终决定；必须先由 Security Engineer 确认后方可实施，Codex 不能自行批准其安全结论。
