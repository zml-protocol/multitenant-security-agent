# Claude Static Review v4 结果归档

本目录保存 Claude Code 对 AppSec v1 漏洞版本执行静态代码审查后生成的原始结果。

## 结果状态

- 审查方式：仅静态代码审查
- 动态请求：0
- 当前状态：Claude 草稿，等待 Security Engineer 裁决
- 已确认 finding：无
- 已确认严重性：无

`raw/` 中的 8 个文件是 Claude 的原始输出。归档后不得直接修改；`result-manifest.json` 记录每个文件的大小和 SHA-256，可用于验证证据完整性。后续对 finding 的接受、拒绝、影响判断和严重性判断，应记录在独立的裁决文件中，不应改写 Claude 的原始报告。

## 文件

- `raw/static-review-log.json`：静态审查过程与证据日志
- `raw/findings.json`：机器可读的审查结果和未执行测试矩阵
- `raw/findings.md`、`raw/findings.en.md`：中英文审查报告
- `raw/remediation-advice.md`、`raw/remediation-advice.en.md`：中英文修复建议草稿
- `raw/limitations.md`、`raw/limitations.en.md`：中英文限制说明
- `result-manifest.json`：本次运行的来源信息、状态和文件完整性清单

这些材料只代表独立 reviewer 的候选结论。是否构成真实安全问题，由 Security Engineer 根据已批准的安全需求、范围和证据作最终裁决。
