# 多租户安全测试 Agent 实验项目

[English](README.en.md) | 中文

用于安全工程师面试的双工作流安全实验项目。长期目标与路线见 [docs/project-vision.md](docs/project-vision.md)，需求基线见 [spec.md](spec.md)，本阶段实现说明见 [docs/phase1.md](docs/phase1.md)，Reviewer 隔离设计见 [docs/reviewer-bundle.md](docs/reviewer-bundle.md)，分阶段 runner 见 [docs/reviewer-runner.md](docs/reviewer-runner.md)，Claude 运行时准备审计见 [docs/claude-runtime.md](docs/claude-runtime.md)，受限出口设计见 [docs/reviewer-egress.md](docs/reviewer-egress.md)。

最终目标包含 human-in-the-loop 的白盒 AppSec AI Agent Flow，以及 Alibaba Cloud 上的 DDoS / Network Security Incident Response Flow。已实现第一阶段：FastAPI + SQLite、两个租户六个测试用户、三个 GET 接口、四种模式、独立权限矩阵、脱敏 JSON/Markdown 报告、结构化应用日志和修复复测。当前没有接入模型、阿里云、SLS 或响应执行器。

工作流一的人工评估输入草案位于 [`assessment/appsec/v1/`](assessment/appsec/v1/)。开始 Claude 正式评估前，Security Engineer 需要审核 brief、security requirements 和 reviewer input manifest，并在代码冻结后的 Git commit 上记录批准。

## Windows PowerShell 快速开始

在项目根目录运行。无需激活虚拟环境，也无需修改 PowerShell 执行策略。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m scripts.demo
```

已有 `.venv` 或 `.local` 时，复用它们，跳过对应初始化步骤。初始化器拒绝覆盖现有数据库/令牌，避免修复复测时意外更换数据。默认 seed 为 42；数据可重复，令牌每次独立随机生成。邮箱使用 `example.com`，电话为明确的 `TEST-PHONE-...` 虚构占位符。

演示输出在 `reports/local/demo/`：四种模式及三次安全复测，各自包含 `report.json`、中文 `report.md` 和英文 `report.en.md`；`comparison.json` 汇总结果。该演示使用进程内 TestClient，不启动网络服务。

## 真实 HTTP 验证

一条命令临时启动安全模式、每秒最多两次请求、校验 54 项检查与日志关联，并自动停止服务（8000 端口须空闲）：

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke
```

报告：`reports/local/http-secure/`；服务端日志：`.local/smoke-access.log`。

若需手动操作，终端一启动应用：

```powershell
$env:LAB_MODE = 'secure'
.\.venv\Scripts\python.exe -m app.serve
```

终端二运行固定矩阵：

```powershell
.\.venv\Scripts\python.exe -m scanner.run --output reports/local/manual-secure
```

入口固定为 `http://127.0.0.1:8000`，CLI 不接受其他目标；只生成已知用户的 GET 请求，不跟随重定向、不使用环境代理。54 次请求约需 27 秒，单请求超时 10 秒。退出码：0 全部通过，1 存在确认违规，2 有无法判断项；违规与无法判断并存时返回 1。

## 漏洞切换与复测

在终端一用 Ctrl+C 停止应用，然后选择一种模式并重新启动：

```powershell
$env:LAB_MODE = 'same_tenant_bypass'
.\.venv\Scripts\python.exe -m app.serve
```

终端二再次运行执行器，使用单独输出目录：

```powershell
.\.venv\Scripts\python.exe -m scanner.run --output reports/local/manual-same-tenant
```

| LAB_MODE | 预期确认违规 | 缺失/无效凭据检查 |
| --- | ---: | --- |
| secure | 0 | 6 项全部通过 |
| same_tenant_bypass | 8 | 6 项全部通过 |
| cross_tenant_bypass | 18 | 6 项全部通过 |
| list_role_bypass | 4 | 6 项全部通过 |

恢复时停止应用，将 `LAB_MODE` 设回 `secure` 并重启，再运行同一矩阵。不要重新初始化 `.local`。模式只在启动时读取，无 HTTP 切换接口。默认安全模式；拼错模式直接启动失败。

## 代码导航

- `app/seed.py`：数据快照、独立令牌、SQLite 初始化。
- `app/main.py`：认证、三条业务路由、policy 调用和结构化审计；不包含场景答案。
- `app/policy.py`：默认安全授权实现。
- `evaluation/`：操作者专用的中性场景与 truth mapping，不进入 reviewer bundle。
- `reviewer/bundle.py`：构建单场景、脱敏、带完整性哈希的 reviewer bundle。
- `reviewer/runner.py`：准备隔离阶段输入、封存第一阶段输出，并强制执行人工批准的第二阶段释放门禁。
- `reviewer/runtime/`：固定 Claude Code 版本、基础镜像摘要、npm 完整性锁和强制 managed settings 的 Linux reviewer 镜像定义。
- `reviewer/egress/`：默认拒绝、代理唯一、固定 `api.anthropic.com:443` allowlist 的未启用出口基础。
- `fixtures/permissions.v1.json`：独立的显式权限预期。
- `fixtures/request-template.v1.json`：正常请求模板，不含凭据。
- `scanner/`：固定矩阵、响应证据判定和报告。
- `tests/`：完整矩阵、模式独立性、修复复测、错误/超时夹具与日志脱敏。
- `scripts/demo.py`：进程内完整演示；`scripts/smoke.py`：真实 HTTP 验证；`scripts/reviewer_runtime_smoke.py`：无凭据、离线 reviewer 容器隔离验证；`scripts/reviewer_egress_smoke.py`：代理 allowlist 与直连阻断验证。

`.local/`、数据库、令牌、运行日志和本地报告已被 Git 忽略。原始响应不落盘；报告只保留用户/租户测试 ID、命中的字段名和证据引用。当前为本地实验认证方案，不是生产身份平台。
