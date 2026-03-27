# E2E test container for jupyter-deploy templates
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
    wget \
    unzip \
    gnupg \
    software-properties-common \
    curl \
    jq \
    git \
    oathtool \
    && rm -rf /var/lib/apt/lists/*

# Install Terraform
RUN wget -qO- https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg && \
    echo 'deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com bookworm main' | tee /etc/apt/sources.list.d/hashicorp.list && \
    apt-get update && \
    apt-get install -y terraform && \
    rm -rf /var/lib/apt/lists/*

# Install AWS CLI
RUN curl -s 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o 'awscliv2.zip' && \
    unzip -q awscliv2.zip && \
    ./aws/install && \
    rm -rf aws awscliv2.zip

# Install AWS Session Manager Plugin
RUN curl -s 'https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb' -o 'session-manager-plugin.deb' && \
    dpkg -i session-manager-plugin.deb && \
    rm session-manager-plugin.deb

# Create user with configurable UID/GID (defaults to 1000:1000)
ARG USER_UID=1000
ARG USER_GID=1000
RUN set -e; \
    # Check if group with this GID already exists
    if getent group ${USER_GID} > /dev/null 2>&1; then \
        echo "Group with GID ${USER_GID} already exists, using it"; \
    else \
        echo "Creating group testuser with GID ${USER_GID}"; \
        groupadd -g ${USER_GID} testuser; \
    fi; \
    # Create user with the specified UID/GID
    useradd -m -u ${USER_UID} -g ${USER_GID} -s /bin/bash testuser

# Set working directory and make it owned by testuser
WORKDIR /workspace
RUN chown ${USER_UID}:${USER_GID} /workspace

# Install Playwright system dependencies only (browsers will be installed after uv sync)
# We install system deps here so they're cached in the image layer
RUN apt-get update && \
    apt-get install -y \
    # Playwright Firefox dependencies
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxshmfence1 \
    fonts-liberation \
    fonts-noto-color-emoji \
    xvfb \
    x11-xkb-utils \
    xauth \
    && rm -rf /var/lib/apt/lists/*

# Project files will be synced at runtime via docker-compose volumes and e2e-sync
# Python dependencies will be installed via e2e-sync after files are copied

# Switch to testuser
USER testuser

# Keep container running
CMD ["sleep", "infinity"]
