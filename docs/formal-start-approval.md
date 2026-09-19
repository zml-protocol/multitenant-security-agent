# Claude Reviewer 最终启动批准包

[English](formal-start-approval.en.md) | 中文

状态：`prepared_not_approved`

本批准包把“运行方案已经批准”和“允许这一次 Claude 正式评估”分开。当前候选、预算、容器和出口控制已经验证，但 Security Engineer 尚未接受评估期间不可变性承诺，也未填写最终批准人和时间。因此所有运行开关保持关闭，没有创建或读取真实 API key，也没有模型调用或费用。

## 当前绑定对象

机器可读批准包位于 `assessment/appsec/v1/formal-start-approval-package.json`：

| 对象 | 已绑定值 |
| --- | --- |
| 候选证明 SHA-256 | `8a2d419e75754557c8ef61e03dd52b8acd8882d92d9bd53bde764b73e86272bb` |
| 批准包 SHA-256 | `fe0b63ffdd00aa5c3b7d44f95615e2aef7cc7570092fe7eefe4add17c8f0059b` |
| 漏洞代码 commit | `14a7b48ae30b833962752e4d65b7e03ade5664a1` |
| fixture | `fixture-256eb13b57860e22` |
| scenario | `scenario-7f3a` |
| bundle | `bundle-6a1a247aca19153c0d22` |
| 模型 | `claude-sonnet-5` |
| 单次运行上限 | `$1.00`、12 turns、900 秒、1 MiB 捕获输出 |
| 工具 | `Read`、`Glob`、`Grep` |
| 出口 | 仅 `api.anthropic.com:443` |

批准包自身保持 `prepared_not_approved`，作为不可变的批准对象。最终批准记录写入 `start-gate.json`，并引用这个文件和候选证明的 SHA-256；不能通过改写批准包把新内容带入已批准运行。

## 仍需人工完成的两项决定

1. Security Engineer 接受：从最终批准开始到本次评估结束，不修改漏洞代码、requirements、fixture、reviewer manifest、bundle 或已绑定控制文件。需要变更时终止本次运行，重新生成证明并重新批准。
2. Security Engineer 填写最终 approver 与 UTC 时间，并明确把状态从 `requirements_approved` 改为 `ready_for_claude_review`。

这正是审批记录第 8 节尚未勾选的两项。准备批准包不代表替你作出决定。

## Anthropic Console 前置操作

这些操作需要你本人在 Anthropic Console 完成，并可能涉及购买不可退款的预付 credits。当前步骤没有执行任何付费操作。

1. 在 **Settings → Workspaces** 创建本项目专用 Workspace，例如 `appsec-v1-reviewer`。Anthropic 说明只有 Organization Admin 可以创建 Workspace。
2. 进入该 Workspace 的 **Limits**，设置 Workspace spend limit。当前项目政策要求记录的值为正数且不高于 `$1.00`。如果 Console 不允许该数值，停止启动并先修改、重新批准本项目预算；不要用更高限制代替。
3. 在组织 **Billing** 页面确认 auto-reload 关闭。预付 credits 余额属于组织级控制，不能替代本项目的 `$1.00` 单次 CLI 停止线。
4. 在 Workspace 的 **API Keys** 标签页创建专用 key，使用可识别但不敏感的标签，例如 `appsec-v1-reviewer-20260919`。
5. 只把 key 值保存到仓库外的临时文件。不要把值填入 JSON、Markdown、命令参数、聊天、Docker environment 参数或镜像。批准记录只写 Workspace 名称和 key 标签。
6. 运行完成后禁用或删除该 key，并在 Anthropic Usage/Cost 报告中按 Workspace 和 API key 核对实际用量。

Anthropic 官方说明：Workspace key 绑定到创建它的 Workspace；Workspace 的 Limits 页面可配置消费限制和通知；Billing 页面管理预付 credits 与 auto-reload；Usage/Cost 页面可以按 Workspace 和 API key 查看用量。

## 批准后一次性修改

批准包中的 `activation_changes` 记录了 14 个固定 JSON Pointer 变更。它们必须与 `start-gate.json`、审批记录的两个复选框和最终批准元数据一起修改，不能分批留下半开启状态。变更涵盖：

- auth/budget：状态改为 `formally_authorized`，允许正式执行和模型调用；
- execution：允许受控执行器运行；
- runtime：启用 `internal_proxy_only` 与只读 secret-file 注入；
- egress：把代理标记为正式 runner 的活动出口；
- reviewer manifest：改为 `ready_for_claude_review`；
- start gate：记录 approver、UTC 时间、不可变性承诺、Workspace/key 非敏感标识、消费限制周期以及两个 SHA-256。

控制器会在创建 Docker 网络或读取 secret 文件之前重新校验这些值。任一值缺失、批准包被改写、消费上限超过 `$1.00`、auto-reload 未明确关闭，或当前值不等于批准目标，执行都会失败。

## 面试说明

这一步展示的是 human-in-the-loop 的授权边界：Codex 可以把候选、控制、费用和密钥路径准备成可验证对象，但不能替 Security Engineer 接受冻结承诺或批准模型执行。批准使用文件哈希绑定具体输入和控制面；密钥值不进入审批证据；provider 限额、CLI 停止线和 supervisor 形成不同层次的费用控制。

## 官方依据

- [Creating and managing Workspaces](https://support.anthropic.com/en/articles/9796807-creating-and-managing-workspaces)
- [How do I pay for API usage?](https://support.anthropic.com/en/articles/8977456-how-do-i-pay-for-my-api-usage)
- [Cost and Usage Reporting in Console](https://support.anthropic.com/en/articles/9534590-cost-and-usage-reporting-in-console)
- [API Console Roles and Permissions](https://support.anthropic.com/en/articles/10186004-api-console-roles-and-permissions)
