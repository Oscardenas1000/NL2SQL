#!/bin/bash

# Setup logging
LOG_FILE="/tmp/python_setup_$(date +%F_%H-%M).log"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "📄 Logging setup to $LOG_FILE"

# Gracefully handle individual errors without killing the whole script
run_step() {
  echo -e "\n🔹 $1"
  if eval "$2"; then
    echo "✅ Success: $1"
  else
    echo "❌ Failed: $1 — check log for details"
  fi
}

# Repos and updates
run_step "Enable CodeReady Builder repo" \
  "sudo dnf config-manager --set-enabled ol8_codeready_builder"

run_step "Install Oracle EPEL" \
  "sudo dnf install -y oracle-epel-release-el8"

run_step "System update" \
  "sudo dnf update -y"

# OCI CLI (optional: uncomment if needed)
# run_step "Enable Oracle Linux Developer repo" \
#   "sudo dnf -y install oraclelinux-developer-release-el8"

run_step "Install OCI CLI (Python 3.6 version)" \
  "sudo dnf -y install python36-oci-cli"

# Development Tools
run_step "Install Development Tools group" \
  "sudo dnf groupinstall -y 'Development Tools'"

run_step "Install build dependencies" \
  "sudo dnf install -y gcc openssl-devel bzip2-devel libffi-devel \
   wget make zlib-devel xz-devel readline-devel sqlite-devel"

# Python 3.11
run_step "Download Python 3.11.9 source" \
  "cd /usr/src && sudo wget -nc https://www.python.org/ftp/python/3.11.9/Python-3.11.9.tgz"

run_step "Extract Python source" \
  "cd /usr/src && sudo tar xzf Python-3.11.9.tgz"

run_step "Clean previous Python build (if any)" \
  "cd /usr/src/Python-3.11.9 && sudo make clean"

run_step "Configure Python build" \
  "cd /usr/src/Python-3.11.9 && sudo ./configure --enable-optimizations"

run_step "Compile Python source" \
  "cd /usr/src/Python-3.11.9 && sudo make -j\$(nproc)"

run_step "Install Python using make altinstall" \
  "cd /usr/src/Python-3.11.9 && sudo make altinstall"

run_step "Register python3.11 as default python3" \
  "sudo alternatives --install /usr/bin/python3 python3 /usr/local/bin/python3.11 2 && \
   sudo alternatives --set python3 /usr/local/bin/python3.11"

run_step "Verify Python version" \
  "python3 --version"

# pip and libraries
run_step "Install pip for Python 3.11" \
  "python3.11 -m ensurepip --upgrade"

run_step "Install required Python libraries" \
  "python3.11 -m pip install --upgrade pip setuptools && \
   python3.11 -m pip install mysql-connector-python==9.3.0 seaborn streamlit"

# Firewall setup
run_step "Enable and configure firewalld for Streamlit port" \
  "sudo systemctl enable firewalld && \
   sudo systemctl start firewalld && \
   sudo firewall-cmd --zone=public --add-port=8501/tcp --permanent && \
   sudo firewall-cmd --reload && \
   sudo firewall-cmd --zone=public --list-ports"

# Completion message
echo -e "\n🎉 All setup tasks completed!"
echo "👉 Python version: $(python3 --version)"
echo "✅ Port 8501 is open"
echo "📦 Installed Python libraries: mysql-connector-python==9.3.0, seaborn, streamlit, setuptools"
echo "🚀 You can now run: streamlit run app.py"
echo "📄 Full log saved to: $LOG_FILE"

eco "execute the following commands:"
echo "chmod +x oci_cli_setup.sh"
echo "./oci_cli_setup.sh"
