FROM node:22.17.0-bookworm-slim@sha256:b04ce4ae4e95b522112c2e5c52f781471a5cbc3b594527bcddedee9bc48c03a0

RUN groupadd --gid 10002 egress \
    && useradd --uid 10002 --gid 10002 --no-create-home --shell /usr/sbin/nologin egress

COPY --chown=root:root --chmod=0555 proxy.js /opt/reviewer-egress/proxy.js

LABEL org.opencontainers.image.title="Multi-Tenant Security Agent Reviewer Egress Proxy" \
      org.opencontainers.image.source="https://github.com/zml-protocol/multitenant-security-agent"

USER 10002:10002
WORKDIR /opt/reviewer-egress
EXPOSE 3128

ENTRYPOINT ["node", "/opt/reviewer-egress/proxy.js"]
