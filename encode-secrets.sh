#!/bin/bash

# Script to encode environment variables for Kubernetes secrets
# Run this script to generate base64 encoded values for your secrets

echo "🔐 Encoding environment variables for Kubernetes secrets"
echo ""

# Read from .env file if it exists
if [ -f ".env" ]; then
    echo "Found .env file. Encoding values..."
    echo ""

    while IFS='=' read -r key value; do
        # Skip empty lines and comments
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue

        # Remove quotes if present
        value=$(echo "$value" | sed 's/^"\(.*\)"$/\1/' | sed "s/^'\(.*\)'$/\1/")

        # Encode the value
        encoded=$(echo -n "$value" | base64 -w 0)

        echo "$key: $encoded"
    done < .env
else
    echo "❌ .env file not found!"
    echo "Please create a .env file with your environment variables."
    exit 1
fi

echo ""
echo "✅ Copy these values to k8s/secret.yaml under the 'data' section"
echo ""
echo "Example:"
echo "data:"
echo "  GROQ_API_KEY: <encoded-value>"
echo "  SECRET_KEY: <encoded-value>"