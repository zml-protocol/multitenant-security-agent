# Claude Reviewer 受控执行

[English](reviewer-execution.en.md) | 中文

状态：`implemented_validated_not_formally_authorized`

受控执行器把固定 Claude Code 运行时、只读 reviewer bundle、独立出站代理、secret 文件注入、固定模型与预算以及两阶段输出 schema 组合成一条 fail-closed 路径。当前只完成了无费用验证；正式启动门仍关闭。

## 固定命令

`reviewer/execution/controller.py` 为每个阶段生成固定参数：

- `--print`：非交互运行；
- `--restricted --bare`：只使用受控工作目录和 managed settings，跳过项目或用户自定义；
- `--model claude-sonnet-5`：固定模型；
- `--max-budget-usd 1.00`：Claude Code 原生费用停止线；
- `--max-turns 12`：agentic turn 硬上限；
- `--json-schema`：阶段输出必须符合固定 schema；
- `--no-session-persistence`：不持久化会话；
- `--permission-prompts none`：无人值守时不能临时批准新权限；
- `--tools Read,Glob,Grep`：仅允许读取隔离 bundle，不提供 Bash、编辑、Web、MCP 或浏览器工具。
- `--disallowedTools mcp__*`、`--disable-slash-commands` 和 `--no-chrome`：显式关闭 `--tools` 不覆盖的扩展入口。

Claude Code 的 `--max-turns` 不等于底层 API 请求计数。`maximum_model_api_calls=12` 和累计 100k/20k token 仍是审批与运行后核对边界；当前可硬停止的本地控制是 `$1.00`、12 turns、900 秒、1 MiB 捕获输出和容器资源限制。

## 凭据和网络路径

真实 key 将来只能位于运行前创建的临时只读 secret 文件。Docker 命令只包含文件路径；`reviewer-credential-exec` 在容器内部读取 key、设置 `ANTHROPIC_API_KEY`，然后直接 `exec` Claude。key 不进入 Docker environment metadata、命令行、bundle 或镜像。

Reviewer 仅加入临时 `--internal` 网络，通过 `HTTPS_PROXY=http://egress-proxy:3128` 访问独立代理。代理是唯一连接外网的组件，只允许 `api.anthropic.com:443` CONNECT。supervisor 在超时或输出越界时强制删除 reviewer 容器，并在保存结果前扫描 reviewer 与代理输出是否含 key。

## 无费用组合验证

运行：

```text
python -m scripts.reviewer_combined_smoke
```

2026-09-19 的最新验证结果：

- reviewer image：`sha256:d49654657cc6a7977adb7c50a03f613afa62b7fa71f70a1d78d83de8807b642a`；
- egress image：`sha256:dc4b0704ba84407d472ae93dd04dc01f80bbf2fb4f16d2adf12c93d1518ae235`；
- synthetic key 未进入 `docker inspect`、探测子进程、输出、代理日志或持久化结果；
- `claude doctor` 在无网络、无凭据条件下报告无安装问题，并确认更新被 managed environment 禁用；
- allowlisted TLS CONNECT 成功，非 allowlist 返回 403，reviewer 直连失败；
- 没有执行 `claude -p`，没有模型调用或费用。

初次 doctor 验证发现镜像缺少 `bubblewrap`。镜像随后固定安装 Anthropic 文档要求的 `bubblewrap` 与 `socat`，重建后 doctor 和组合 smoke 均通过。这个过程展示了为什么应验证实际 CLI 启动路径，而不只检查 JSON 文件。

## 正式候选

`assessment/appsec/v1/formal-candidate-attestation.json` 绑定冻结 commit、fixture、scenario、bundle manifest hash、三类 profile hash、批准的预算对象 hash、固定 Claude command hash 和本地镜像 ID。attestation 状态为 `validated_waiting_formal_start_approval`，内嵌 bundle 仍保持 `draft_not_for_claude`。

正式执行还要求：

- Security Engineer 确认评估期间的不可变性承诺；
- 完成最终 approver 和 UTC 时间；
- 创建项目专用 API key 和 workspace spend limit；
- 将 start gate 及 runtime、egress、execution、auth profile 的执行开关一次性绑定到已批准 attestation；
- 云部署前使用 registry digest 代替本地 image ID。

## 官方依据

- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference)
- [Claude Code programmatic usage](https://code.claude.com/docs/en/headless)
- [Claude Code environment variables](https://code.claude.com/docs/en/env-vars)
- [Claude Code settings precedence](https://code.claude.com/docs/en/settings)
