#!/bin/bash

# =============================================================================
# CREATE OR PATCH AGENTSPACE AGENT
# =============================================================================
# This script creates an agent if it doesn't exist, or patches it if it does.
# It links the agent to the authorization resource.

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
required_vars=("GOOGLE_CLOUD_PROJECT" "GOOGLE_CLOUD_PROJECT_NUMBER" "GOOGLE_CLOUD_LOCATION" "AS_APP" "ASSISTANT_ID" "AGENT_NAME" "AGENT_DISPLAY_NAME" "AGENT_DESCRIPTION" "TOOL_DESCRIPTION" "AUTH_ID" "REASONING_ENGINE")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Error: Required environment variable $var is not set in .env"
        exit 1
    fi
done

echo "🚀 Creating or patching AgentSpace Agent..."
echo "   Project: $GOOGLE_CLOUD_PROJECT"
echo "   Agent Name: $AGENT_NAME"
echo "   Display Name: $AGENT_DISPLAY_NAME"
echo "   Reasoning Engine: $REASONING_ENGINE"
echo "   Auth ID: $AUTH_ID"

# --- Script Body ---
AUTH_TOKEN=$(gcloud auth print-access-token)
DISCOVERY_ENGINE_API_BASE_URL="https://discoveryengine.googleapis.com"
AGENTS_API_ENDPOINT="${DISCOVERY_ENGINE_API_BASE_URL}/v1alpha/projects/${GOOGLE_CLOUD_PROJECT}/locations/global/collections/default_collection/engines/${AS_APP}/assistants/${ASSISTANT_ID}/agents"

# --- 1. Check if agent exists ---
echo "🔎 Checking for existing agent with display name: '$AGENT_DISPLAY_NAME'…"
response=$(curl -s -X GET \
  -H "Authorization: Bearer ${AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT}" \
  "${AGENTS_API_ENDPOINT}")

AGENT_ID=$(echo "$response" | jq -r --arg NAME "$AGENT_DISPLAY_NAME" '.agents[] | select(.displayName == $NAME) | .name' | cut -d'/' -f10)

# --- 2. Create or Patch ---
if [ -n "$AGENT_ID" ]; then
    # --- Agent exists, so PATCH it ---
    echo "✅ Agent found with ID: $AGENT_ID. Patching agent…"
    API_ENDPOINT="${AGENTS_API_ENDPOINT}/${AGENT_ID}"
    HTTP_METHOD="PATCH"
    JSON_PAYLOAD=$(cat <<EOF
    {
      "displayName": "${AGENT_DISPLAY_NAME}",
      "description": "${AGENT_DESCRIPTION}",
      "adk_agent_definition": {
        "tool_settings": { "tool_description": "${TOOL_DESCRIPTION}" },
        "provisioned_reasoning_engine": { "reasoning_engine": "${REASONING_ENGINE}" },
        "authorizations": [ "projects/${GOOGLE_CLOUD_PROJECT_NUMBER}/locations/global/authorizations/${AUTH_ID}" ]
      }
    }
EOF
    )
else
    # --- Agent does not exist, so CREATE it ---
    echo "ℹ️ No existing agent found. Creating a new agent…"
    API_ENDPOINT="${AGENTS_API_ENDPOINT}"
    HTTP_METHOD="POST"
    JSON_PAYLOAD=$(cat <<EOF
    {
      "displayName": "${AGENT_DISPLAY_NAME}",
      "description": "${AGENT_DESCRIPTION}",
      "adk_agent_definition": {
        "tool_settings": { "tool_description": "${TOOL_DESCRIPTION}" },
        "provisioned_reasoning_engine": { "reasoning_engine": "${REASONING_ENGINE}" },
        "authorizations": [ "projects/${GOOGLE_CLOUD_PROJECT_NUMBER}/locations/global/authorizations/${AUTH_ID}" ]
      }
    }
EOF
    )
fi

# --- 3. Make the API call ---
echo "📡 Making API request to ${HTTP_METHOD} agent…"
response=$(curl -s -w "\n%{http_code}" -X ${HTTP_METHOD} \
  -H "Authorization: Bearer ${AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT}" \
  "${API_ENDPOINT}" \
  -d "${JSON_PAYLOAD}")

# Extract response body and status code
http_code=$(echo "$response" | tail -n1)
response_body=$(echo "$response" | sed '$d')

echo "📋 Response:"
echo "$response_body" | jq . 2>/dev/null || echo "$response_body"

if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 201 ]; then
    echo "✅ Agent ${HTTP_METHOD} operation successful!"
else
    echo "❌ Failed to ${HTTP_METHOD} agent (HTTP $http_code)"
    echo "   Check your configuration and try again"
    exit 1
fi
