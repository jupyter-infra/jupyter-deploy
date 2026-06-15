# roborev CI review image.
#
# A standalone runtime for `roborev ci review`: roborev plus the claude-code
# agent it shells out to, git, gh (roborev posts the PR comment via gh), and jq.
# Consumer workflows assume an IAM role, pull this image from ECR, and run it
# against a PR ref range. The image holds no credentials; AWS and GitHub creds
# are passed in as environment at run time.
#
# All tool versions are pinned so a given image tag is reproducible and the
# supply chain is auditable. The roborev tarball is checksum-verified.

FROM node:22-bookworm-slim

# Pinned tool versions.
ARG ROBOREV_VERSION=0.58.0
ARG ROBOREV_SHA256=21539085e4f5dcf67da9f6a5eec090da8fe2aec10d4892f4a509f5fc269be4d3
ARG CLAUDE_CODE_VERSION=2.1.177
ARG GH_VERSION=2.94.0

# System packages: git for the ref range, jq for JSON in the review workflow,
# curl/ca-certificates for the installs below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        jq \
    && rm -rf /var/lib/apt/lists/*

# roborev — pinned release, SHA256-verified.
RUN curl -sfLO "https://github.com/roborev-dev/roborev/releases/download/v${ROBOREV_VERSION}/roborev_${ROBOREV_VERSION}_linux_amd64.tar.gz" \
    && echo "${ROBOREV_SHA256}  roborev_${ROBOREV_VERSION}_linux_amd64.tar.gz" | sha256sum --check \
    && tar xzf "roborev_${ROBOREV_VERSION}_linux_amd64.tar.gz" -C /usr/local/bin roborev \
    && rm -f "roborev_${ROBOREV_VERSION}_linux_amd64.tar.gz" \
    && roborev version

# gh CLI — pinned release tarball.
RUN curl -sfLO "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_amd64.tar.gz" \
    && tar xzf "gh_${GH_VERSION}_linux_amd64.tar.gz" \
    && install "gh_${GH_VERSION}_linux_amd64/bin/gh" /usr/local/bin/gh \
    && rm -rf "gh_${GH_VERSION}_linux_amd64" "gh_${GH_VERSION}_linux_amd64.tar.gz" \
    && gh --version

# claude-code agent — pinned npm release. roborev invokes `claude`.
RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
    && claude --version

LABEL org.opencontainers.image.source="https://github.com/jupyter-infra/jupyter-deploy"
LABEL org.opencontainers.image.description="roborev CI review runner (roborev + claude-code agent)"

CMD ["roborev", "--help"]
