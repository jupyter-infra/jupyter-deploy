ARG CLAUDE_CODE_VERSION
ARG CODEX_VERSION
ARG SSH_SERVER_IMAGE

# Coding agent CLIs. The npm packages wrap native binaries but need a newer node
# than trixie ships, so install them here and copy the prefix (plus node, for the
# codex launcher) into the final image.
FROM node:22-trixie-slim AS ai-clis
ARG CLAUDE_CODE_VERSION
ARG CODEX_VERSION
RUN test -n "$CLAUDE_CODE_VERSION" && test -n "$CODEX_VERSION" && \
    npm install -g --prefix /opt/ai-clis \
      "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
      "@openai/codex@${CODEX_VERSION}" && \
    npm cache clean --force

# The SSH server the editors connect to, published as an image to copy the binary from.
FROM ${SSH_SERVER_IMAGE} AS ssh-server

FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim
ARG CODEX_PROFILE_PREFIX
ARG CODEX_MODEL_PATTERNS

USER root

# git for the editor and the coding agents' repo awareness; procps (ps) for the
# Codex TUI, which tracks its background app-server by pid; curl for the editor's
# download of its remote server on first connect (tar and libstdc++ come with the base).
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends curl git procps && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash jovyan

COPY --from=ssh-server /remote-access-server /usr/local/bin/remote-access-server

# Installed outside /home/jovyan, which the data volume mounts over. Both CLIs
# reach Bedrock with the workspace's EKS Pod Identity credentials; the region and
# inference profile prefix come from the WorkspaceTemplate env.
COPY --from=ai-clis /usr/local/bin/node /usr/local/bin/node
COPY --from=ai-clis /opt/ai-clis /opt/ai-clis
RUN ln -s /opt/ai-clis/bin/claude /usr/local/bin/claude && \
    ln -s /opt/ai-clis/bin/codex /usr/local/bin/codex
COPY claude-managed-settings.json /etc/claude-code/managed-settings.json
COPY codex-config.toml /etc/codex/config.toml
# Codex's model is pinned at build from the installed release's catalog so it follows the pinned
# version and the models IAM allows; the script documents the placeholder and failure cases.
COPY pick-codex-model.py /tmp/pick-codex-model.py
RUN python3 /tmp/pick-codex-model.py "$CODEX_PROFILE_PREFIX" "$CODEX_MODEL_PATTERNS" /etc/codex/config.toml workspace_ && \
    rm /tmp/pick-codex-model.py

RUN chmod -R a+r /etc/claude-code /etc/codex

WORKDIR /home/jovyan
USER jovyan
ENV HOME=/home/jovyan

# Loopback only: the ws-proxy sidecar is the one client. The host key persists in
# /home/jovyan/.ssh on the workspace volume, so a restart keeps the fingerprint.
ENTRYPOINT ["/usr/local/bin/remote-access-server", "--port", "2222"]
