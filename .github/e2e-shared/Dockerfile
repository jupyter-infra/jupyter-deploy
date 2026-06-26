# CI-optimized E2E image: extends the foundational image with Python deps,
# Playwright, and workspace code. Template-shared — base and eks-oidc tests run
# in the same image; the TEMPLATE build-arg selects the published-package
# pyproject for pypi-mode installs (see the pypi branch below).
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
# "pypi" installs published packages from PyPI using a template pyproject.
ARG INSTALL_MODE=workspace
# Install variant (only applies when INSTALL_MODE=pypi):
#   "release" (default) — renders pyproject.release.toml with placeholders
#   "canary" — uses pyproject.canary.toml (all from prod PyPI, no pins)
ARG INSTALL_VARIANT=release
ARG PKG_VERSION=""
ARG EXTRA_INDEX_URL=https://test.pypi.org/simple/
# Template under test (only applies when INSTALL_MODE=pypi): selects which
# .github/e2e-<template>/pyproject.*.toml declares the published package.
#   "base"     — jupyter-deploy-tf-aws-ec2-base
#   "eks-oidc" — jupyter-deploy-tf-aws-eks-oidc
ARG TEMPLATE=base

# --- Dependency layer (cached when pyproject.toml unchanged) ---
# Copy manifests and create stub files that hatchling validates (LICENSE, README.md).
# Stubs avoid copying actual content that would bust the cache on every edit.
# No uv.lock — resolve deps freely to match what users get on `pip install`.
USER root
COPY --chown=testuser:testuser pyproject.toml /workspace/
COPY --chown=testuser:testuser libs/jupyter-deploy/pyproject.toml /workspace/libs/jupyter-deploy/
COPY --chown=testuser:testuser libs/jupyter-deploy-tf-aws-ec2-base/pyproject.toml /workspace/libs/jupyter-deploy-tf-aws-ec2-base/
COPY --chown=testuser:testuser libs/jupyter-deploy-tf-aws-eks-oidc/pyproject.toml /workspace/libs/jupyter-deploy-tf-aws-eks-oidc/
COPY --chown=testuser:testuser libs/jupyter-infra-tf-aws-iam-ci/pyproject.toml /workspace/libs/jupyter-infra-tf-aws-iam-ci/
COPY --chown=testuser:testuser libs/pytest-jupyter-deploy/pyproject.toml /workspace/libs/pytest-jupyter-deploy/
RUN for lib in jupyter-deploy jupyter-deploy-tf-aws-ec2-base jupyter-deploy-tf-aws-eks-oidc jupyter-infra-tf-aws-iam-ci pytest-jupyter-deploy; do \
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

# The pyproject templates (.github/e2e-<template>/pyproject.{release,canary}.toml)
# arrive with the full-source COPY above; TEMPLATE selects which template dir.

# Workspace mode: re-run uv sync to register editable packages (registers the
# package under test from local source — base AND eks-oidc are workspace members).
# Release mode: render template, uv sync (resolves everything including the
# published package under test from the configured index), then install Playwright.
#   release variant: sed-render placeholders from pyproject.release.toml
#   canary variant: copy pyproject.canary.toml as-is (no placeholders)
RUN if [ "$INSTALL_MODE" = "pypi" ]; then \
        cd /workspace && \
        rm -rf .venv && \
        uv cache clean && \
        if [ "$INSTALL_VARIANT" = "canary" ]; then \
            cp ".github/e2e-${TEMPLATE}/pyproject.canary.toml" pyproject.toml; \
        else \
            sed -e "s|{{PKG_VERSION}}|${PKG_VERSION}|g" \
                -e "s|{{EXTRA_INDEX_URL}}|${EXTRA_INDEX_URL}|g" \
                ".github/e2e-${TEMPLATE}/pyproject.release.toml" > pyproject.toml && \
            # Strip workspace source — uv errors on it outside workspace context
            sed -i '/\[tool\.uv\.sources\.jupyter-deploy\]/,+1d' libs/pytest-jupyter-deploy/pyproject.toml; \
        fi && \
        # Drop the now-unused pyproject templates so the image ships no stale copies.
        rm -rf .github/e2e-base .github/e2e-eks-oidc && \
        uv sync && \
        .venv/bin/playwright install firefox && \
        ln -sf ~/.cache/ms-playwright/firefox-*/firefox/firefox ~/.local/bin/firefox; \
    else \
        cd /workspace && \
        rm -rf .github/e2e-base .github/e2e-eks-oidc && \
        uv sync --all-packages && \
        uv run playwright install firefox && \
        ln -sf ~/.cache/ms-playwright/firefox-*/firefox/firefox ~/.local/bin/firefox; \
    fi

CMD ["sleep", "infinity"]
