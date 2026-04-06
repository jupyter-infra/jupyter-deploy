# List all available commands
default:
    @just --list

# Run all linting and formatting tools
lint:
    uv run ruff format
    uv run ruff check --preview --fix
    uv run mypy
    terraform fmt -recursive -write=true
    uv run yamllint .

# Run unit tests
unit-test:
    uv run pytest

# Detect container tool (finch or docker)
container-tool := `command -v finch >/dev/null 2>&1 && echo "finch" || echo "docker"`

# Host user UID/GID for running containers with correct permissions
export HOST_UID := `id -u`
export HOST_GID := `id -g`

# E2E image configuration (template-independent, vended by pytest-jupyter-deploy)
e2e-image-dir := `uv run python -c "from pytest_jupyter_deploy.image import IMAGE_PATH; print(IMAGE_PATH)"`
e2e-compose-file := e2e-image-dir + "/docker-compose.yml"
e2e-container-name := "jupyter-deploy-e2e"
e2e-image-tag := "latest"

# Default template for E2E tests
default-template := "tf-aws-ec2-base"

# Start E2E container in background (always builds to ensure correct UID/GID)
# Usage: just e2e-up [no-cache=true]
e2e-up no_cache="false":
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Building and starting E2E container with correct UID/GID (HOST_UID={{HOST_UID}}, HOST_GID={{HOST_GID}})..."
    mkdir -p {{justfile_directory()}}/test-results
    mkdir -p {{justfile_directory()}}/.auth

    # Update .env file with current values
    sed -i 's/^HOST_UID=.*/HOST_UID={{HOST_UID}}/' {{justfile_directory()}}/.env
    sed -i 's/^HOST_GID=.*/HOST_GID={{HOST_GID}}/' {{justfile_directory()}}/.env
    # Set Dockerfile path for compose (finch/nerdctl reads vars from .env, not process env)
    if grep -q '^E2E_DOCKERFILE=' {{justfile_directory()}}/.env; then
        sed -i 's|^E2E_DOCKERFILE=.*|E2E_DOCKERFILE={{e2e-image-dir}}/Dockerfile|' {{justfile_directory()}}/.env
    else
        echo 'E2E_DOCKERFILE={{e2e-image-dir}}/Dockerfile' >> {{justfile_directory()}}/.env
    fi
    # Resolve AWS_REGION from env or AWS config (must not be empty — SDK treats "" as valid)
    _AWS_REGION="${AWS_REGION:-$(aws configure get region 2>/dev/null || echo "")}"
    if [ -n "$_AWS_REGION" ]; then
        if grep -q '^AWS_REGION=' {{justfile_directory()}}/.env; then
            sed -i "s|^AWS_REGION=.*|AWS_REGION=$_AWS_REGION|" {{justfile_directory()}}/.env
        else
            echo "AWS_REGION=$_AWS_REGION" >> {{justfile_directory()}}/.env
        fi
    fi

    if [ "{{no_cache}}" = "true" ]; then
        echo "Building with --no-cache..."
        {{container-tool}} compose --project-directory {{justfile_directory()}} -f {{e2e-compose-file}} build --no-cache
    else
        {{container-tool}} compose --project-directory {{justfile_directory()}} -f {{e2e-compose-file}} build
    fi

    {{container-tool}} compose --project-directory {{justfile_directory()}} -f {{e2e-compose-file}} up -d e2e
    echo "E2E container started. Syncing latest code..."
    just e2e-sync
    echo "✓ E2E container ready"

# Stop E2E container
e2e-down:
    @echo "Stopping E2E container..."
    {{container-tool}} compose --project-directory {{justfile_directory()}} -f {{e2e-compose-file}} down

# Sync project files to E2E container (for iterating without building image)
# NOTE: If you're not seeing your changes, use 'just e2e-build' instead
e2e-sync:
    #!/usr/bin/env bash
    set -euo pipefail

    # Check if container is running
    if ! ({{container-tool}} compose --project-directory {{justfile_directory()}} -f {{e2e-compose-file}} ps e2e) | grep -qE "(Up|running)"; then
        echo "Error: E2E container is not running. Start it with: just e2e-up"
        exit 1
    fi

    echo "Syncing project files to E2E container..."

    # Copy project files to container (excluding .venv, project directories, and build artifacts)
    {{container-tool}} exec {{e2e-container-name}} bash -c "
        echo 'Removing old .venv...'
        rm -rf /workspace/.venv

        echo 'Copying project files...'
        # We'll use the container tool to copy files
    "

    # Use tar to copy files efficiently (excluding project directories which are mounted)
    echo "Copying files from host to container..."
    cd {{justfile_directory()}} && \
    tar --exclude='.venv' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache' \
        --exclude='test-results' \
        --exclude='.git' \
        --exclude='.ruff_cache' \
        --exclude='.mypy_cache' \
        --exclude='sandbox*' \
        --exclude='.auth' \
        -cf - . | \
    {{container-tool}} exec -i {{e2e-container-name}} tar -xf - -C /workspace

    echo "Running uv sync..."
    {{container-tool}} compose --project-directory {{justfile_directory()}} -f {{e2e-compose-file}} exec e2e bash -c "cd /workspace && uv sync --all-packages"

    echo "Installing Playwright browsers..."
    {{container-tool}} compose --project-directory {{justfile_directory()}} -f {{e2e-compose-file}} exec e2e bash -c "cd /workspace && uv run playwright install firefox"

    # Make Playwright's Firefox discoverable by Python's webbrowser module (used by `jd open`)
    {{container-tool}} compose --project-directory {{justfile_directory()}} -f {{e2e-compose-file}} exec e2e bash -c "mkdir -p ~/.local/bin && ln -sf ~/.cache/ms-playwright/firefox-*/firefox/firefox ~/.local/bin/firefox"

    echo "✓ E2E container synced successfully"

# Run E2E tests in containerized environment
# Usage: just test-e2e [project-dir] [test-filter] [options]
# Options: comma-separated key=value pairs (e.g., mutate=true,destroy=true,log-level=debug)
# Example: just test-e2e                                      # deploy sandbox-e2e from scratch (includes mutating tests)
# Example: just test-e2e sandbox-e2e                          # deploy sandbox-e2e from scratch (explicit)
# Example: just test-e2e sandbox2                             # test existing project (skips mutating tests)
# Example: just test-e2e sandbox2 test_users                  # test specific test on existing project
# Example: just test-e2e sandbox2 test_config_changes mutate=true   # test existing project with mutating tests
# Example: just test-e2e sandbox-e2e "" mutate=true,destroy=true    # deploy from scratch and destroy after tests
# Example: just test-e2e sandbox2 "" log-level=debug          # test with debug logging
# Example: just test-e2e sandbox2 test_application ci-dir=sandbox-ci  # CI mode with automated 2FA
test-e2e project_dir="sandbox-e2e" test_filter="" options="" template=default-template:
    #!/usr/bin/env bash
    set -euo pipefail


    # Track override file for cleanup
    OVERRIDE_FILE=""

    # Cleanup function
    cleanup() {
        [ -n "$OVERRIDE_FILE" ] && [ -f "$OVERRIDE_FILE" ] && rm -f "$OVERRIDE_FILE"
    }

    # Ensure cleanup on exit
    trap cleanup EXIT

    # Determine if this is a deployment from scratch
    IS_DEPLOYMENT_FROM_SCRATCH="false"
    if [ "{{project_dir}}" = "sandbox-e2e" ] || [ "{{project_dir}}" = "sandbox-e2e-ci" ]; then
        # Check if sandbox-e2e exists and is not empty
        if [ -d "{{project_dir}}" ] && [ -n "$(ls -A {{project_dir}} 2>/dev/null)" ]; then
            # sandbox-e2e exists and is not empty - treat as existing project
            IS_DEPLOYMENT_FROM_SCRATCH="false"
            echo "Mode: Test existing project ({{project_dir}})"
        else
            # sandbox-e2e is empty or doesn't exist - deploy from scratch
            IS_DEPLOYMENT_FROM_SCRATCH="true"
            # Create empty directory for mounting (will be populated by tests)
            mkdir -p "{{project_dir}}"
            echo "Mode: Deploy from scratch ({{project_dir}})"
        fi
    else
        # Validate existing project directory exists
        if [ ! -d "{{project_dir}}" ]; then
            echo "Error: Project directory '{{project_dir}}' does not exist"
            exit 1
        fi
        echo "Mode: Test existing project ({{project_dir}})"
    fi

    # Always mount project directory dynamically
    echo "Mounting project directory: {{project_dir}}"

    # Create test-results and .auth directories
    mkdir -p "{{justfile_directory()}}/test-results"
    mkdir -p "{{justfile_directory()}}/.auth"
    echo "Cleaning old test artifacts..."
    rm -rf "{{justfile_directory()}}/test-results"/*

    # Update .env file with current values
    sed -i 's/^HOST_UID=.*/HOST_UID={{HOST_UID}}/' {{justfile_directory()}}/.env
    sed -i 's/^HOST_GID=.*/HOST_GID={{HOST_GID}}/' {{justfile_directory()}}/.env
    if grep -q '^E2E_DOCKERFILE=' {{justfile_directory()}}/.env; then
        sed -i 's|^E2E_DOCKERFILE=.*|E2E_DOCKERFILE={{e2e-image-dir}}/Dockerfile|' {{justfile_directory()}}/.env
    else
        echo 'E2E_DOCKERFILE={{e2e-image-dir}}/Dockerfile' >> {{justfile_directory()}}/.env
    fi
    # Resolve AWS_REGION from env or AWS config (must not be empty — SDK treats "" as valid)
    _AWS_REGION="${AWS_REGION:-$(aws configure get region 2>/dev/null || echo "")}"
    if [ -n "$_AWS_REGION" ]; then
        if grep -q '^AWS_REGION=' {{justfile_directory()}}/.env; then
            sed -i "s|^AWS_REGION=.*|AWS_REGION=$_AWS_REGION|" {{justfile_directory()}}/.env
        else
            echo "AWS_REGION=$_AWS_REGION" >> {{justfile_directory()}}/.env
        fi
    fi

    # Parse ci-dir from options early (needed for override file)
    CI_DIR=""
    OPTIONS_STR_EARLY="{{options}}"
    if echo "$OPTIONS_STR_EARLY" | grep -qE "ci-dir="; then
        CI_DIR=$(echo "$OPTIONS_STR_EARLY" | grep -oE "ci-dir=[^,]+" | cut -d'=' -f2)
        if [ ! -d "$CI_DIR" ]; then
            echo "Error: CI directory '$CI_DIR' does not exist"
            exit 1
        fi
        echo "CI directory: $CI_DIR"
    fi

    # Create temporary override file to mount the project directory, test-results, and optionally CI dir
    OVERRIDE_FILE="{{justfile_directory()}}/docker-compose.e2e-override.yml"
    {
        echo "services:"
        echo "  e2e:"
        echo "    volumes:"
        echo "      - ./{{project_dir}}:/workspace/{{project_dir}}"
        echo "      - ./test-results:/workspace/test-results"
        if [ -n "$CI_DIR" ]; then
            echo "      - ./${CI_DIR}:/workspace/${CI_DIR}"
        fi
    } > "$OVERRIDE_FILE"

    # Stop and restart container with new mounts (ensures clean mount state)
    echo "Restarting E2E container with project mount..."
    {{container-tool}} compose --project-directory {{justfile_directory()}} -f {{e2e-compose-file}} down
    {{container-tool}} compose --project-directory {{justfile_directory()}} -f {{e2e-compose-file}} -f "$OVERRIDE_FILE" up -d

    # Re-sync files after restart (container loses synced files when restarted)
    echo "Re-syncing project files after mount..."
    just e2e-sync

    # Check if container is running
    if ! {{container-tool}} ps --filter "name={{e2e-container-name}}" --format "{{{{.Status}}}}" | grep -q "Up"; then
        echo "Error: E2E container is not running. Start it with: just e2e-up"
        [ -n "$OVERRIDE_FILE" ] && rm -f "$OVERRIDE_FILE"
        exit 1
    fi

    # Verify test-results directory is writable (detect stale mount)
    echo "Verifying test-results directory is writable..."
    if ! {{container-tool}} exec {{e2e-container-name}} bash -c "touch /workspace/test-results/.mount-check && rm /workspace/test-results/.mount-check" 2>/dev/null; then
        echo "Error: test-results directory is not writable (stale mount detected)"
        echo ""
        echo "This happens when test-results was deleted while the container was running."
        echo "To fix: just e2e-down && just e2e-up"
        [ -n "$OVERRIDE_FILE" ] && rm -f "$OVERRIDE_FILE"
        exit 1
    fi
    echo "✓ test-results directory is writable"

    # Build the pytest command based on deployment mode
    # Resolve E2E tests directory: try jupyter-deploy-<template> first, then jupyter-infra-<template>
    if [ -d "libs/jupyter-deploy-{{template}}/tests/e2e" ]; then
        E2E_TESTS_DIR="libs/jupyter-deploy-{{template}}/tests/e2e"
    elif [ -d "libs/jupyter-infra-{{template}}/tests/e2e" ]; then
        E2E_TESTS_DIR="libs/jupyter-infra-{{template}}/tests/e2e"
    else
        echo "Error: Could not find E2E tests directory for template '{{template}}'"
        echo "Looked in: libs/jupyter-deploy-{{template}}/tests/e2e"
        echo "       and: libs/jupyter-infra-{{template}}/tests/e2e"
        exit 1
    fi
    if [ "$IS_DEPLOYMENT_FROM_SCRATCH" = "true" ]; then
        # Deploy from scratch - don't pass --e2e-existing-project (uses default config "base")
        PYTEST_ARGS="$E2E_TESTS_DIR -m e2e --e2e-tests-dir=$E2E_TESTS_DIR"
    else
        # Use existing project
        PYTEST_ARGS="$E2E_TESTS_DIR -m e2e --e2e-tests-dir=$E2E_TESTS_DIR --e2e-existing-project={{project_dir}}"
    fi

    # Add test filter if provided
    if [ -n "{{test_filter}}" ]; then
        PYTEST_ARGS="$PYTEST_ARGS -k {{test_filter}}"
    fi

    # Default log level
    LOG_LEVEL="INFO"

    # Parse options (comma-separated key=value pairs)
    OPTIONS_STR="{{options}}"
    if [ -n "$OPTIONS_STR" ]; then
        echo "Options: $OPTIONS_STR"

        # List of recognized options (for validation)
        RECOGNIZED_OPTIONS="mutate destroy log-level ci-dir"

        # Validate all options are recognized
        IFS=',' read -ra OPTS <<< "$OPTIONS_STR"
        for opt in "${OPTS[@]}"; do
            # Extract key from key=value
            opt_key=$(echo "$opt" | cut -d'=' -f1)
            if ! echo "$RECOGNIZED_OPTIONS" | grep -qw "$opt_key"; then
                echo "Error: Unrecognized option '$opt_key'"
                echo "Recognized options: $RECOGNIZED_OPTIONS"
                exit 1
            fi
        done

        # Check if destroy=true is used with existing project
        if echo "$OPTIONS_STR" | grep -q "destroy=true"; then
            if [ "$IS_DEPLOYMENT_FROM_SCRATCH" = "false" ]; then
                echo "Error: destroy=true cannot be used when testing against an existing project"
                echo "The destroy option only applies to deployments from scratch (e.g., sandbox-e2e)"
                echo ""
                echo "To destroy an existing project, manually run:"
                echo "  cd {{project_dir}} && jd down -y"
                exit 1
            fi
        fi

        # Parse mutate=true option
        if echo "$OPTIONS_STR" | grep -q "mutate=true"; then
            PYTEST_ARGS="$PYTEST_ARGS --with-mutating-cases"
            echo "  - mutating tests: enabled"
        fi

        # Parse destroy=true option
        if echo "$OPTIONS_STR" | grep -q "destroy=true"; then
            PYTEST_ARGS="$PYTEST_ARGS --destroy-after"
            echo "  - destroy after tests: enabled"
        fi

        # Parse log-level option
        if echo "$OPTIONS_STR" | grep -qE "log-level=(info|debug|warning|error)"; then
            LOG_LEVEL=$(echo "$OPTIONS_STR" | grep -oE "log-level=(info|debug|warning|error)" | cut -d'=' -f2 | tr '[:lower:]' '[:upper:]')
            echo "  - log level: $LOG_LEVEL"
        fi

        # Parse ci-dir option (enables CI mode with automated 2FA)
        if [ -n "$CI_DIR" ]; then
            PYTEST_ARGS="$PYTEST_ARGS --ci --ci-dir $CI_DIR"
            echo "  - CI mode: enabled (ci-dir=$CI_DIR)"
        fi
    fi

    # Add common pytest options
    PYTEST_ARGS="$PYTEST_ARGS --screenshot only-on-failure --verbose --browser firefox --log-cli-level=$LOG_LEVEL"

    echo "Running E2E tests for project: {{project_dir}}"
    echo "Test filter: {{test_filter}}"
    echo "================================================"

    {{container-tool}} compose --project-directory {{justfile_directory()}} -f {{e2e-compose-file}} exec -e XAUTHORITY=/home/testuser/.Xauthority e2e bash -c "cd /workspace && xvfb-run --auto-servernum uv run pytest $PYTEST_ARGS"

# Setup GitHub OAuth authentication (one-time, requires X11 forwarding)
# Usage: just auth-setup <project-dir> [display]
# Example: just auth-setup sandbox3
# Example: just auth-setup sandbox3 localhost:10.0
auth-setup project_dir display="${DISPLAY:-}":
    #!/usr/bin/env bash
    set -euo pipefail


    # Track override file for cleanup
    OVERRIDE_FILE=""

    # Cleanup function
    cleanup() {
        [ -n "$OVERRIDE_FILE" ] && [ -f "$OVERRIDE_FILE" ] && rm -f "$OVERRIDE_FILE"
    }

    # Ensure cleanup on exit
    trap cleanup EXIT

    if [ ! -d "{{project_dir}}" ]; then
        echo "Error: Project directory '{{project_dir}}' does not exist"
        exit 1
    fi

    # Check if container is running
    if ! ({{container-tool}} compose --project-directory {{justfile_directory()}} -f {{e2e-compose-file}} ps e2e) | grep -qE "(Up|running)"; then
        echo "Error: E2E container is not running. Start it with: just e2e-up"
        exit 1
    fi

    # Always mount project directory dynamically
    echo "Mounting project directory: {{project_dir}}"

    # Create test-results and .auth directories
    mkdir -p "{{justfile_directory()}}/test-results"
    mkdir -p "{{justfile_directory()}}/.auth"
    echo "Cleaning old test artifacts..."
    rm -rf "{{justfile_directory()}}/test-results"/*

    # Update .env file with current values
    sed -i 's/^HOST_UID=.*/HOST_UID={{HOST_UID}}/' {{justfile_directory()}}/.env
    sed -i 's/^HOST_GID=.*/HOST_GID={{HOST_GID}}/' {{justfile_directory()}}/.env
    if grep -q '^E2E_DOCKERFILE=' {{justfile_directory()}}/.env; then
        sed -i 's|^E2E_DOCKERFILE=.*|E2E_DOCKERFILE={{e2e-image-dir}}/Dockerfile|' {{justfile_directory()}}/.env
    else
        echo 'E2E_DOCKERFILE={{e2e-image-dir}}/Dockerfile' >> {{justfile_directory()}}/.env
    fi
    # Resolve AWS_REGION from env or AWS config (must not be empty — SDK treats "" as valid)
    _AWS_REGION="${AWS_REGION:-$(aws configure get region 2>/dev/null || echo "")}"
    if [ -n "$_AWS_REGION" ]; then
        if grep -q '^AWS_REGION=' {{justfile_directory()}}/.env; then
            sed -i "s|^AWS_REGION=.*|AWS_REGION=$_AWS_REGION|" {{justfile_directory()}}/.env
        else
            echo "AWS_REGION=$_AWS_REGION" >> {{justfile_directory()}}/.env
        fi
    fi

    # Create temporary override file to mount the project directory and test-results
    OVERRIDE_FILE="{{justfile_directory()}}/docker-compose.e2e-override.yml"
    cat > "$OVERRIDE_FILE" <<EOF
    services:
      e2e:
        volumes:
          - ./{{project_dir}}:/workspace/{{project_dir}}
          - ./test-results:/workspace/test-results
    EOF

    # Stop and restart container with new mounts (ensures clean mount state)
    echo "Restarting E2E container with project mount..."
    {{container-tool}} compose --project-directory {{justfile_directory()}} -f {{e2e-compose-file}} down
    {{container-tool}} compose --project-directory {{justfile_directory()}} -f {{e2e-compose-file}} -f "$OVERRIDE_FILE" up -d

    # Re-sync files after restart (container loses synced files when restarted)
    echo "Re-syncing project files after mount..."
    just e2e-sync

    # Verify test-results directory is writable (detect stale mount)
    echo "Verifying test-results directory is writable..."
    if ! {{container-tool}} exec {{e2e-container-name}} bash -c "touch /workspace/test-results/.mount-check && rm /workspace/test-results/.mount-check" 2>/dev/null; then
        echo "Error: test-results directory is not writable (stale mount detected)"
        echo ""
        echo "This happens when test-results was deleted while the container was running."
        echo "To fix: just e2e-down && just e2e-up"
        [ -n "$OVERRIDE_FILE" ] && rm -f "$OVERRIDE_FILE"
        exit 1
    fi
    echo "✓ test-results directory is writable"

    # Check if DISPLAY is set
    if [ -z "{{display}}" ]; then
        echo "Error: DISPLAY environment variable is not set."
        echo ""
        echo "X11 forwarding is required for authentication setup."
        echo ""
        echo "Solutions:"
        echo "  1. SSH with X11 forwarding: ssh -X your-host"
        echo "  2. Set DISPLAY manually: export DISPLAY=localhost:10.0"
        echo "  3. Pass DISPLAY explicitly: just auth-setup {{project_dir}} localhost:10.0"
        exit 1
    fi

    echo "Setting up GitHub OAuth authentication..."
    echo "Using DISPLAY: {{display}}"
    echo "A browser window will open for you to complete authentication."
    echo "================================================"

    # Setup X11 authentication
    echo "Setting up X11 authentication..."

    # Parse DISPLAY to extract the display number (e.g., "localhost:10.0" -> "10")
    DISPLAY_NUM=$(echo "{{display}}" | cut -d':' -f2 | cut -d'.' -f1)

    # Get X11 auth cookie for this display
    COOKIE=$(xauth list 2>/dev/null | grep ":$DISPLAY_NUM" | awk '{print $NF}' | head -1)

    if [ -z "$COOKIE" ]; then
        echo "⚠ Error: Could not find X11 auth cookie for display :$DISPLAY_NUM"
        echo "Make sure X11 forwarding is enabled (ssh -X) and DISPLAY is set"
        exit 1
    fi

    echo "Found X11 cookie: ${COOKIE:0:16}..."

    # Add localhost cookies to host .Xauthority (needed for TCP connections)
    # xauth converts "localhost:10" to "localhost/unix:10", but we need both formats
    xauth list | grep -q "localhost:$DISPLAY_NUM" || xauth add localhost:$DISPLAY_NUM MIT-MAGIC-COOKIE-1 $COOKIE 2>/dev/null || true
    xauth list | grep -q "127.0.0.1:$DISPLAY_NUM" || xauth add 127.0.0.1:$DISPLAY_NUM MIT-MAGIC-COOKIE-1 $COOKIE 2>/dev/null || true

    # Copy the host's .Xauthority file to container (preserves all cookie formats)
    {{container-tool}} cp ~/.Xauthority {{e2e-container-name}}:/home/testuser/.Xauthority
    {{container-tool}} compose --project-directory {{justfile_directory()}} -f {{e2e-compose-file}} exec e2e chmod 600 /home/testuser/.Xauthority

    echo "✓ X11 authentication cookies copied to container"

    echo ""
    echo "Verifying X11 setup..."
    {{container-tool}} compose --project-directory {{justfile_directory()}} -f {{e2e-compose-file}} exec -e DISPLAY={{display}} e2e bash -c "\
        echo \"DISPLAY in container: \$DISPLAY\" && \
        echo \"Container hostname: \$(hostname -f)\" && \
        echo \"\" && \
        echo \"Xauthority file:\" && \
        ls -lh /home/testuser/.Xauthority 2>&1 || echo 'No .Xauthority' && \
        echo \"\" && \
        echo \"X11 cookies installed:\" && \
        xauth list 2>&1 || echo 'No xauth cookies' \
    "

    echo ""
    echo "Launching browser..."

    # Ensure project files are synced (check if scripts directory exists)
    if ! {{container-tool}} exec {{e2e-container-name}} test -d /workspace/scripts; then
        echo "Project files not found in container, syncing..."
        just e2e-sync
    fi

    {{container-tool}} compose --project-directory {{justfile_directory()}} -f {{e2e-compose-file}} exec -e DISPLAY={{display}} -e XAUTHORITY=/home/testuser/.Xauthority e2e bash -c "\
        export DISPLAY={{display}} && \
        export XAUTHORITY=/home/testuser/.Xauthority && \
        cd /workspace && \
        uv run python scripts/github_auth_setup.py --project-dir={{project_dir}} \
    "

# Clean up test artifacts and remove image
clean-e2e:
    rm -rf test-results .pytest_cache
    {{container-tool}} compose --project-directory {{justfile_directory()}} -f {{e2e-compose-file}} down -v
    {{container-tool}} rmi {{e2e-container-name}}:{{e2e-image-tag}} || true

# Full workflow: start container (builds if needed) and run tests
# Usage: just e2e-all <project-dir> [test-filter] [options] [no-cache]
e2e-all project_dir test_filter="" options="" no_cache="false" template=default-template:
    @echo "Starting E2E container (will build image if needed)..."
    @just e2e-up {{no_cache}}
    @echo ""
    @just test-e2e {{project_dir}} {{test_filter}} {{options}} {{template}}

# --- Per-template convenience wrappers ---

# Run E2E tests for the base template (tf-aws-ec2-base)
test-e2e-base project_dir="sandbox-e2e" test_filter="" options="":
    @just test-e2e {{project_dir}} "{{test_filter}}" "{{options}}" tf-aws-ec2-base

# Run E2E tests for the CI template (tf-aws-iam-ci)
test-e2e-ci project_dir="sandbox-e2e-ci" test_filter="" options="":
    @just test-e2e {{project_dir}} "{{test_filter}}" "{{options}}" tf-aws-iam-ci

# Setup GitHub OAuth for the base template
auth-setup-base project_dir display="${DISPLAY:-}":
    @just auth-setup {{project_dir}} "{{display}}"

# --- CI infrastructure commands ---

# Ensure the host is running (start if stopped)
# Usage: just ensure-host-running <project-dir>
ensure-host-running project_dir:
    #!/usr/bin/env bash
    set -euo pipefail
    STATUS=$(uv run jd host status -p {{project_dir}} 2>&1 || true)
    echo "$STATUS"
    if echo "$STATUS" | grep -q "running"; then
        echo "Host is already running."
    else
        echo "Host is not running, starting..."
        uv run jd host start -p {{project_dir}}
    fi

# Ensure the host is stopped (stop if running)
# Usage: just ensure-host-stopped <project-dir>
ensure-host-stopped project_dir:
    #!/usr/bin/env bash
    set -euo pipefail
    STATUS=$(uv run jd host status -p {{project_dir}} 2>&1 || true)
    echo "$STATUS"
    if echo "$STATUS" | grep -q "running"; then
        uv run jd host stop -p {{project_dir}}
    else
        echo "Host is not running, skipping stop."
    fi

# Initialize a new CI infrastructure project
# Usage: just init-ci [ci-dir]
# Example: just init-ci sandbox-ci
init-ci ci_dir="sandbox-ci":
    mkdir -p {{ci_dir}}
    uv run jd init {{ci_dir}} --engine terraform --provider aws --infrastructure iam --template ci

# Deploy a new base template project from scratch using CI infrastructure
# Usage: just ci-deploy-base <oauth-app-num> [ci-dir] [project-dir]
# Example: just ci-deploy-base 3
# Example: just ci-deploy-base 3 sandbox-ci sandbox-base
ci-deploy-base oauth_app_num ci_dir="sandbox-ci" project_dir="sandbox-base":
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -d "{{project_dir}}" ] && [ "$(ls -A {{project_dir}})" ]; then
        echo "Error: {{project_dir}} already exists and is not empty."
        echo "Remove it first to avoid overwriting an existing deployment."
        exit 1
    fi
    mkdir -p {{project_dir}}
    uv run jd init {{project_dir}}
    uv run python scripts/config_base_from_ci.py {{project_dir}} {{ci_dir}} {{oauth_app_num}}
    uv run jd up -y -p {{project_dir}}

# Discover and restore CI project from S3 store
ci-restore ci_dir="sandbox-ci":
    uv run python scripts/ci_restore.py {{ci_dir}}

# Find and restore a base template project from S3 by OAuth app subdomain
# Usage: just ci-restore-base <oauth-app-num> [ci-dir] [project-dir]
ci-restore-base oauth_app_num ci_dir="sandbox-ci" project_dir="sandbox-base":
    uv run python scripts/ci_restore_base.py {{ci_dir}} {{oauth_app_num}} {{project_dir}}

# Find a base template project by subdomain, take it down (jd down), and delete from S3 store
# Exits successfully if no matching project is found (nothing to take down)
# Usage: just find-takedown-base <oauth-app-num> [ci-dir] [project-dir]
find-takedown-base oauth_app_num ci_dir="sandbox-ci" project_dir="sandbox-e2e":
    uv run python scripts/find_takedown_base.py {{ci_dir}} {{oauth_app_num}} {{project_dir}}

# Export local auth state to Secrets Manager
auth-export ci_dir="sandbox-ci":
    uv run python scripts/sync_auth_state.py export {{ci_dir}}

# Import auth state from Secrets Manager (run ci-restore first)
auth-import ci_dir="sandbox-ci":
    uv run python scripts/sync_auth_state.py import {{ci_dir}}

# Check local auth state cookie expiry (no AWS access needed)
auth-check:
    uv run python scripts/sync_auth_state.py check

# Print the GitHub bot account password from CI secrets
auth-bot-password ci_dir="sandbox-ci":
    @uv run python scripts/auth_bot_secret.py {{ci_dir}} password

# Generate a 2FA code for the GitHub bot account (requires oathtool)
auth-bot-2fa ci_dir="sandbox-ci":
    @uv run python scripts/auth_bot_secret.py {{ci_dir}} totp

# Print the GitHub bot account email from CI project variables
auth-bot-email ci_dir="sandbox-ci":
    @uv run jd show -v github_bot_account_email --text --path {{ci_dir}}

# Print the GitHub bot account username (email prefix before @)
auth-bot-username ci_dir="sandbox-ci":
    @just auth-bot-email {{ci_dir}} | cut -d'@' -f1

# Generate .env for base template E2E tests
# Two modes:
#   Existing project: reads deployment variables from the project via `jd show -v`
#   Fresh deploy:     pass "" as project-dir, provide deployment vars as options
# Usage: just env-setup-base <project-dir> [ci-dir] [oauth-app-num] [options]
# Options: comma-separated key=value pairs (same format as test-e2e options)
# Quote options containing [] values (zsh treats brackets as glob patterns)
# Example: just env-setup-base sandbox-e2e sandbox-ci 4 user=botuser,safe-user=realuser
# Example: just env-setup-base "" sandbox-ci 4 'user=botuser,safe-user=realuser'
env-setup-base project_dir ci_dir="sandbox-ci" oauth_app_num="1" options="":
    uv run python scripts/env_setup_base.py "{{project_dir}}" {{ci_dir}} {{oauth_app_num}} "{{options}}"
