#!/bin/bash

# Check OCI CLI version
oci --version || { echo "OCI CLI not found. Exiting."; exit 1; }

# Run OCI config setup if not found
if [ ! -f ~/.oci/config ]; then
  echo "OCI config not found. Running setup..."
  oci setup config
else
  echo "OCI config already set up."
fi

# Display the generated public API key to the user
cat /home/opc/.oci/oci_api_key_public.pem #change path if needed

# Confirmation wait
read -p "Confirm that you have placed the generated API key in your OCI tenancy console [Y/N]: " usr_conf

if [[ "$usr_conf" = "N" || "$usr_conf" = "n" ]]; then
  echo " ^}^l Please provide the generated API key in your OCI tenancy console. Exiting."
  exit 1
fi

# Ask for HeatWave OCID
read -p "Enter the OCID of your HeatWave instance: " hw_ocid

# Get IP address
ip_address=$(oci mysql db-system get \
  --db-system-id "$hw_ocid" \
  --query "data.endpoints[0].\"ip-address\"" \
  --raw-output)

if [[ -z "$ip_address" ]]; then
  echo "Failed to retrieve IP address. Exiting."
  exit 1
fi

# Get port endpoint
port_endpoint=$(oci mysql db-system get \
  --db-system-id "$hw_ocid" \
  --query "data.endpoints[0].port" \
  --raw-output)

if [[ -z "$port_endpoint" ]]; then
  echo "Failed to retrieve port endpoint. Exiting."
  exit 1
fi

# Ask for HeatWave credentials
read -p "Enter the username for your HeatWave instance: " hw_usr
read -s -p "Enter the password for your HeatWave instance: " hw_pswrd
echo

# Define target Python file
PYFILE="/home/opc/NL2SQL-main/nl2sql_app.py"

# Backup original file
cp "$PYFILE" "${PYFILE}.bak"

# Replace values using sed (escaped double quotes and slashes)
sed -i "s/^DB_HOST = .*/DB_HOST = \"${ip_address}\"/" "$PYFILE"
sed -i "s/^DB_USER = .*/DB_USER = \"${hw_usr}\"/" "$PYFILE"
sed -i "s/^DB_PASSWORD = .*/DB_PASSWORD = \"${hw_pswrd}\"/" "$PYFILE"
sed -i "s/^DB_PORT = .*/DB_PORT = ${port_endpoint}/" "$PYFILE"

echo "✅ Updated $PYFILE with provided values."
