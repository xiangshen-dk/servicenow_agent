#!/bin/bash

# =============================================================================
# REGISTER/UNREGISTER DEPLOYED AGENT TO/FROM AGENTSPACE APP
# =============================================================================
# This script registers or unregisters an already deployed agent (reasoning engine) 
# to/from an existing AgentSpace app.
#
# Usage: 
#   Register:   ./register_agent.sh --register <reasoning_engine_uri> <agentspace_app_id>
#   Unregister: ./register_agent.sh --unregister <agentspace_app_id> [agent_display_name]
#
# Arguments:
#   --register:          Register an agent to an app
#   --unregister:        Unregister an agent from an app
#   reasoning_engine_uri: The URI of the deployed reasoning engine (for register)
#   agentspace_app_id:   The ID of the AgentSpace app
#   agent_display_name:  Optional display name for unregister (defaults to env var)

set -euo pipefail  # Exit on error, undefined variables, and pipe failures

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
ACTION=""
REASONING_ENGINE_URI=""
AS_APP_ID=""
AGENT_DISPLAY_NAME_ARG=""

# Function to show usage
show_usage() {
    echo "Usage:"
    echo "  Register agent:"
    echo "    $0 --register <reasoning_engine_uri> <agentspace_app_id>"
    echo ""
    echo "  Unregister agent:"
    echo "    $0 --unregister <agentspace_app_id> [agent_display_name]"
    echo ""
    echo "Examples:"
    echo "  Register:"
    echo "    $0 --register projects/123/locations/us-central1/reasoningEngines/456 my-app_1234567890"
    echo ""
    echo "  Unregister (using display name from .env):"
    echo "    $0 --unregister my-app_1234567890"
    echo ""
    echo "  Unregister (with specific display name):"
    echo "    $0 --unregister my-app_1234567890 \"My Agent Name\""
    echo ""
    echo "Arguments:"
    echo "  --register:           Register an agent to an app"
    echo "  --unregister:         Unregister an agent from an app"
    echo "  reasoning_engine_uri: The URI of the deployed reasoning engine (for register)"
    echo "  agentspace_app_id:    The ID of the AgentSpace app"
    echo "  agent_display_name:   Optional display name for unregister"
}

# Check if we have at least 2 arguments
if [ $# -lt 2 ]; then
    echo -e "${RED}❌ Error: Invalid number of arguments${NC}"
    echo ""
    show_usage
    exit 1
fi

# Parse the action
case "$1" in
    --register)
        ACTION="register"
        if [ $# -ne 3 ]; then
            echo -e "${RED}❌ Error: Register requires exactly 3 arguments${NC}"
            echo ""
            show_usage
            exit 1
        fi
        REASONING_ENGINE_URI="$2"
        AS_APP_ID="$3"
        
        # Validate reasoning engine URI format
        if [[ ! $REASONING_ENGINE_URI =~ ^projects/[^/]+/locations/[^/]+/reasoningEngines/[^/]+$ ]]; then
            echo -e "${RED}❌ Error: Invalid reasoning engine URI format${NC}"
            echo "Expected format: projects/PROJECT_ID/locations/LOCATION/reasoningEngines/ENGINE_ID"
            exit 1
        fi
        ;;
    --unregister)
        ACTION="unregister"
        if [ $# -lt 2 ] || [ $# -gt 3 ]; then
            echo -e "${RED}❌ Error: Unregister requires 2 or 3 arguments${NC}"
            echo ""
            show_usage
            exit 1
        fi
        AS_APP_ID="$2"
        if [ $# -eq 3 ]; then
            AGENT_DISPLAY_NAME_ARG="$3"
        fi
        ;;
    *)
        echo -e "${RED}❌ Error: Invalid action. Use --register or --unregister${NC}"
        echo ""
        show_usage
        exit 1
        ;;
esac

# Display action header
if [ "$ACTION" = "register" ]; then
    echo -e "${YELLOW}🔗 Register Agent to AgentSpace App${NC}"
else
    echo -e "${YELLOW}🔓 Unregister Agent from AgentSpace App${NC}"
fi
echo "===================================="

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
required_vars=("GOOGLE_CLOUD_PROJECT" "GOOGLE_CLOUD_PROJECT_NUMBER")
for var in "${required_vars[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo -e "${RED}❌ Error: Required environment variable $var is not set in .env${NC}"
        exit 1
    fi
done

# Set default values if not provided in .env
ASSISTANT_ID="${ASSISTANT_ID:-default_assistant}"
AGENT_NAME="${AGENT_NAME:-ServiceNow Agent}"
AGENT_DISPLAY_NAME="${AGENT_DISPLAY_NAME:-$AGENT_NAME}"
AGENT_DESCRIPTION="${AGENT_DESCRIPTION:-AI agent for managing ServiceNow records through natural language}"
TOOL_DESCRIPTION="${TOOL_DESCRIPTION:-A tool to perform Create, Read, Update, and Delete operations on ServiceNow records.}"
AGENT_ICON_URL="${AGENT_ICON_URL:-}"  # Optional icon URL

# Override display name if provided as argument for unregister
if [ "$ACTION" = "unregister" ] && [ -n "$AGENT_DISPLAY_NAME_ARG" ]; then
    AGENT_DISPLAY_NAME="$AGENT_DISPLAY_NAME_ARG"
fi

echo ""
echo "📋 Configuration:"
echo "   Project: $GOOGLE_CLOUD_PROJECT"
echo "   Project Number: $GOOGLE_CLOUD_PROJECT_NUMBER"
echo "   AgentSpace App: $AS_APP_ID"
echo "   Assistant ID: $ASSISTANT_ID"
echo "   Agent Display Name: $AGENT_DISPLAY_NAME"
if [ -n "${AGENT_ICON_URL}" ]; then
    echo "   Agent Icon URL: $AGENT_ICON_URL"
fi
if [ "$ACTION" = "register" ]; then
    echo "   Reasoning Engine: $REASONING_ENGINE_URI"
fi
echo ""

# Get authentication token
AUTH_TOKEN=$(gcloud auth print-access-token)
if [ -z "$AUTH_TOKEN" ]; then
    echo -e "${RED}❌ Error: Failed to get authentication token${NC}"
    echo "Please ensure you are logged in with: gcloud auth login"
    exit 1
fi

# Set up API endpoints
DISCOVERY_ENGINE_API_BASE_URL="https://discoveryengine.googleapis.com"
AGENTS_API_ENDPOINT="${DISCOVERY_ENGINE_API_BASE_URL}/v1alpha/projects/${GOOGLE_CLOUD_PROJECT}/locations/global/collections/default_collection/engines/${AS_APP_ID}/assistants/${ASSISTANT_ID}/agents"

# Function to unregister agent
unregister_agent() {
    echo "🔎 Looking for agent with display name: '$AGENT_DISPLAY_NAME'..."
    
    # Get list of agents
    response=$(curl -s -X GET \
      -H "Authorization: Bearer ${AUTH_TOKEN}" \
      -H "Content-Type: application/json" \
      -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT}" \
      "${AGENTS_API_ENDPOINT}" 2>/dev/null)
    
    # Check if we got a valid response
    if [ -z "$response" ] || [[ "$response" == *"error"* && "$response" == *"404"* ]]; then
        echo -e "${RED}❌ Error: Could not retrieve agents from app${NC}"
        echo "   Please check if the app ID is correct: $AS_APP_ID"
        exit 1
    fi
    
    # Show available agents
    echo ""
    echo "Available agents in this app:"
    echo "$response" | jq -r '.agents[] | "  - \(.displayName) (ID: \(.name | split("/") | .[-1]))"' 2>/dev/null || echo "  Could not parse agents list"
    
    # Extract the full agent resource name
    AGENT_RESOURCE=$(echo "$response" | jq -r --arg NAME "$AGENT_DISPLAY_NAME" '.agents[] | select(.displayName == $NAME) | .name' 2>/dev/null)
    
    if [ -z "$AGENT_RESOURCE" ] || [ "$AGENT_RESOURCE" = "null" ]; then
        echo ""
        echo -e "${RED}❌ Error: No agent found with display name '$AGENT_DISPLAY_NAME'${NC}"
        echo "Please check the agent display name and try again"
        exit 1
    fi
    
    # Extract just the numeric agent ID from the end of the resource path
    AGENT_ID=$(echo "$AGENT_RESOURCE" | awk -F'/' '{print $NF}')
    echo ""
    echo "Found agent:"
    echo "  Resource: $AGENT_RESOURCE"
    echo "  Agent ID: $AGENT_ID"
    
    # Confirm deletion
    echo ""
    echo -e "${YELLOW}⚠️  Warning: This will unregister the agent from AgentSpace${NC}"
    read -p "Are you sure you want to continue? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
        echo "Unregistration cancelled."
        exit 0
    fi
    
    # Delete the agent
    echo ""
    echo -e "${BLUE}📡 Deleting agent from AgentSpace...${NC}"
    
    delete_response=$(curl -s -w "\n%{http_code}" -X DELETE \
      -H "Authorization: Bearer ${AUTH_TOKEN}" \
      -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT}" \
      "${AGENTS_API_ENDPOINT}/${AGENT_ID}" 2>/dev/null)
    
    http_code=$(echo "$delete_response" | tail -n1)
    response_body=$(echo "$delete_response" | sed '$d')
    
    if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 204 ]; then
        echo -e "${GREEN}✅ Agent successfully unregistered from AgentSpace!${NC}"
        echo ""
        echo "The agent has been removed from the app."
        echo "Note: The reasoning engine still exists and can be registered to another app if needed."
    else
        echo -e "${RED}❌ Failed to unregister agent (HTTP $http_code)${NC}"
        if [ -n "$response_body" ]; then
            echo ""
            echo "Error details:"
            echo "$response_body" | jq . 2>/dev/null || echo "$response_body"
        fi
        exit 1
    fi
}

# Function to register agent
register_agent() {
    # Check if agent with same display name already exists
    echo "🔎 Checking for existing agent with display name: '$AGENT_DISPLAY_NAME'..."
    response=$(curl -s -X GET \
      -H "Authorization: Bearer ${AUTH_TOKEN}" \
      -H "Content-Type: application/json" \
      -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT}" \
      "${AGENTS_API_ENDPOINT}" 2>/dev/null)

    # Check if we got a valid response
    if [ -z "$response" ] || [[ "$response" == *"error"* && "$response" == *"404"* ]]; then
        echo -e "${YELLOW}⚠️  Warning: Could not check for existing agents${NC}"
        echo "   This might be a new app or the app ID might be incorrect"
    else
        # Extract agent ID if it exists
        EXISTING_AGENT_ID=$(echo "$response" | jq -r --arg NAME "$AGENT_DISPLAY_NAME" '.agents[] | select(.displayName == $NAME) | .name' 2>/dev/null | cut -d'/' -f10)
        
        if [ -n "$EXISTING_AGENT_ID" ] && [ "$EXISTING_AGENT_ID" != "null" ]; then
            echo -e "${YELLOW}⚠️  Agent with display name '$AGENT_DISPLAY_NAME' already exists (ID: $EXISTING_AGENT_ID)${NC}"
            read -p "Do you want to update the existing agent? (yes/no): " -r
            if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
                echo "Registration cancelled."
                exit 0
            fi
            HTTP_METHOD="PATCH"
            API_ENDPOINT="${AGENTS_API_ENDPOINT}/${EXISTING_AGENT_ID}"
            echo "Will update existing agent..."
        else
            HTTP_METHOD="POST"
            API_ENDPOINT="${AGENTS_API_ENDPOINT}"
            echo "Will create new agent..."
        fi
    fi

    # If we couldn't determine, default to POST (create)
    if [ -z "${HTTP_METHOD:-}" ]; then
        HTTP_METHOD="POST"
        API_ENDPOINT="${AGENTS_API_ENDPOINT}"
    fi

    # Prepare the JSON payload for agent registration
    # Build the base JSON structure
    JSON_BASE='{
  "displayName": "'"${AGENT_DISPLAY_NAME}"'",
  "description": "'"${AGENT_DESCRIPTION}"'"'
    
    # Add icon URL if provided
    if [ -n "${AGENT_ICON_URL}" ]; then
        JSON_BASE="${JSON_BASE}"',
  "icon": {
    "uri": "'"${AGENT_ICON_URL}"'"
  }'
    fi
    
    # Add ADK agent definition
    JSON_BASE="${JSON_BASE}"',
  "adk_agent_definition": {
    "tool_settings": {
      "tool_description": "'"${TOOL_DESCRIPTION}"'"
    },
    "provisioned_reasoning_engine": {
      "reasoning_engine": "'"${REASONING_ENGINE_URI}"'"
    }'
    
    # Add authorization if OAuth is configured
    if [ -n "${AUTH_ID:-}" ]; then
        JSON_BASE="${JSON_BASE}"',
    "authorizations": [
      "projects/'"${GOOGLE_CLOUD_PROJECT_NUMBER}"'/locations/global/authorizations/'"${AUTH_ID}"'"
    ]'
    fi
    
    # Close the JSON structure
    JSON_PAYLOAD="${JSON_BASE}"'
  }
}'

    # Make the API call to register/update the agent
    echo ""
    echo -e "${BLUE}📡 Making API request to ${HTTP_METHOD} agent...${NC}"
    echo "Endpoint: $API_ENDPOINT"

    response=$(curl -s -w "\n%{http_code}" -X ${HTTP_METHOD} \
      -H "Authorization: Bearer ${AUTH_TOKEN}" \
      -H "Content-Type: application/json" \
      -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT}" \
      "${API_ENDPOINT}" \
      -d "${JSON_PAYLOAD}" 2>/dev/null)

    # Extract response body and status code
    http_code=$(echo "$response" | tail -n1)
    response_body=$(echo "$response" | sed '$d')

    # Check the response
    if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 201 ]; then
        echo -e "${GREEN}✅ Agent successfully registered to AgentSpace!${NC}"
        echo ""
        echo "📋 Agent Details:"
        echo "$response_body" | jq . 2>/dev/null || echo "$response_body"
        
        # Extract and display the agent ID
        AGENT_ID=$(echo "$response_body" | jq -r '.name' 2>/dev/null | cut -d'/' -f10)
        if [ -n "$AGENT_ID" ] && [ "$AGENT_ID" != "null" ]; then
            echo ""
            echo -e "${GREEN}Agent ID: $AGENT_ID${NC}"
        fi
        
        # Update .env file with the AgentSpace app ID if not already set
        if [ -z "${AS_APP:-}" ] || [ "$AS_APP" != "$AS_APP_ID" ]; then
            echo ""
            echo "Updating .env file with AgentSpace app ID..."
            grep -v "^AS_APP=" snow_agent/.env > snow_agent/.env.tmp 2>/dev/null || true
            echo "AS_APP=$AS_APP_ID" >> snow_agent/.env.tmp
            mv snow_agent/.env.tmp snow_agent/.env
            echo -e "${GREEN}✅ Updated AS_APP in .env${NC}"
        fi
        
        # Update REASONING_ENGINE in .env if different
        if [ -z "${REASONING_ENGINE:-}" ] || [ "$REASONING_ENGINE" != "$REASONING_ENGINE_URI" ]; then
            grep -v "^REASONING_ENGINE=" snow_agent/.env > snow_agent/.env.tmp 2>/dev/null || true
            echo "REASONING_ENGINE=$REASONING_ENGINE_URI" >> snow_agent/.env.tmp
            mv snow_agent/.env.tmp snow_agent/.env
            echo -e "${GREEN}✅ Updated REASONING_ENGINE in .env${NC}"
        fi
        
        echo ""
        echo -e "${GREEN}🎉 Registration complete!${NC}"
        echo ""
        echo "Next steps:"
        echo "1. Test the agent in the AgentSpace web interface"
        echo "2. Monitor the agent's performance and logs in Google Cloud Console"
        
    else
        echo -e "${RED}❌ Failed to register agent (HTTP $http_code)${NC}"
        echo ""
        echo "Error details:"
        echo "$response_body" | jq . 2>/dev/null || echo "$response_body"
        
        # Provide helpful error messages
        if [ "$http_code" -eq 401 ]; then
            echo ""
            echo "Authentication error. Please ensure:"
            echo "- You are logged in with: gcloud auth login"
            echo "- You have the necessary permissions in the project"
        elif [ "$http_code" -eq 404 ]; then
            echo ""
            echo "Resource not found. Please check:"
            echo "- The AgentSpace app ID is correct: $AS_APP_ID"
            echo "- The app exists in your project"
        elif [ "$http_code" -eq 400 ]; then
            echo ""
            echo "Bad request. Please check:"
            echo "- The reasoning engine URI is valid"
            echo "- All required fields are properly configured"
        fi
        
        exit 1
    fi
}

# Execute the appropriate action
if [ "$ACTION" = "register" ]; then
    register_agent
else
    unregister_agent
fi
