#!/bin/bash
set -e

# Records logs
mkdir -p /var/log/jupyter-deploy
exec > >(tee /var/log/jupyter-deploy/cloudinit.log) 2>&1

echo "Running cloudinit script as: $(whoami)"

# Detect Linux distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    VERSION=$VERSION_ID
else
    echo "Cannot detect OS version"
    exit 1
fi

if [[ "$OS" == "Amazon Linux" ]]; then
    yum update -y

    # Install docker
    yum install -y docker  # this should be a no-op
    
    # Install docker-compose
    curl -L https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose

elif [[ "$OS" == "Ubuntu" ]] || [[ "$OS" == "Debian" ]]; then
    # Update package list and install required packages
    apt-get update
    apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        software-properties-common

    # Add docker's official GPG key
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -

    # Add docker repository
    add-apt-repository \
    "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) \
    stable"

    # Install docker
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io

    # Install docker Compose
    apt-get install -y docker-compose-plugin
    chmod +x /usr/local/bin/docker-compose

else
    echo "Unsupported OS version"
    exit 1
fi

# Enable docker
systemctl start docker
systemctl enable docker

# create the service user and restrict permissions
useradd -r -s /sbin/nologin -d /home/service-user -m service-user

# revisit: granting access to the docker deamon is an avenue for elevation of privilege
usermod -aG docker service-user

tee /etc/sudoers.d/service-user << EOF
service-user ALL=(ALL) NOPASSWD: /bin/systemctl start docker
service-user ALL=(ALL) NOPASSWD: /bin/systemctl stop docker
service-user ALL=(ALL) NOPASSWD: /bin/systemctl restart docker
EOF
chmod 440 /etc/sudoers.d/service-user

# Set up specific PATH
tee /home/service-user/.bash_profile << EOF
PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin
EOF

chown service-user:service-user /home/service-user/.bash_profile
chmod 644 /home/service-user/.bash_profile

mkdir -p /home/service-user/.aws
chown -R service-user:service-user /home/service-user

# Create limits configuration
echo "Setting up resource limits..."
tee /etc/security/limits.d/service-user.conf << EOF
service-user soft nproc 1024
service-user hard nproc 2048
service-user soft nofile 4096
service-user hard nofile 8192
EOF
chmod 440 /etc/security/limits.d/service-user.conf

# Mount the jupyter-data drive and save config to persist on reboots
mkfs -t ext4 /dev/sdf
mkdir -p /mnt/jupyter-data
mount /dev/sdf /mnt/jupyter-data

chown service-user:service-user /mnt/jupyter-data
chmod 750 /mnt/jupyter-data

echo "/dev/sdf /mnt/jupyter-data ext4 defaults,nofail 0 2" | tee -a /etc/fstab

# Create the required dirs
mkdir -p /opt/docker
