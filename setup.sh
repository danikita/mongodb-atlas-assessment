#!/bin/bash
set -e

echo "Detecting operating system..."

if [ -f /etc/os-release ]; then
  . /etc/os-release
else
  echo "Cannot detect operating system."
  exit 1
fi

install_amazon_linux() {
  echo "Detected Amazon Linux"

  sudo yum update -y

  echo "Installing base packages..."
  sudo yum install -y python3 python3-pip curl

  echo "Upgrading pip..."
  python3 -m pip install --upgrade pip

  echo "Installing Python dependencies..."
  python3 -m pip install pymongo requests

  echo "Installing Node.js 20.x..."
  curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
  sudo yum install -y nodejs

  echo "Adding MongoDB repository..."
  sudo tee /etc/yum.repos.d/mongodb-org.repo << 'EOF'
[mongodb-org-6.0]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/amazon/2023/mongodb-org/6.0/x86_64/
gpgcheck=1
enabled=1
gpgkey=https://pgp.mongodb.com/server-6.0.asc
EOF

  sudo yum clean all
  sudo yum makecache

  echo "Installing MongoDB Shell (mongosh)..."
  sudo yum install -y mongodb-mongosh

  echo "Installing MongoDB Realm CLI..."
  sudo npm install -g mongodb-realm-cli
}

install_ubuntu() {
  echo "Detected Ubuntu"

  sudo apt update -y

  echo "Installing base packages..."
  sudo apt install -y python3 python3-pip curl gnupg

  echo "Upgrading pip..."
  python3 -m pip install --upgrade pip

  echo "Installing Python dependencies..."
  python3 -m pip install pymongo requests

  echo "Installing Node.js 20.x..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
  sudo apt install -y nodejs

  echo "Adding MongoDB repository..."
  curl -fsSL https://pgp.mongodb.com/server-6.0.asc | \
    sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server.gpg

  echo "deb [ signed-by=/usr/share/keyrings/mongodb-server.gpg ] \
https://repo.mongodb.org/apt/ubuntu ${VERSION_CODENAME}/mongodb-org/6.0 multiverse" | \
    sudo tee /etc/apt/sources.list.d/mongodb-org-6.0.list

  sudo apt update -y

  echo "Installing MongoDB Shell (mongosh)..."
  sudo apt install -y mongodb-mongosh

  echo "Installing MongoDB Realm CLI..."
  sudo npm install -g mongodb-realm-cli
}

case "$ID" in
  amzn)
    install_amazon_linux
    ;;
  ubuntu)
    install_ubuntu
    ;;
  *)
    echo "Unsupported OS: $ID"
    exit 1
    ;;
esac

echo "✅ All dependencies installed successfully."
