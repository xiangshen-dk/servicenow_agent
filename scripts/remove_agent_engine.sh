#!/bin/bash

# =============================================================================
# REMOVE AGENT ENGINE (REASONING ENGINE) BY ID
# =============================================================================
# This script removes a deployed agent engine (reasoning engine) from Vertex AI.
# WARNING: This permanently deletes the agent engine and cannot be undone.
#
# Usage: ./remove_agent_engine.sh <reasoning_engine_uri_or_id>
#
# Arguments:
#   reasoning_engine_uri_or_id: Either the full URI or just the engine ID
#     Full URI: projects/123/locations/us-central1/reasoningEngines/456
#     Engine ID: 456 (will use project/location from .env)

set -euo pipefail  # Exit on error, undefined variables, and pipe failures

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🗑️  Remove Agent Engine (Reasoning Engine)${NC}"
echo "=========================================="

# Function to show usage
show_usage() {
    echo "Usage: $0 <reasoning_engine_uri_or_id>"
    echo ""
    echo "Examples:"
    echo "  With full URI:"
    echo "    $0 projects/123/locations/us-central1/reasoningEngines/456"
    echo ""
    echo "  With just engine ID (uses project/location from .env):"
    echo "    $0 456"
    echo ""
    echo "Arguments:"
    echo "  reasoning_engine_uri_or_id: The URI or ID of the reasoning engine to delete"
    echo ""
    echo "WARNING: This action is permanent and cannot be undone!"
}

# Check arguments
if [ $# -ne 1 ]; then
    echo -e "${RED}❌ Error: Invalid number of arguments${NC}"
    echo ""
    show_usage
    exit 1
fi

INPUT_ARG="$1"

# Load environment variables from .env file
if [ -f snow_agent/.env ]; then
    # Source the .env file with proper quoting to handle special characters
    set +a  # Disable automatic export
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ "$key" =~ ^#.*$ ]] && continue
        [[ -z "$key" ]] && continue

        # Strip leading/trailing whitespace from key
        key=$(echo "$key" | xargs)

        # Strip leading/trailing whitespace and quotes from value
        # Remove leading/trailing double quotes
        value="${value#\"}"
        value="${value%\"}"
        # Remove leading/trailing single quotes
        value="${value#\'}"
        value="${value%\'}"
        # Trim whitespace
        value=$(echo "$value" | xargs)

        # Export the variable
        export "$key=$value"
    done < snow_agent/.env
    set -a  # Re-enable if needed
    echo -e "${GREEN}✅ Loaded configuration from snow_agent/.env${NC}"
else
    echo -e "${RED}❌ Error: snow_agent/.env file not found${NC}"
    echo "Please ensure you have a configured .env file"
    exit 1
fi

# Validate required environment variables
required_vars=("GOOGLE_CLOUD_PROJECT" "GOOGLE_CLOUD_LOCATION")
for var in "${required_vars[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo -e "${RED}❌ Error: Required environment variable $var is not set in .env${NC}"
        exit 1
    fi
done

# Parse the input to determine if it's a full URI or just an ID
if [[ $INPUT_ARG =~ ^projects/([^/]+)/locations/([^/]+)/reasoningEngines/([^/]+)$ ]]; then
    # Full URI provided
    PROJECT="${BASH_REMATCH[1]}"
    LOCATION="${BASH_REMATCH[2]}"
    ENGINE_ID="${BASH_REMATCH[3]}"
    REASONING_ENGINE_URI="$INPUT_ARG"
    echo "Parsed full URI:"
elif [[ $INPUT_ARG =~ ^[0-9]+$ ]]; then
    # Just engine ID provided, use project/location from env
    PROJECT="$GOOGLE_CLOUD_PROJECT"
    LOCATION="$GOOGLE_CLOUD_LOCATION"
    ENGINE_ID="$INPUT_ARG"
    REASONING_ENGINE_URI="projects/${PROJECT}/locations/${LOCATION}/reasoningEngines/${ENGINE_ID}"
    echo "Using engine ID with project/location from .env:"
else
    echo -e "${RED}❌ Error: Invalid input format${NC}"
    echo "Expected either:"
    echo "  - Full URI: projects/PROJECT/locations/LOCATION/reasoningEngines/ENGINE_ID"
    echo "  - Engine ID: numeric ID (e.g., 456)"
    exit 1
fi

echo "  Project: $PROJECT"
echo "  Location: $LOCATION"
echo "  Engine ID: $ENGINE_ID"
echo "  Full URI: $REASONING_ENGINE_URI"
echo ""

# Get authentication token
AUTH_TOKEN=$(gcloud auth print-access-token)
if [ -z "$AUTH_TOKEN" ]; then
    echo -e "${RED}❌ Error: Failed to get authentication token${NC}"
    echo "Please ensure you are logged in with: gcloud auth login"
    exit 1
fi

# First, check if the reasoning engine exists
echo "🔎 Checking if reasoning engine exists..."
VERTEX_API_BASE_URL="https://${LOCATION}-aiplatform.googleapis.com/v1beta1"

check_response=$(curl -s -w "\n%{http_code}" -X GET \
    -H "Authorization: Bearer ${AUTH_TOKEN}" \
    -H "Content-Type: application/json" \
    "${VERTEX_API_BASE_URL}/${REASONING_ENGINE_URI}" 2>/dev/null)

http_code=$(echo "$check_response" | tail -n1)
response_body=$(echo "$check_response" | sed '$d')

if [ "$http_code" -eq 404 ]; then
    echo -e "${YELLOW}⚠️  Reasoning engine not found${NC}"
    echo "The engine might have already been deleted or the ID is incorrect."
    exit 0
elif [ "$http_code" -ne 200 ]; then
    echo -e "${RED}❌ Error checking reasoning engine (HTTP $http_code)${NC}"
    if [ -n "$response_body" ]; then
        echo "Error details:"
        echo "$response_body" | jq . 2>/dev/null || echo "$response_body"
    fi
    exit 1
fi

# Display engine information
echo -e "${GREEN}✅ Found reasoning engine${NC}"
echo ""
echo "Engine details:"
echo "$response_body" | jq '{
    name: .name,
    displayName: .displayName,
    description: .description,
    createTime: .createTime,
    updateTime: .updateTime
}' 2>/dev/null || echo "$response_body"

# Check if this engine is referenced in AgentSpace
echo ""
echo "🔎 Checking for AgentSpace references..."
if [ -n "${AS_APP:-}" ] && [ -n "${ASSISTANT_ID:-default_assistant}" ]; then
    DISCOVERY_ENGINE_API_BASE_URL="https://discoveryengine.googleapis.com"
    AGENTS_API_ENDPOINT="${DISCOVERY_ENGINE_API_BASE_URL}/v1alpha/projects/${GOOGLE_CLOUD_PROJECT}/locations/global/collections/default_collection/engines/${AS_APP}/assistants/${ASSISTANT_ID}/agents"
    
    agents_response=$(curl -s -X GET \
      -H "Authorization: Bearer ${AUTH_TOKEN}" \
      -H "Content-Type: application/json" \
      -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT}" \
      "${AGENTS_API_ENDPOINT}" 2>/dev/null)
    
    # Check if any agents use this reasoning engine
    if echo "$agents_response" | grep -q "$REASONING_ENGINE_URI"; then
        echo -e "${YELLOW}⚠️  WARNING: This reasoning engine is referenced by agents in AgentSpace${NC}"
        echo "Agents using this engine:"
        echo "$agents_response" | jq -r --arg URI "$REASONING_ENGINE_URI" '.agents[] | select(.adkAgentDefinition.provisionedReasoningEngine.reasoningEngine == $URI) | "  - \(.displayName)"' 2>/dev/null
        echo ""
        echo "You should unregister these agents first using:"
        echo "  ./scripts/register_agent.sh --unregister $AS_APP [agent_display_name]"
        echo ""
    else
        echo "No AgentSpace references found"
    fi
else
    echo "AgentSpace not configured, skipping reference check"
fi

# Confirm deletion
echo ""
echo -e "${RED}⚠️  WARNING: This action is PERMANENT and CANNOT BE UNDONE!${NC}"
echo "You are about to delete reasoning engine: $ENGINE_ID"
echo ""
read -p "Type 'DELETE' to confirm deletion: " -r
if [ "$REPLY" != "DELETE" ]; then
    echo "Deletion cancelled."
    exit 0
fi

# Delete the reasoning engine
echo ""
echo -e "${BLUE}📡 Deleting reasoning engine...${NC}"

delete_response=$(curl -s -w "\n%{http_code}" -X DELETE \
    -H "Authorization: Bearer ${AUTH_TOKEN}" \
    -H "Content-Type: application/json" \
    "${VERTEX_API_BASE_URL}/${REASONING_ENGINE_URI}" 2>/dev/null)

http_code=$(echo "$delete_response" | tail -n1)
response_body=$(echo "$delete_response" | sed '$d')

if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 204 ]; then
    echo -e "${GREEN}✅ Reasoning Engine successfully deleted${NC}"
    
    # Check if this was the engine in .env and remove it
    if [ -n "${REASONING_ENGINE:-}" ] && [ "$REASONING_ENGINE" = "$REASONING_ENGINE_URI" ]; then
        echo ""
        echo "Removing REASONING_ENGINE from .env..."
        grep -v "^REASONING_ENGINE=" snow_agent/.env > snow_agent/.env.tmp 2>/dev/null || true
        mv snow_agent/.env.tmp snow_agent/.env
        echo -e "${GREEN}✅ Removed REASONING_ENGINE from .env${NC}"
    fi
    
    echo ""
    echo "Summary:"
    echo "- Reasoning Engine ID $ENGINE_ID has been permanently deleted"
    echo "- All associated resources have been cleaned up"
    echo "- The staging bucket may still contain deployment artifacts"
    
elif [ "$http_code" -eq 404 ]; then
    echo -e "${YELLOW}⚠️  Reasoning engine was already deleted or not found${NC}"
else
    echo -e "${RED}❌ Failed to delete reasoning engine (HTTP $http_code)${NC}"
    if [ -n "$response_body" ]; then
        echo ""
        echo "Error details:"
        echo "$response_body" | jq . 2>/dev/null || echo "$response_body"
    fi
    
    echo ""
    echo "Common issues:"
    echo "- Permission denied: Ensure you have 'Vertex AI Administrator' role"
    echo "- Resource in use: The engine might be referenced by AgentSpace agents"
    echo "- Invalid project/location: Check that the project and location are correct"
    echo ""
    echo "You may need to:"
    echo "1. Check your permissions in the Google Cloud Console"
    echo "2. Unregister any agents using this engine first"
    echo "3. Try deleting manually from the Vertex AI console"
    
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 Deletion complete!${NC}"
