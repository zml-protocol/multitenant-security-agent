# F1 修复验证报告

[English](remediation-verification.en.md) | 中文

- Bundle：`remediation-bundle-9d359afaf9d8f80e1ca6`
- Finding：`F1`
- 冻结漏洞基线：`14a7b48ae30b833962752e4d65b7e03ade5664a1`
- 修复分支来源 commit：`84396352268b34a407c2ac2f27602e09c2d55eaa`
- 验证方式：**仅静态**，容器启动器已强制执行 Security Engineer 的人工启动批准；本次不进行动态测试，也不是新的漏洞挖掘
- 草稿验证结论：**`remediation_verified`**
- 最终验收权限：**Security Engineer**（本报告只是 Claude 的独立验证建议，不构成最终验收）

## 1. 输入确认

已使用 Read 读取 `bundle-manifest.json` 并确认返回了实际内容（18 个 `readable_files` 条目 + `file_sha256`）。随后逐一读取 `readable_files` 中列出的全部 18 个相对路径，未使用 Glob 替代 manifest allowlist。

## 2. 证据来源分层

本报告严格区分两类证据：

- **静态证据（本次由 Claude 直接读取源码得出）**：`app/main.py`、`app/policy.py`、`app/seed.py`、`changes/remediation.diff`、`scanner/assess.py`、`scanner/matrix.py`、`tests/test_application.py`（仅读取源码，未执行）、`inputs/permissions.json`。
- **既有运行时证据（由此前已授权的动态测试提供，非本次会话生成）**：`evidence/before.json`（修复前）、`evidence/after.json`（修复后/回归）。Claude 本次会话未执行任何代码、未发送任何 HTTP 请求。

## 3. 待验证的 Finding

`assessment/adjudication-record.json:9-24`：F1 `final_status = confirmed`，`remediation_decision = authorized`。

验收标准（`assessment/adjudication-record.md:25-27`）：同一低权限已认证 actor 请求跨租户已存在对象与不存在对象时，两次响应必须具有相同的 HTTP 状态码和通用错误体；两次都不得返回 protected profile；服务端审计日志可继续保留内部拒绝原因。

## 4. 独立追踪修复后的鉴权判定路径

路由：`GET /api/users/{user_id}`，`app/main.py:110-122`。

1. `app/main.py:112` 对 `user_id` 做全局（无 tenant 过滤）查询。
2. 若无结果：`app/main.py:113-114` → `deny(request, 404, "unknown_user")`。
3. 若有结果：调用 `app/policy.py:10-15` 的 `authorize_detail(actor, target)`：
   - `tenant_id` 不同 → `(False, "tenant_boundary")`（`policy.py:11-12`）；
   - 同租户且 `user_id` 相同或 `role == admin` → `(True, "self_or_tenant_administrator")`（`policy.py:13-14`）；
   - 同租户但既非本人也非 admin → `(False, "owner_required")`（`policy.py:15`）。
4. `app/main.py:118-120`：`deny(request, 404 if reason == "tenant_boundary" else 403, reason)`。
5. 允许分支只返回 `public(target)`（`app/main.py:94-95, 121-122`），字段集合 `FIELDS = (user_id, tenant_id, role, name, email, phone)`（`app/main.py:16`），与 `assessment/security-requirements.json:22` 的 `approved_public_fields` 完全一致。
6. `deny()`（`app/main.py:76-79`）返回的 HTTP body 永远是固定通用文本（401→"Unauthorized"，404→"Not found"，403→"Forbidden"），从不包含 `reason` 字符串或任何用户字段。

## 5. 逐项验收标准评估

| 验收项 | 结论 | 关键证据 |
| --- | --- | --- |
| 跨租户已存在对象 vs 不存在对象，对未授权调用者不可区分 | **通过** | `app/main.py:119-120` 把 `tenant_boundary` 和 `unknown_user` 都映射到 404，且 body 都是固定的 `{"detail":"Not found"}`；`evidence/after.json:14-50` 显示两者均为 `404`/`{"detail":"Not found"}`；`evidence/before.json:14-50` 显示修复前两者分别是 403/404（即原始漏洞）；`tests/test_application.py:101-115` 端到端断言状态码和 body 相等 |
| 同租户合法访问（本人 / 同租户 admin）保持可用 | **通过** | `app/policy.py:13` 未被 diff 改动；`evidence/after.json` 的 `matrix_summary.confirmed_violation = 0`，`passed = 54/54` |
| 同租户 owner 拒绝保持不变 | **通过** | `app/policy.py:15` 未变；`app/main.py:120` 的 else 分支对非 `tenant_boundary` 原因继续返回 403；`tests/test_application.py:80-81` |
| 租户管理员范围（同租户可读，跨租户仍拒绝）保持不变 | **通过** | `app/policy.py:11-14`：tenant 检查先于 role 检查，跨租户 admin 也会先命中 `tenant_boundary`（→404），不会进入 admin 允许分支，符合 `AUTHZ-OBJ-02` deny 条款 |
| Protected field 最小化不受影响 | **通过** | diff（`changes/remediation.diff:5-13`）只改了 116-123 行的状态码映射，`FIELDS`/`public()` 未变；`deny()` 从不调用 `public()` |
| 服务端审计原因保持区分且不对客户端泄露 | **通过** | `app/main.py:73` 无条件记录结构化日志中的 `reason` 字段；HTTPException 的 `detail` 只有固定通用文案；`tests/test_application.py:112-115` 断言两条日志的 `reason` 分别为 `tenant_boundary` 和 `unknown_user` |

## 6. Bypass 分析

检查了：客户端伪造 `X-Tenant-ID`/`X-Role`/`X-User-ID` 头、跨租户 admin 是否可利用分支顺序绕过、reason 或响应体/时序泄露存在性、任意拒绝路径的字段泄露、路由清单是否被扩大。

**结论：未发现 bypass。** 依据：`tests/test_application.py:70-77` 中伪造身份头不改变由 `authenticate()`（`app/main.py:81-89`）从数据库派生的实际身份；`policy.py:11` 的检查顺序天然阻止了跨租户 admin 绕过；本次 diff（`changes/remediation.diff:5-13`）在应用层只有一行状态码映射改动，没有新增字段、路由或查询。

## 7. 回归测试与 scanner oracle 的独立性/覆盖评估

- **回归测试**（`tests/test_application.py:101-115`）：直接通过 `TestClient` 调用生产默认策略（未替换 policy），验证的是真实行为而非 mock；断言与本报告独立静态推导的结论一致。但该测试与修复代码在同一次 diff/commit 中新增，并非由第三方独立编写。覆盖面上只有一个 actor（`a_user1`）、一个跨租户目标（`b_user1`）和一个固定的不存在 UUID，缺少更多 actor/target 组合（例如跨租户 admin 作为未授权 actor）的自动化覆盖。
- **Scanner oracle**（`scanner/assess.py:41-44`）：期望状态码是根据 fixture 中 actor/target 的 `tenant_id` 是否相等直接计算得出，**没有**导入或镜像 `app/policy.py` 的 reason 字符串，具备一定的需求驱动型独立性。但该 oracle 文件与应用修复在同一个 `changes/remediation.diff`（第 15-37 行）中一起被修改，并非预先存在、完全独立的第三方 oracle。更重要的是，`scanner/matrix.py:22-50` 的 `build_cases` 只在六个配置好的 fixture 别名之间构造 detail 用例，**从未构造"不存在对象"的用例**，因此固定权限矩阵（`evidence/after.json` 中的 54 条）验证的是租户/角色鉴权正确性，并不直接覆盖 F1 的存在性预言机属性；该属性目前只由第 5 节提到的单一单元测试覆盖。
- `scanner/run.py`（被 `tests/test_application.py:13` 引用）与 `evaluation/operator.py`（被 `tests/test_application.py:12` 引用，很可能对应 `bundle-manifest.json:57` 中被排除的 "operator scenario mappings" 类别）均不在 `readable_files` 中，未被读取，其对 `run_matrix()`/`load_policy()` 的具体接线无法独立追踪。

## 8. 不受支持或无法验证的声明

1. `remediation/remediation-record.md:11` 与 `.en.md:11` 链接到 `regression-evidence.json`，但该相对路径（`remediation/regression-evidence.json`）未出现在 `bundle-manifest.json` 的 `readable_files`/`file_sha256` 中，无法在 allowlist 下打开。`evidence/after.json` 的内容看起来等价（相同 `fixture_id`、相同用例数据、相同 `matrix_summary`），但文档中引用的具体文件本身未经验证。
2. `remediation/remediation-record.md`/`.en.md` 声明 `appsec-v1-fixed` 标签尚未创建——任何可读文件中都不包含 git tag/ref 信息，此声明超出静态文件证据范围，无法独立确认或证伪，仅作为背景信息记录。

## 9. 结转的 out-of-scope 项（不在本次修复范围）

- **F2**：`rejected`，当前版本已满足要求，属于架构/可维护性问题；diff 未改动 `app/main.py:108` 的相关逻辑，确认未受影响。
- **O1**：`informational`，固定 seed 生成的 fixture user ID 可预测，但不是认证凭据；本次未处理，也未要求处理。
- **O2**：`informational`，SQLite digest 比较未保证 constant-time，属理论性 concern，无动态证据；本次静态复核未评估时序侧信道，超出范围。

## 10. 局限性（详见 limitations.md）

- 仅静态审查，本次会话未执行代码、未运行 pytest、未发起任何 HTTP 请求。
- `evaluation/operator.py`、`scanner/run.py`、`conftest.py`（`lab` fixture 来源）不在 `readable_files` 中，未读取，测试装置的完整接线无法独立验证。
- 无法在不使用 Bash 的情况下重新计算 `bundle-manifest.json` 中的 `file_sha256`，哈希值仅作为声明信息记录，未独立验证文件完整性。
- F1 存在性不可区分属性目前只有一个自动化测试场景覆盖，缺少更广泛的 actor/target 组合。
- `remediation-record` 文本中引用的 `regression-evidence.json` 具体文件不在 allowlist 内，未能直接核实该确切文件（以功能等价的 `evidence/after.json` 佐证）。
- `evidence/before.json`、`evidence/after.json` 是此前已授权动态测试提供的既有证据，不是本次会话产生的证据；Claude 的贡献是基于源码的独立静态复现同一结论，属于佐证而非新的一次执行。

## 11. 结论

**草稿验证状态：`remediation_verified`**

理由：唯一的应用代码改动（`app/main.py:118-120`）直接且最小化地消除了已确认的 F1 差异信号——跨租户已存在对象与不存在对象现在共享相同的状态码（404）和相同的通用 body（`{"detail":"Not found"}`），该结论已通过对 `app/main.py`、`app/policy.py` 的独立静态追踪确认，并有既有的修复前后动态证据和专门的回归测试佐证。五项保持性要求（同租户合法访问、同租户 owner 拒绝、租户管理员范围、字段最小化、服务端审计原因区分）均未受 diff 影响，且已独立确认未变。未发现 bypass。已识别的差距（allowlist 之外的测试装置文件、单场景的自动化存在性预言机覆盖、一条无法核实的文档交叉引用）属于应向 Security Engineer 披露的局限性，而非否定修复本身的缺陷。

本结论为 Claude 的独立验证建议，**最终验收权限仍归 Security Engineer 所有**。本报告未指定最终严重性，也未修改任何代码。
