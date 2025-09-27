#!/bin/bash

# =============================================================================
# CREATE SERVICENOW AUTHORIZATION
# =============================================================================
# This script creates an OAuth 2.0 authorization for the ServiceNow Agent.
# Run this before patching the agent.

set -euo pipefail  # Exit on error, undefined variables, and pipe failures

# Load environment variables
if [ -f snow_agent/.env ]; then
    source snow_agent/.env
    echo "✅ Loaded snow_agent/.env file"
else
    echo "❌ Error: snow_agent/.env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

# Validate required variables
required_vars=("GOOGLE_CLOUD_PROJECT" "AUTH_ID" "SERVICENOW_CLIENT_ID" "SERVICENOW_CLIENT_SECRET" "SERVICENOW_INSTANCE_URL")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Error: Required environment variable $var is not set in .env"
        exit 1
    fi
done

echo "🚀 Creating AgentSpace Authorization for ServiceNow..."
echo "   Project: $GOOGLE_CLOUD_PROJECT"
echo "   Auth ID: $AUTH_ID"

# --- Script Body ---
AUTH_TOKEN=$(gcloud auth print-access-token)
DISCOVERY_ENGINE_API_BASE_URL="https://discoveryengine.googleapis.com/v1alpha"

# Construct the ServiceNow token URI
TOKEN_URI="${SERVICENOW_INSTANCE_URL}/oauth_token.do"

# The authorization URI is not used in the client credentials flow, but it's a required field in the API.
# We'll use the token URI as a placeholder.
AUTHORIZATION_URI="${SERVICENOW_INSTANCE_URL}/oauth_auth.do?response_type=code&access_type=offline&prompt=consent"

# Create the JSON payload
JSON_PAYLOAD=$(cat <<EOF
{
  "name": "projects/${GOOGLE_CLOUD_PROJECT}/locations/global/authorizations/${AUTH_ID}",
  "serverSideOauth2": {
    "clientId": "${SERVICENOW_CLIENT_ID}",
    "clientSecret": "${SERVICENOW_CLIENT_SECRET}",
    "authorizationUri": "${AUTHORIZATION_URI}",
    "tokenUri": "${TOKEN_URI}"
  }
}
EOF
)

echo "📡 Making API request to create authorization..."
response=$(curl -s -w "\n%{http_code}" -X POST \
     -H "Authorization: Bearer ${AUTH_TOKEN}" \
     -H "Content-Type: application/json" \
     -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT}" \
     "${DISCOVERY_ENGINE_API_BASE_URL}/projects/${GOOGLE_CLOUD_PROJECT}/locations/global/authorizations?authorizationId=${AUTH_ID}" \
     -d "${JSON_PAYLOAD}")


# Extract response body and status code
http_code=$(echo "$response" | tail -n1)
response_body=$(echo "$response" | sed '$d')

echo "📋 Response:"
echo "$response_body" | jq . 2>/dev/null || echo "$response_body"

if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 201 ]; then
    echo "✅ Authorization '$AUTH_ID' created successfully!"
else
    echo "❌ Failed to create authorization (HTTP $http_code)"
    echo "   Check your configuration and try again"
    exit 1
fi
