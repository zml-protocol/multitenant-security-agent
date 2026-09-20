# F1 修复验证局限性说明

[English](limitations.en.md) | 中文

本文件汇总本次静态修复验证的已知局限性。这些局限性不改变第 11 节给出的草稿结论 `remediation_verified`，但应完整披露给 Security Engineer，作为其最终验收决策的输入。

## 1. 方法论局限

- **仅静态审查**：按任务约束，本次会话仅使用 Read/Glob/Grep/Edit，未使用 Bash、Web、MCP、浏览器、应用凭据或 HTTP；未执行 `tests/test_application.py` 中的任何测试，未运行 scanner，未发起任何网络请求。所有关于运行时行为的结论，要么来自对源码的静态推理，要么来自 bundle 中已提供的既有动态证据（见下）。
- **既有动态证据的边界**：`evidence/before.json` 和 `evidence/after.json` 是此前已获授权的动态测试产生的证据快照，并非本次会话生成。Claude 对这两份证据做了独立的静态复核（通过阅读 `app/main.py`、`app/policy.py` 重新推导相同结论），但没有能力重新执行以生成新的动态证据来交叉验证。
- **文件完整性未做密码学验证**：`bundle-manifest.json` 中的 `file_sha256` 字段未使用 Bash 或等效工具重新计算，只是作为声明信息被读取和引用；本报告不对这些哈希值的真实性做出独立断言。

## 2. Allowlist 边界导致的证据缺口

以下文件被 `tests/test_application.py` 或 `remediation/remediation-record.md` 引用，但**不在** `bundle-manifest.json` 的 `readable_files` 中，因此未被读取、也未被假设其内容：

| 被引用路径 | 引用位置 | 影响 |
| --- | --- | --- |
| `evaluation/operator.py`（`catalog`、`load_policy`） | `tests/test_application.py:12` | 无法独立追踪各种 bypass 模式（`same_tenant_bypass`、`cross_tenant_bypass`、`list_role_bypass`）以及 `"secure"` 模式与生产 `app/policy.py` 之间的映射关系是否完全一致；很可能对应 `bundle-manifest.json:57` 中声明被排除的 "operator scenario mappings" 类别 |
| `scanner/run.py`（`run_matrix`） | `tests/test_application.py:13` | 无法独立核实矩阵聚合、`fixture_id`/`run_id` 传递、以及最终汇总统计（`passed`/`confirmed_violation` 等）的实现细节，只能依据其产出（`evidence/after.json`）间接确认结果自洽 |
| `conftest.py`（`lab` fixture） | 隐式用于 `tests/test_application.py` 中所有 `lab` 参数 | 无法核实测试数据库/凭据的搭建方式是否确实调用 `app/seed.py:initialize()`，只能通过 `fixture_id` 字段在 `bundle-manifest.json`、`evidence/before.json`、`evidence/after.json` 之间一致（均为 `fixture-256eb13b57860e22`）来间接佐证 |
| `remediation/regression-evidence.json` | `remediation/remediation-record.md:11`、`.en.md:11` | 文档中链接的具体文件不在 allowlist 内，无法直接打开核实；`evidence/after.json` 在内容上（相同 fixture_id、相同用例、相同 matrix_summary）与其描述一致，视为功能等价证据，但不是对该确切文件的核实 |

这些排除大多与 `bundle-manifest.json:55-60` 声明的 `excluded_categories`（"operator scenario mappings"、"unrelated historical outputs"、"source repository and parent directories"）相符，属于 bundle 设计上的既定范围限制，而非本次审查的疏漏；但仍构成"缺失证据"，应予以披露。

## 3. 回归/oracle 覆盖局限

- F1 的核心可验证属性（跨租户已存在对象与不存在对象对未授权调用者不可区分）目前只有 **一个** 自动化单元测试场景覆盖（`tests/test_application.py:101-115`，固定 actor `a_user1`、固定跨租户 target `b_user1`、固定不存在 UUID）。虽然静态代码路径分析表明该修复对所有 actor 一致生效（`policy.py:11` 的 tenant 检查先于所有其他判断），但缺少覆盖更多 actor/target 组合（尤其是"跨租户 admin 作为未授权 actor"）以及多个不存在 ID 的自动化用例。
- `scanner/matrix.py` 构造的固定权限矩阵（48 条 + 6 条认证用例）完全基于六个已配置的 fixture 别名，**不包含任何"不存在对象"用例**，因此该矩阵验证的是租户/角色鉴权正确性，而不直接验证 F1 所定义的"存在性预言机"属性。
- `scanner/assess.py` 中更新后的 oracle 逻辑与本次修复在同一个 diff/commit 中一起提交，因此它相对于本次修复而言不是完全独立的第三方检验，尽管其期望值是基于 fixture 的 tenant 身份直接计算得出，而非镜像实现的 reason 字符串。

## 4. 未评估或明确排除的项目

- **时序侧信道**（对应裁决记录中的 O2）：本次未评估，也未获授权评估；裁决记录明确将其列为 informational、无需修复。
- **Fixture ID 可预测性**（对应 O1）：本次未处理，裁决记录明确列为 informational、无需修复。
- **F2**（列表租户过滤位于 route SQL 而非 policy 模块）：裁决记录明确 `rejected`，当前版本满足需求；本报告确认 diff 未触及相关代码（`app/main.py:108`），不再重复评估。
- **Git 标签/发布状态**（如 `appsec-v1-fixed` 是否已创建）：不属于任何可读文件的静态内容，无法核实，仅作为文档声明记录。

## 5. 本报告的性质

本报告是 Claude 的独立静态验证建议，**不是最终验收决定**。Security Engineer 保留最终验收权限，包括是否接受上述局限性、是否需要补充动态证据或扩展自动化覆盖，以及最终严重性判定。本报告未修改任何代码，也未创建或建议创建任何 git 标签。
