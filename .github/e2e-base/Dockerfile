# CI-optimized E2E image: extends base image with Python deps, Playwright, and workspace code.
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
# "release" installs published packages from PyPI, then overrides the package
# under test from EXTRA_INDEX_URL (defaults to Test PyPI).
ARG INSTALL_MODE=workspace
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

# Release mode: replace workspace pyproject.toml with a rendered template that
# declares PyPI deps + the package under test pinned from EXTRA_INDEX_URL.
COPY --chown=testuser:testuser .github/e2e-base/template.pyproject.toml /workspace/.github/e2e-base/template.pyproject.toml

# Workspace mode: re-run uv sync to register editable packages.
# Release mode: render template, uv sync (resolves everything including the
# package under test from the configured index), then install Playwright.
RUN if [ "$INSTALL_MODE" = "release" ]; then \
        cd /workspace && \
        rm -rf .venv && \
        sed -e "s|{{PKG_VERSION}}|${PKG_VERSION}|g" \
            -e "s|{{EXTRA_INDEX_URL}}|${EXTRA_INDEX_URL}|g" \
            .github/e2e-base/template.pyproject.toml > pyproject.toml && \
        # Strip workspace source — uv errors on it outside workspace context
        sed -i '/\[tool\.uv\.sources\.jupyter-deploy\]/,+1d' libs/pytest-jupyter-deploy/pyproject.toml && \
        uv sync && \
        .venv/bin/playwright install firefox && \
        ln -sf ~/.cache/ms-playwright/firefox-*/firefox/firefox ~/.local/bin/firefox; \
    else \
        cd /workspace && uv sync --all-packages; \
    fi

CMD ["sleep", "infinity"]
