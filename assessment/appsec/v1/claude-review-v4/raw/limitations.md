# 限制、未执行用例与矩阵差异说明

[English](limitations.en.md) | 中文

## 1. 本次运行的范围

本次会话**仅执行静态代码审查**。根据操作者的明确说明，容器启动器已针对本次范围严格受限的运行（"静态代码审查、决策路径追踪与独立矩阵推导"）提前完成了 Security Engineer 的外部人工启动审批。本次未向 `127.0.0.1:8000` 或任何其他目标发出任何 HTTP 请求；未使用测试工具、Bash、Web、MCP、浏览器或任何凭据。独立测试矩阵（`findings.json → test_matrix`）中全部 25 个用例均标记为 `execution_status: not_executed`。

## 2. 遇到的工具缺口

任务说明中允许使用 `Grep` 与 `Glob`，但本次会话中调用时返回"No such tool available"。影响评估：可忽略。`bundle-manifest.json → readable_files` 是一个已完整枚举的小型白名单（12 个文件），每个文件均已通过 `Read` 完整读取，因此缺少目录列举/模式搜索工具并未造成覆盖缺口。此处如实记录，而非静默绕过。

## 3. 本 bundle 中被引用但无法访问的文件

- `assessment-brief.en.md` 第 10、13 节引用的 `assessment/approval-record.en.md` / `approval-record.md` **未**列入 `bundle-manifest.json → readable_files`，本次未读取。因此本次审查无法独立核实简报中所述人工审批门槛的当前状态（简报文字本身显示有一项检查框未勾选——"当前评估场景已冻结"）。本次审查完全基于操作者的明确陈述——即"本次特定的纯静态阶段"的人工启动审批已在外部提前完成——才得以进行；在将本产出用于静态审查之外的任何阶段之前，Security Engineer 应将该陈述与实际的 approval-record 进行核对。
- `security-requirements.json → matrix_reference` 指向 `../../../fixtures/permissions.v1.json`，位于 bundle 根目录之外，且属于明确的 `excluded_categories`（"existing test and scanner code"）。本次审查未读取也未尝试读取该文件。因此，"与现有固定矩阵的差异说明"这一交付物在本阶段无法以真正的 diff 形式给出——`findings.json`/`findings.md` 中的独立矩阵完全基于 `assessment/security-requirements.json` 与 fixture/actor 表构建，符合信任边界 #4（"测试 oracle 不得从应用授权函数或现有矩阵推导"）。真正的差异审查留待 `assessment/reviewer-input-manifest.json` 定义的 `difference_review` 阶段，届时由 Security Engineer 提供固定矩阵和脱敏的确定性结果摘要作为该阶段的 `additional_inputs`。
- `readable_files` 中不包含 reviewer/执行工具层（负责目标、方法、路由、身份、速率限制的组件，对应 `TOOL-01`）的源码。因此 `TOOL-01` 被标记为 `not_applicable_or_unverifiable_by_this_static_review`，而非通过/不通过。

## 4. 有意未提供给本次审查的数据（属于设计，非缺口）

依据 `bundle-manifest.json → excluded_categories` 与 `reviewer-input-manifest.json → forbidden_inputs`：原始凭据、SQLite 数据库本身、operator 的场景-漏洞映射/ground-truth 标签、其他场景实现、历史报告/扫描器代码均正确地未被提供，本次也从未请求过。`inputs/fixture.json` 仅包含 alias/user_id/tenant_id/role —— 全程未读取任何姓名/邮箱/电话/token 值，符合 `README.md` 所述的最小权限设计。

## 5. 有意不作为证据使用的溯源信息

- `bundle-manifest.json → status: "draft_not_for_claude"` 以及 `README.md`/`README.en.md` 中生成时的措辞（"尚未通过正式启动门槛"）已被保留并作为溯源/上下文信息阅读。它们未被、也不应被用作判断是否存在漏洞的信号。
- `scenario_id: "scenario-7f3a"` 被当作不透明标识符处理。`findings.json`/`findings.md`/`findings.en.md` 中的任何 finding 均未从该 ID 推断或以其为依据——每条 finding 均引用具体的文件/行号证据。

## 6. "未观察到违规"结论的性质

`findings.json` 中每一条"未观察到违规"均为**仅基于静态审查**的结论：所追踪的代码路径与需求一致。依据 `assessment-brief.md` 第 8 节，"源代码中的可疑分支"本身不能证明存在漏洞，反过来同样成立——在没有动态执行的情况下，一条看似一致的分支也不能被视为 `confirmed` 的通过。这些结论应理解为"静态审查未发现与需求相矛盾的代码路径"，仍需第二阶段的动态确认。

## 7. 本交付物的权限与边界

- Claude 未曾、也不会决定 finding 的最终有效性、严重性或 CVSS。该决定权属于 Security Engineer（见 `assessment-brief.md` 第 8、9 节）。
- Claude 未修改 `/review/input` 下的任何文件；所有写操作均限定在 `/review/output` 内。
- Claude 未修改应用代码，也未做出任何修复变更；`remediation-advice.md` 仅为方向性建议，需由 Codex 实施并经 Security Engineer 批准。
- 本文件与 `findings.json`、`findings.md`/`findings.en.md`、`remediation-advice.md`/`remediation-advice.en.md` 共同构成 `reviewer-input-manifest.json` 中定义的第一阶段（`decision_path_and_independent_matrix`）完整交付物集合。依据该 manifest，第一阶段产出应保持持久化/不可变，且需 Security Engineer 明确授权后方可进入第二阶段（`difference_review`）。

Claude 将继续留在本会话中，供 Security Engineer 就以上任何内容提出后续问题。
