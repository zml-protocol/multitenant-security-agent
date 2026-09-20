# Reviewer 凭据与预算门禁

[English](reviewer-auth-budget.en.md) | 中文

状态：`approved_not_formally_authorized`

本阶段固化并批准 Claude reviewer 的凭据来源、模型和预算字段，并用纯本地 synthetic sentinel 验证秘密边界。它没有配置真实 API key、没有调用模型、没有产生费用。正式评估启动门现在只允许 Security Engineer 手工启动已绑定 workspace；项目与 Codex 的模型调用能力仍然关闭。

## 凭据设计

正式评估建议使用 Anthropic Console 中为本项目单独创建、可撤销的 workspace API key。不得复用 Windows 主机上的个人 Claude 登录、`%USERPROFILE%\.claude` 或其他个人配置。真实 key 只能在已批准运行启动时通过 `ANTHROPIC_API_KEY` 注入 reviewer 主进程，并且不得进入：

- Git、reviewer bundle、镜像层或持久化配置；
- 命令行参数、run manifest、Docker plan、日志或 reviewer 输出；
- Claude 启动的子进程；
- 评估报告或证据文件。

运行记录只允许保存凭据类型和之后填写的非秘密 key identifier。每次正式运行后必须撤销该 key，并清除临时 Claude 配置目录。

## 固定模型和已批准预算

`reviewer/auth_budget/profile.json` 是已由 Security Engineer 批准的机器可读方案；其中执行开关保持关闭，因为凭据只在 Security Engineer 手工启动容器时提供：

| 控制 | 提案值 |
| --- | ---: |
| 模型 | `claude-sonnet-5` |
| 每次运行累计输入 token 上限 | 100,000 |
| 每次运行累计输出 token 上限 | 20,000 |
| 模型 API 调用上限 | 12 |
| Agentic turn 规划边界 | 12 |
| 补充工具调用上限 | 30 |
| 最长运行时间 | 900 秒 |
| 标准价格规划值 | 输入 $2 / MTok，输出 $10 / MTok |
| 按 token 上限计算的标准成本 | $0.40 |
| 单次运行审批上限 | $1.00 |

模型和价格依据 2026-09-19 的 Anthropic 官方文档。批准人、UTC 时间和审批对象 SHA-256 已写入 profile 与审批记录。正式运行前仍须重新确认模型有效性和价格。

$0.40 是按未缓存的标准输入/输出价格计算的规划值。Claude Code 可能产生多次 API 请求、缓存计费或重试，本地 preflight 无法替代提供商计费控制。固定版本 CLI 的 `--max-budget-usd` 和 `--max-turns` 只适用于非交互 `--print`，因此交互式评估使用 900 秒外层 timeout、独立 Anthropic Workspace spend limit，并在运行后核对实际 usage。API 调用数和累计 token 值仍是审批与核对边界，不是本地硬停止。

## Synthetic sentinel 验证

运行：

```text
python -m scripts.reviewer_auth_budget_smoke
```

脚本只在父 Python 进程内存中的环境副本放入随机、无效的 synthetic key，然后：

1. 校验 profile 审批 hash 有效，同时模型调用仍关闭；
2. 生成不含 key 值的离线 execution envelope；
3. 从子进程环境删除 `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN` 和 `CLAUDE_CODE_OAUTH_TOKEN`；
4. 检查 sentinel 不在子进程命令行、子进程环境、现有冻结 reviewer bundle 或持久化输出中；
5. 只把布尔验证结果写入 Git 忽略的 `.local/reviewer-auth-budget/`。

该验证不建立网络连接，也不运行 Claude。它证明本项目当前的配置和本地验证路径不会把假凭据复制到上述位置；真实 key 由 Security Engineer 在项目外保管，并只在手工 Docker Compose 启动时作为 secret 文件提供。

## 仍然关闭的项目侧门禁

- `formal_execution_authorized` 为 `false`；
- `model_invocation_enabled` 为 `false`；
- `approval.approved` 为 `true`，但 `model_invocation_enabled` 仍为 `false`；
- `assessment/appsec/v1/start-gate.json` 对 v2 为 `approved_for_security_engineer_manual_launch`，同时 `codex_may_launch_claude` 保持 `false`；
- runtime、egress 和 execution profile 的 `formal_execution_authorized` 均为 `false`。

## 官方依据

- [Anthropic 模型概览](https://platform.claude.com/docs/en/models/overview)
- [Anthropic API 定价](https://platform.claude.com/docs/en/about-claude/pricing)
- [Claude Code 认证](https://code.claude.com/docs/en/authentication)
- [Anthropic API rate limits 与 spend limits](https://platform.claude.com/docs/en/api/rate-limits)
