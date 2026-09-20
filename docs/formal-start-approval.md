# Claude Reviewer 手工启动批准包

[English](formal-start-approval.en.md) | 中文

状态：`approved_for_security_engineer_manual_launch`

本批准包绑定已经验证的漏洞候选与已经生成的 isolated reviewer workspace。Codex 已完成环境准备和容器验证。在项目所有者明确授权后，Codex 运行了一次隔离的最小模型 preflight；该服务只能看到固定探针文件，未挂载或读取 reviewer bundle，也未暴露 API key 值。正式评估尚未开始。

## 已绑定对象

| 对象 | 值 |
| --- | --- |
| 候选证明 SHA-256 | `c2cd87005bf1333be573df341e86837eca0f9c755fb6938fd0b6a2b1b01e76e7` |
| 启动批准包 SHA-256 | `258148e4c18dd68b8f241d07291469c0b3a81529362ea444089aedef55798193` |
| Handoff manifest SHA-256 | `9dc4e0e2dc2f9b6cf9b93ba8994762df5e260062ba44c9dfd05820a828c7d5ad` |
| 漏洞代码 commit | `14a7b48ae30b833962752e4d65b7e03ade5664a1` |
| Fixture / scenario / bundle | `fixture-256eb13b57860e22` / `scenario-7f3a` / `bundle-6a1a247aca19153c0d22` |
| Workspace | `.local/reviewer-handoffs/appsec-v1-phase1-ready-v4/` |
| 独立结果目录 | `.local/reviewer-results/appsec-v1-phase1-ready-v4/` |
| 模型 | `claude-sonnet-5` |
| Claude 工具 | `Read`、`Glob`、`Grep`、只允许 `/review/output` 的 `Write` |
| 禁止工具 | `Bash`、`Edit`、`WebFetch`、`WebSearch`、MCP 与浏览器 |
| 网络出口 | reviewer 无直接出口；proxy 只允许 `api.anthropic.com:443` |

机器可读对象是 `assessment/appsec/v1/formal-start-approval-package.json`。其中只包含职责、hash、预算和非秘密状态，不包含 API key 值。

## v4 准备与 preflight

已批准的 v2 手工运行因 `Read` 工具结果未传回模型而失败。Claude 未读取代码、未生成输出，也未形成 finding。v2 保持冻结，作为 reviewer 基础设施失败证据。

v3 移除了未在当前官方 CLI 参考中公开支持的 `--restricted` 参数，改由容器边界负责隔离。独立 preflight service 只挂载 `read-probe.txt`；Claude 精确返回预期值 `REVIEWER_READ_CHANNEL_OK_8D2F4A61`。同一次运行还暴露了当前 Claude Code 的文件权限规则语法，因此 managed rule 已修正为 `Edit(/review/output/**)`，实际暴露给模型的输出工具仍为 `Write`。

v4 的评估窗口不可变性承诺和 Security Engineer 人工启动已由 `project_owner` 于 `2026-09-20T03:02:30.589534Z` 正式批准。`codex_may_launch_claude` 保持 `false`。

## 批准后的单条启动命令

把 Anthropic API key 作为单行文本保存到仓库外，例如 `C:\secure\anthropic-api-key.txt`。随后在 Windows Terminal 中，从任意目录运行：

```text
D:\multitenant-security-agent\.local\reviewer-handoffs\appsec-v1-phase1-ready-v4\START-CLAUDE.cmd "C:\secure\anthropic-api-key.txt"
```

这条命令构建容器、以交互模式启动 Claude Code，并在退出后执行 `docker compose down -v`。脚本先验证人工批准，再由容器内 credential wrapper 读取 Compose secret；项目 Python 代码与 Codex 都不读取 key 值。

Claude 只能静态阅读 `/review/input`。不会启动应用、提供应用 token、发出 HTTP 请求或执行动态测试。结果保存在独立的 `/review/output` 宿主目录，包括中英文 findings、remediation advice、limitations 以及 JSON 日志。

## 运行限制

容器强制 900 秒超时、只读根文件系统、只读输入和每个输出文件 1 MiB 的进程级文件大小限制。交互式 Claude Code 当前没有可验证的原生 token、turn 或美元硬停止参数，因此 12 turns 与 `$1.00` 是已批准的规划边界；正式运行还依赖 Anthropic Workspace spend limit，并在结束后核对用量。达到规划边界时，Security Engineer 应退出会话。

## 面试说明

这一设计把评估准备、运行授权和安全结论分开：Codex 生成可复核环境；Security Engineer 绑定并亲自启动具体候选；Claude 只做静态代码审查并输出 finding 与修复建议草稿；Security Engineer 最终确认路径是否可达、是否需要动态证据、finding 是否成立及其影响和严重性。
