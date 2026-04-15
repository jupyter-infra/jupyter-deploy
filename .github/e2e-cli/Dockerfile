# CI-optimized E2E image for CLI release testing.
# Extends base image with Python deps, Playwright, and workspace code.
#
# Layer strategy (dep-first COPY):
#   1. Copy dependency manifests only → uv sync (cached when deps unchanged)
#   2. Install Playwright browsers (cached when version unchanged)
#   3. Copy full workspace source (cheap, changes every run)
#
# The base image is built from libs/pytest-jupyter-deploy (system packages, Terraform, AWS CLI).
# This image adds everything that `just e2e-sync` would normally install at runtime.

ARG BASE_IMAGE=jupyter-deploy-e2e:latest
FROM ${BASE_IMAGE}

# Install mode: "workspace" (default) installs from local source via uv sync.
# "pypi" installs the CLI from Test PyPI using a template pyproject.
ARG INSTALL_MODE=workspace
# Install variant (only applies when INSTALL_MODE=pypi):
#   "bare" — CLI only, no AWS deps, no template
#   "aws"  — CLI with [aws] extra + base template from workspace
ARG INSTALL_VARIANT=aws
ARG PKG_VERSION=""
ARG EXTRA_INDEX_URL=https://test.pypi.org/simple/

# --- Dependency layer (cached when pyproject.toml unchanged) ---
# Copy manifests and create stub files that hatchling validates (LICENSE, README.md).
# Stubs avoid copying actual content that would bust the cache on every edit.
# No uv.lock — resolve deps freely to match what users get on `pip install`.
USER root
COPY --chown=testuser:testuser pyproject.toml /workspace/
COPY --chown=testuser:testuser libs/jupyter-deploy/pyproject.toml /workspace/libs/jupyter-deploy/
COPY --chown=testuser:testuser libs/jupyter-deploy-tf-aws-ec2-base/pyproject.toml /workspace/libs/jupyter-deploy-tf-aws-ec2-base/
COPY --chown=testuser:testuser libs/jupyter-infra-tf-aws-iam-ci/pyproject.toml /workspace/libs/jupyter-infra-tf-aws-iam-ci/
COPY --chown=testuser:testuser libs/pytest-jupyter-deploy/pyproject.toml /workspace/libs/pytest-jupyter-deploy/
RUN for lib in jupyter-deploy jupyter-deploy-tf-aws-ec2-base jupyter-infra-tf-aws-iam-ci pytest-jupyter-deploy; do \
        touch /workspace/libs/$lib/LICENSE /workspace/libs/$lib/README.md; \
    done && chown -R testuser /workspace/libs
USER testuser

RUN cd /workspace && uv sync --all-packages

# --- Playwright layer (cached when playwright version unchanged) ---
RUN cd /workspace && uv run playwright install firefox && \
    mkdir -p ~/.local/bin && \
    ln -sf ~/.cache/ms-playwright/firefox-*/firefox/firefox ~/.local/bin/firefox

# --- Source code layer (changes every run, but cheap) ---
USER root
COPY --chown=testuser:testuser . /workspace/
USER testuser

# Copy template pyproject files for release mode.
COPY --chown=testuser:testuser .github/e2e-cli/pyproject.bare.toml /workspace/.github/e2e-cli/pyproject.bare.toml
COPY --chown=testuser:testuser .github/e2e-cli/pyproject.aws.toml /workspace/.github/e2e-cli/pyproject.aws.toml

# Workspace mode: re-run uv sync to register editable packages.
# Release mode: render template, uv sync (resolves the CLI from the configured index),
# then install Playwright.
#   bare variant: CLI from Test PyPI, plugin from workspace, no AWS deps
#   aws variant:  CLI[aws] from Test PyPI, base template + plugin from workspace
RUN if [ "$INSTALL_MODE" = "pypi" ]; then \
        cd /workspace && \
        rm -rf .venv && \
        uv cache clean && \
        sed -e "s|{{PKG_VERSION}}|${PKG_VERSION}|g" \
            -e "s|{{EXTRA_INDEX_URL}}|${EXTRA_INDEX_URL}|g" \
            .github/e2e-cli/pyproject.${INSTALL_VARIANT}.toml > pyproject.toml && \
        rm -f .github/e2e-cli/pyproject.bare.toml .github/e2e-cli/pyproject.aws.toml && \
        # Strip workspace sources — uv errors on them outside workspace context
        sed -i '/\[tool\.uv\.sources\.jupyter-deploy\]/,+1d' libs/pytest-jupyter-deploy/pyproject.toml && \
        sed -i '/\[tool\.uv\.sources\.\(jupyter-deploy\|pytest-jupyter-deploy\)\]/,+1d' libs/jupyter-deploy-tf-aws-ec2-base/pyproject.toml && \
        uv sync && \
        .venv/bin/playwright install firefox && \
        ln -sf ~/.cache/ms-playwright/firefox-*/firefox/firefox ~/.local/bin/firefox; \
    else \
        cd /workspace && \
        rm -f .github/e2e-cli/pyproject.bare.toml .github/e2e-cli/pyproject.aws.toml && \
        uv sync --all-packages; \
    fi

CMD ["sleep", "infinity"]
