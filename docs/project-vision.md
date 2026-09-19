# 项目总目标与双工作流路线

[English](project-vision.en.md) | 中文

本文定义项目的长期目标。`spec.md v0.1` 是第一版需求基线，当前已完成的 `docs/phase1.md` 是本地授权实验的第一阶段实现；它们不是最终架构的全部范围。

## 核心目标

在 Alibaba Cloud 上建设一个可控、可重复、可审计的真实安全实验环境，用同一个多租户应用完成两条端到端工作流：

1. 白盒、human-in-the-loop 的 AppSec AI-assisted Security Assessment。
2. DDoS / Network Security Incident Response。

项目不是为了证明 AI 能独立发现所有漏洞，也不让模型直接控制生产或云安全配置。目标是展示安全工程师如何定义问题、约束工具、核验证据、审批动作并对最终判断负责，同时把 Web/API 安全能力扩展到云、网络、DDoS 检测与响应。

最终演示必须能由项目所有者自己解释：信任边界、控制点、证据链、判断依据、缓解措施、恢复验证和局限，而不是依赖 Agent 临场给出答案。

## 工作流一：AppSec AI Agent Flow

这是一次正式白盒 Product Security Assessment 的模拟，而不是黑盒自动扫描。

### 角色与责任

| 角色 | 责任 | 不应代替的责任 |
| --- | --- | --- |
| Security Engineer（项目所有者） | 定义业务背景、范围、actor、asset、trust boundary、security requirement、expected behavior；审核证据；判断 finding 是否成立、影响与严重性；批准 remediation；验收 regression | 不把最终风险判断交给模型 |
| Claude（独立 reviewer） | 阅读代码；追踪 authentication/authorization decision path；从独立需求生成测试矩阵；执行或提出 negative test；收集和引用证据；起草 finding | 不修改需求答案、不直接批准修复、不自行决定最终严重性 |
| Codex（实现者） | 实现应用和测试工具；根据已确认 finding 修复代码；补充回归测试；维护部署与可重复实验 | 不把自己的实现逻辑当作独立测试 oracle，不替 Security Engineer 接受风险 |

Claude 与 Codex 应保持 reviewer / implementer 的职责分离。两者的输出都是可审查材料，不是权威结论。

### 完整流程

1. Security Engineer 编写 assessment brief：业务、数据分类、actor、asset、入口、信任边界、威胁、明确范围和禁止动作。
2. 将 security requirement 与 expected behavior 版本化，作为独立测试 oracle。
3. Claude 阅读代码并输出 authentication / authorization decision path，标明身份来源、租户上下文、策略判断、对象查询及响应位置。
4. Claude 根据需求而不是应用授权函数生成正向和负向测试矩阵。
5. 在明确目标、已知身份、只读/受控操作和请求预算内执行测试，记录 run_id、case_id、request_id 和脱敏证据。
6. 区分 confirmed finding、functional anomaly、inconclusive 和 no violation observed；HTTP 状态码本身不构成越权证据。
7. Claude 起草 finding：requirement、前置条件、复现、证据、影响、可能根因、建议和局限。
8. Security Engineer 核验证据，确认或驳回 finding，并决定影响与严重性。
9. Codex 在确认范围内实现 remediation 和必要的 regression test。
10. 使用同一 fixture、身份映射、权限版本和用例重测；确认违规消失且合法业务仍然工作。
11. Security Engineer 完成 assessment report 和风险接受/关闭记录。

### 最终交付证据

- assessment brief 与数据流/信任边界图。
- authentication / authorization decision path。
- 独立、版本化的 security requirement 和测试矩阵。
- 原始证据的脱敏引用、finding 草稿、人工裁决记录。
- 修复 diff、回归结果和修复前后对照。
- Agent 工具边界、调用预算、失败模式和审计记录。

## 工作流二：DDoS / Network Security Incident Response Flow

同一个应用部署到 Alibaba Cloud，逐步形成 ALB、ECS、RDS、SLS，以及按阶段加入 WAF、Anti-DDoS 和 ActionTrail 的实验环境。所有测试只针对自有、明确授权的资源，并受流量、持续时间、并发和停止条件约束。

### 场景层次

| 场景 | 首选实现方式 | 主要观察目标 |
| --- | --- | --- |
| HTTP Flood | 自有环境中的受控低强度 load test，配合正常探针 | L7 请求率、URI/来源特征、ALB/WAF/应用状态、429/5xx、延迟和业务影响 |
| SYN/UDP Flood | 优先 synthetic telemetry、预制日志或云厂商安全演练能力；真实包测试必须另行评审并严格限界 | L4 协议、连接/包速率、丢包、主机与边界指标、L7 日志缺失的含义 |
| Compromised ECS outbound attack | synthetic logs 或隔离靶场中的受控 egress 模拟，不攻击互联网第三方 | 异常出站连接、进程/主机线索、VPC/主机日志、凭据与配置变更、遏制和取证保全 |

SYN/UDP 和 outbound 场景不能仅靠 HTTP access log 得出结论。设计必须明确哪些是实际流量、哪些是 synthetic telemetry、哪些只是分析假设。

### 完整流程

1. 建立正常基线：请求率、连接、错误率、p50/p95/p99、资源使用、数据库连接和正常探针。
2. 通过告警或合成事件发现异常，记录 incident_id、时间线和触发规则。
3. 收集 ALB、WAF、Anti-DDoS、SLS、ECS、RDS、VPC/网络及 ActionTrail 中当前可用的 telemetry，并标记数据来源与缺口。
4. 判断异常属于 L4、L7、应用故障、配置变更还是证据不足；不因单个指标直接下结论。
5. 分析攻击模式：目标、协议/方法、URI、来源分布、速率、连接行为、时间模式和业务影响。
6. AI Agent 在受限只读工具内关联证据、提出假设和候选 mitigation，引用实际 evidence_id，并报告不确定性。
7. Security Engineer 审核影响、误伤风险、回滚条件和具体动作，进行人工审批。
8. 受限执行器只执行预定义、与 incident_id 和有效期绑定的动作；模型不能直接运行任意 Shell 或修改云配置。
9. 同时验证攻击侧指标、正常探针、错误率、延迟、容量和业务功能；仅观察到 429 不等于恢复成功。
10. 人工批准恢复/回滚，确认配置回到预期状态。
11. 输出 post-incident report：检测、证据、判断、决策、缓解、恢复、时间线、缺口和后续改进。

### 安全与真实性原则

- 不对第三方目标发包，不进行未授权扫描，不做真实带宽耗尽或互联网出站攻击。
- 每次真实 load test 都有目标 allowlist、最大请求数、RPS、并发、持续时间、停止条件和正常探针。
- synthetic 数据必须标记 `synthetic=true`，与真实访问日志分开统计。
- 先完成无付费资源的本地/离线验证，再在创建资源前核对 Alibaba Cloud 当前价格、地域、配额和日志成本。
- 云动作使用最小权限、短期凭据和审计；测试 Agent 与响应执行器分离。
- 明确能力边界：应用层日志不能证明已经检测网络层 DDoS，单节点实验不能证明生产级容量或防护效果。

## 分阶段实施路线

| 阶段 | 目标 | 完成判据 |
| --- | --- | --- |
| 1 | 本地多租户应用、固定权限矩阵和三种独立漏洞模式 | 已完成；安全模式 54 项通过，漏洞模式分别稳定发现 8/18/4 项并完成同 fixture 复测 |
| 2 | 正式 AppSec assessment artifact 与独立 reviewer 流程 | assessment brief、decision path、Claude 测试矩阵、人工 finding 裁决、Codex 修复和回归证据完整 |
| 3 | 本地容器化、NGINX/应用日志、可观察性和 Agent 只读工具 | 日志相关、提示注入/工具越界、模型不可用和预算场景通过 |
| 4 | Alibaba Cloud 基础部署 | ALB、ECS、RDS、SLS 最小架构可重复部署；网络、身份、秘密、备份和成本控制有记录 |
| 5 | L7 incident flow | 受控 HTTP Flood 从发现到 post-incident report 全流程完成，人工审批和恢复可审计 |
| 6 | L4 与 compromised host 演练 | 使用合成或经批准的隔离方式完成 SYN/UDP 与 outbound 场景，能解释 telemetry 差异与调查边界 |
| 7 | 防护组件与最终演示 | 按需加入 WAF、Anti-DDoS、ActionTrail，形成双工作流演示、架构图、报告和三分钟/深度讲述版本 |

每阶段都必须先定义验收条件再实现。云组件的选择应由要回答的安全问题驱动，并记录“为什么需要这个 telemetry/control”，避免为了堆叠产品名称而增加资源。

## 项目叙事

项目最终要表达的能力不是“我让 AI 替我做安全”，而是：

> 我能把安全需求转换为可执行、可审计的验证；让不同 Agent 在明确职责和工具边界内协作；由人核验证据、批准修复和响应动作；并把同一套证据思维从 AppSec 扩展到云与网络事件响应。
