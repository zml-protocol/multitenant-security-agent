FROM node:22.17.0-bookworm-slim@sha256:b04ce4ae4e95b522112c2e5c52f781471a5cbc3b594527bcddedee9bc48c03a0

ARG CLAUDE_CODE_VERSION

WORKDIR /opt/claude-code
COPY --chown=root:root package.json package-lock.json ./

RUN test -n "$CLAUDE_CODE_VERSION" \
    && test "$(node -p 'require("./package-lock.json").packages["node_modules/@anthropic-ai/claude-code"].version')" = "$CLAUDE_CODE_VERSION" \
    && npm ci --omit=dev --no-audit --no-fund \
    && ln -s /opt/claude-code/node_modules/@anthropic-ai/claude-code/bin/claude.exe /usr/local/bin/claude \
    && claude --version | grep -F "${CLAUDE_CODE_VERSION} (Claude Code)"

RUN groupadd --gid 10001 reviewer \
    && useradd --uid 10001 --gid 10001 --create-home --shell /bin/bash reviewer \
    && mkdir -p /review/input /review/output /run/claude-config /etc/claude-code \
    && chmod 0755 /etc/claude-code \
    && chown -R reviewer:reviewer /review /run/claude-config

COPY --chown=root:root --chmod=0444 managed-settings.json /etc/claude-code/managed-settings.json
COPY --chown=root:root --chmod=0555 smoke.sh /usr/local/bin/reviewer-runtime-smoke

ENV CLAUDE_CODE_EXPECTED_VERSION=$CLAUDE_CODE_VERSION \
    CLAUDE_CONFIG_DIR=/run/claude-config \
    HOME=/home/reviewer \
    TMPDIR=/tmp

LABEL org.opencontainers.image.title="Multi-Tenant Security Agent Claude Reviewer" \
      org.opencontainers.image.version=$CLAUDE_CODE_VERSION \
      org.opencontainers.image.source="https://github.com/zml-protocol/multitenant-security-agent"

USER 10001:10001
WORKDIR /review/input

ENTRYPOINT ["claude"]
CMD ["--version"]
