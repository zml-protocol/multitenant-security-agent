# Claude Reviewer 运行时准备审计

[English](claude-runtime.en.md) | 中文

状态：`audited_not_installed_not_authorized`

本文件记录正式 AppSec 评估所需的 Claude Code 运行时边界。审计只检查本机能力和官方要求；没有安装或启动 Claude，没有读取凭据内容，也没有改变 `approval_status`。正式执行仍需 Security Engineer 单独批准。

## 本机审计结果

| 项目 | 观察结果 | 对正式评估的影响 |
| --- | --- | --- |
| Claude Code | `claude` 命令未安装 | 当前无法启动 reviewer |
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

## 网络出口边界

当前 runner 的 `--network none` 适用于离线隔离验证，无法完成真实 Claude API 调用。正式运行需要一个单独实现并验证的受限出口代理。Docker 网络本身不能按域名可靠地执行 allowlist。

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
| Claude Code 安装与版本固定 | 未实现 | 构建并记录固定版本镜像 |
| Linux 运行依赖 | 未验证 | 在镜像内验证 Claude 与所选沙箱依赖 |
| 受限网络出口 | 未实现 | 实现代理 allowlist、拒绝规则与日志脱敏测试 |
| 专用凭据注入与子进程清理 | 未实现 | 选择 secret source，验证不进入输入、日志和输出 |
| 非必要连接、插件和 connectors 禁用 | 未实现 | 固化 managed settings 并验证实际连接 |
| 模型与费用预算 | 未批准 | 由 Security Engineer 单独批准 |
| 正式 Claude 执行 | 未授权 | 完成审批记录第 8 节后另行授权 |

因此当前结论是：离线 runner 隔离基础已经存在，但真实 Claude reviewer 运行时尚未准备完成，也未获执行授权。

## 官方资料

- [Claude Code setup](https://code.claude.com/docs/en/setup)
- [Claude Code authentication](https://code.claude.com/docs/en/authentication)
- [Claude Code network configuration](https://code.claude.com/docs/en/network-config)
- [Claude Code settings](https://code.claude.com/docs/en/settings)
- [Claude Code sandboxing](https://code.claude.com/docs/en/sandboxing)
