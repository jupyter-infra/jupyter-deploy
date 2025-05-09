# Records logs
sudo mkdir -p /var/log/jupyter-startup
exec > >(tee /var/log/jupyter-startup/cloudinit.log) 2>&1

# Retrieves and logs the current user
CURRENT_USER=$(whoami)
echo "Current user: $CURRENT_USER"

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
    sudo yum update -y

    # Install docker
    sudo yum install -y docker  # this should be a no-op
    
    # Install docker-compose
    sudo curl -L https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose

elif [[ "$OS" == "Ubuntu" ]] || [[ "$OS" == "Debian" ]]; then
    # Update package list and install required packages
    sudo apt-get update
    sudo apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        software-properties-common

    # Add docker's official GPG key
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -

    # Add docker repository
    sudo add-apt-repository \
    "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) \
    stable"

    # Install docker
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io

    # Install docker Compose
    sudo apt-get install -y docker-compose-plugin
    sudo chmod +x /usr/local/bin/docker-compose

else
    echo "Unsupported OS version"
    exit 1
fi

# Setup the /opt/docker working dir
sudo mkdir -p /opt/docker
sudo chown $CURRENT_USER:$CURRENT_USER /opt/docker

# Mount the jupyter-data drive and save config to persist on reboots
sudo mkfs -t ext4 /dev/sdf
sudo mkdir -p /mnt/jupyter-data
sudo mount /dev/sdf /mnt/jupyter-data

sudo chown $CURRENT_USER:$CURRENT_USER /mnt/jupyter-data

echo "/dev/sdf /mnt/jupyter-data ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab

# Enable docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $CURRENT_USER
