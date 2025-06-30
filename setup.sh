#!/bin/bash

set -e

echo "Starting system update and enabling required repositories..."
sudo dnf config-manager --set-enabled ol8_codeready_builder
sudo dnf install -y oracle-epel-release-el8
sudo dnf update -y

echo "Installing Oracle CLI and its dependencies..."
sudo dnf -y install oraclelinux-developer-releasoci --versione-el8
sudo dnf -y install python36-oci-cli

echo "Installing Development Tools and common build dependencies..."
sudo dnf groupinstall -y "Development Tools"
sudo dnf install -y gcc openssl-devel bzip2-devel libffi-devel \
                    wget make zlib-devel xz-devel \
                    readline-devel sqlite-devel

echo "Downloading and compiling Python 3.11..."
cd /usr/src
sudo wget https://www.python.org/ftp/python/3.11.9/Python-3.11.9.tgz
sudo tar xzf Python-3.11.9.tgz
cd Python-3.11.9
sudo ./configure --enable-optimizations
sudo make -j$(nproc)
sudo make altinstall

echo "Setting Python 3.11 as the default python3..."
sudo alternatives --install /usr/bin/python3 python3 /usr/local/bin/python3.11 2
sudo alternatives --install /usr/bin/python python /usr/local/bin/python3.11 2
sudo alternatives --set python3 /usr/local/bin/python3.11
sudo alternatives --set python /usr/local/bin/python3.11

echo "Verifying Python version..."
python3 --version

echo "Installing pip and specified Python libraries..."
python3.11 -m ensurepip --upgrade
python3.11 -m pip install --upgrade pip setuptools
python3.11 -m pip install mysql-connector-python==9.3.0 seaborn streamlit

echo "Opening port 8501 in firewalld..."
sudo systemctl enable firewalld
sudo systemctl start firewalld
sudo firewall-cmd --zone=public --add-port=8501/tcp --permanent
sudo firewall-cmd --reload
sudo firewall-cmd --zone=public --list-ports

echo "Setup complete!"
echo "Python 3.11 is installed and set as default."
echo "Port 8501 is open."
echo "Libraries installed: mysql-connector-python==9.3.0, seaborn, setuptools, streamlit"
echo "You can now run: streamlit run app.py"
