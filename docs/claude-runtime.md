# Claude Reviewer 运行时准备审计

[English](claude-runtime.en.md) | 中文

状态：`runtime_foundation_implemented_not_authorized`

本文件记录正式 AppSec 评估所需的 Claude Code 运行时边界。初始审计只检查本机能力和官方要求；后续实现只把 Claude Code 安装进隔离 Docker 镜像并执行离线版本检查，没有在宿主机安装、认证或调用模型，没有读取凭据内容，也没有改变 `approval_status`。正式执行仍需 Security Engineer 单独批准。

## 本机审计结果

| 项目 | 观察结果 | 对正式评估的影响 |
| --- | --- | --- |
| Claude Code | 宿主机未安装 `claude` 命令；隔离镜像内固定为 `2.1.278` | Reviewer 必须通过受控容器运行 |
| Node.js / npm | Node.js `v22.17.0`，npm `10.9.2`；`npm.cmd` 可用 | 可支持安装流程，但本次未安装 |
| Windows | 原生 Windows 环境，已安装 Git for Windows | Claude 可在原生 Windows 运行，但官方 Bash 沙箱不支持原生 Windows |
| WSL | 只发现 Docker Desktop 的内部发行版，没有用户 Linux 发行版 | 当前没有可用于交互式 Claude 沙箱的 WSL2 工作区 |
| Docker | 客户端和服务端 `29.8.0`，已有 `alpine:3.22` | 已验证的项目 runner 可以提供文件系统隔离 |
| Claude 环境变量 | 未发现名称以 `ANTHROPIC` 或 `CLAUDE` 开头的变量 | 没有发现可供 reviewer 使用的环境凭据 |
| Claude 用户目录 | `%USERPROFILE%\.claude` 存在；未读取其内容 | 不得把宿主用户目录挂入 reviewer 容器，也不能把它视为已批准凭据来源 |

检查没有读取环境变量值或 `%USERPROFILE%\.claude` 中的文件。

## 官方运行要求

Anthropic 文档说明：Claude Code 支持 Windows 10 1809 及以上版本，最低 4 GB RAM，并需要网络连接。原生安装是推荐安装方式，且原生安装默认自动更新。原生 Windows 不支持 Claude Code 的 Bash 沙箱；该沙箱支持 Linux 和 WSL2，Linux/WSL2 还需要 `bubblewrap` 与 `socat`。

首次交互式登录通常打开浏览器。也可以使用 `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN`、`CLAUDE_CODE_OAUTH_TOKEN` 或 `apiKeyHelper` 等来源。Windows 登录凭据默认位于 `%USERPROFILE%\.claude\.credentials.json`。本项目不会读取或复用该宿主文件。

Claude Code 的沙箱只约束 Bash 类子进程；内置 Read/Edit/Write 工具仍由权限系统控制。沙箱子进程默认继承父进程环境。官方提供 `sandbox.credentials` 和 `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` 来限制子进程接触凭据，但这些设置不能代替容器挂载、网络出口和审批门禁。

## 本项目选择的运行模型

正式 reviewer 应使用版本固定的 Linux 容器镜像，而不是宿主原生 Windows 会话。容器必须满足以下边界：

- 只读挂载由 runner 校验过的阶段输入到 `/review/input`；
- 只有 `/review/output` 可写，并保持源仓库、父目录、`.git`、数据库、token 文件、`.env`、历史报告和操作者 truth mapping 不可见；
- 使用独立的 `CLAUDE_CONFIG_DIR`，不得挂载宿主 `%USERPROFILE%\.claude`；
- 固定并记录 Claude Code 版本，关闭正式运行期间的自动更新和插件安装；
- 禁用 Claude.ai MCP connectors、Artifacts、非必要流量和遥测，避免扩大可达主机与数据流；
- Claude 凭据由运行时注入，不写入 bundle、命令行、日志、报告或镜像层；子进程必须使用环境清理或显式 credential deny/mask；
- 容器文件系统保持只读，临时目录和 reviewer 输出使用独立受控写挂载；
- 仍由现有 `prepare`、phase 1 seal、人工授权和 phase 2 release 状态机控制输入释放。

容器是主要隔离边界。Claude Code 自带沙箱可作为纵深防御，但不能作为唯一控制，因为它不覆盖所有内置文件工具。

## 已实现的离线容器基础

`reviewer/runtime/` 现已包含：

- 基于摘要固定的 `node:22.17.0-bookworm-slim`；
- Claude Code `2.1.278` 和包含各平台包 integrity 的 `package-lock.json`；
- `/etc/claude-code/managed-settings.json`，禁止 bypass permission mode、Claude.ai connectors、Artifacts、skills/plugins 同步、自动更新、遥测、错误报告和非必要流量，并启用子进程环境清理；
- 非 root UID/GID `10001:10001`；
- Claude Code 子进程隔离所需的 `bubblewrap` 与 `socat`；
- 只从 `/run/secrets/anthropic_api_key` 读取凭据的容器内启动包装器；
- 由现有 runner 生成的只读输入、可写输出、只读根文件系统、受限 tmpfs、删除 capabilities、`no-new-privileges` 和 `--network none` 参数。

`python -m scripts.reviewer_runtime_smoke` 已在 Docker Desktop 上通过，并确认版本、UID、文件系统边界、临时配置、无默认路由和无凭据环境变量。脚本使用本次构建的镜像 ID 执行 smoke 并把 ID 写入本地结果；正式运行仍须使用并记录不可变 registry digest。

基础 smoke 只执行 `claude --version` 和本地边界探测。后续组合 smoke 又执行了无网络、无凭据的 `claude doctor`，确认 CLI 接受 managed environment 且没有安装问题；真实模型会话中的最终设置证据仍须由 canary 提供。

## 网络出口边界

旧 runner 的 `--network none` 适用于离线隔离验证，无法完成真实 Claude API 调用。[受限出口](reviewer-egress.md)已经通过独立和组合 smoke；新的[isolated handoff](reviewer-execution.md)生成 internal + proxy Compose 拓扑，由 Security Engineer 批准后手工创建。Docker 网络负责阻断 reviewer 直连，独立代理负责执行主机 allowlist。

最小主机集合取决于认证方式：

| 主机 | 用途 | 本项目策略 |
| --- | --- | --- |
| `api.anthropic.com` | Anthropic API 请求 | 正式 reviewer 必需 |
| `platform.claude.com` | Console/OAuth token 交换、刷新和撤销 | 仅所选认证流程需要时允许 |
| `claude.ai`、`claude.com` | claude.ai 交互式登录 | 正式非交互容器优先避免 |
| `mcp-proxy.anthropic.com` | Claude.ai MCP connectors | 禁止，并关闭 connectors |
| `downloads.claude.ai`、`registry.npmjs.org` | 安装、更新或插件依赖 | 构建镜像时处理；正式运行禁止 |
| Datadog intake、`raw.githubusercontent.com`、`code.claude.com` 等可选主机 | 遥测、错误报告、release notes 或文档查询 | 正式运行禁止并关闭非必要流量 |

出口代理还必须拒绝任意 IP、重定向到非 allowlist 主机以及 reviewer 自行增加域名。代理日志只能保留连接元数据，不记录认证头、请求正文或模型内容。

## 凭据生命周期

正式运行前需要选择一种专用、可撤销、最小权限的 reviewer 凭据。建议由外部 secret source 或 `apiKeyHelper` 在启动时提供短期凭据，并把 secret source 挂载在 bundle 之外。不得把开发者个人 Claude 配置目录直接交给容器。

运行时应记录凭据来源类型和非敏感标识，但不记录 secret。结束后撤销或失效该凭据，清除临时配置目录，并验证输出中不存在 token。任何真实认证、模型调用或费用发生前，都需要单独批准模型、预算、凭据方式和网络 allowlist。

## 准备状态

| 控制 | 状态 | 进入正式评估前的工作 |
| --- | --- | --- |
| 冻结 bundle 与哈希校验 | 已实现 | 使用已记录的正式候选并再次校验 |
| 只读输入、可写输出、无源仓库挂载 | 已通过真实 Docker smoke test | 在最终 Claude 镜像上重复验证 |
| 两阶段 seal/release 门禁 | 已实现 | 维持人工授权 |
| Claude Code 安装与版本固定 | 已实现离线镜像基础 | 正式运行前记录不可变 registry digest |
| Linux 运行基础 | 已验证 | 已验证二进制、非 root 身份、Docker 文件边界，且 `claude doctor` 无安装问题 |
| 受限网络出口 | 组合 smoke 已通过 | 正式启动后只启用已验证的 internal + proxy 拓扑 |
| 专用凭据注入与子进程清理 | 专用 workspace API key 方案已批准，secret-file 包装器与 synthetic sentinel 组合验证已通过 | Security Engineer 手工启动时提供仓库外 key 文件；项目不读取其值 |
| 非必要连接、插件和 connectors 禁用 | managed settings 已固化 | 联网前验证 Claude 实际加载设置及真实连接 |
| 模型与费用预算 | 固定模型与单次预算已批准；交互 CLI 不支持费用/turn 硬停止 | 使用 900 秒 timeout、Workspace spend limit，并在手工运行后核对 usage |
| 正式 Claude 执行 | v2 已批准由 Security Engineer 手工启动 | 首次尝试未形成评估结果；Codex 不启动模型 |

因此当前结论是：修复后的固定版本 reviewer 容器、组合受限出口、三种 secret 文件格式和挂载边界均已通过无模型验证；v2 的 Security Engineer 手工启动批准已经记录。

## 官方资料

- [Claude Code setup](https://code.claude.com/docs/en/setup)
- [Claude Code authentication](https://code.claude.com/docs/en/authentication)
- [Claude Code network configuration](https://code.claude.com/docs/en/network-config)
- [Claude Code settings](https://code.claude.com/docs/en/settings)
- [Claude Code sandboxing](https://code.claude.com/docs/en/sandboxing)
