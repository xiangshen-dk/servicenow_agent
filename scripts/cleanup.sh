#!/bin/bash

# =============================================================================
# CLEANUP SCRIPT FOR SERVICENOW AGENT
# =============================================================================
# This script removes all deployed resources:
# 1. Unregisters the agent from AgentSpace
# 2. Deletes the GCP Authorization resource
# 3. Deletes the Agent Engine (Reasoning Engine)
# 
# Run this script to completely clean up all deployed resources.

set -euo pipefail  # Exit on error, undefined variables, and pipe failures

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🧹 ServiceNow Agent Cleanup Script${NC}"
echo "===================================="

# Load environment variables
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
    echo -e "${GREEN}✅ Loaded snow_agent/.env file${NC}"
else
    echo -e "${RED}❌ Error: snow_agent/.env file not found.${NC}"
    exit 1
fi

# Validate required variables
required_vars=("GOOGLE_CLOUD_PROJECT" "GOOGLE_CLOUD_PROJECT_NUMBER" "GOOGLE_CLOUD_LOCATION")
for var in "${required_vars[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo -e "${RED}❌ Error: Required environment variable $var is not set in .env${NC}"
        exit 1
    fi
done

echo ""
echo -e "${YELLOW}⚠️  WARNING: This will delete all deployed resources!${NC}"
echo "   Project: $GOOGLE_CLOUD_PROJECT"
echo "   Location: $GOOGLE_CLOUD_LOCATION"
echo ""
read -p "Are you sure you want to continue? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Starting cleanup process..."

# --- Step 1: Delete Agent from AgentSpace (if configured) ---
if [ -n "${AS_APP:-}" ] && [ -n "${ASSISTANT_ID:-}" ] && [ -n "${AGENT_NAME:-}" ]; then
    echo ""
    echo -e "${YELLOW}STEP 1: Removing Agent from AgentSpace...${NC}"
    
    AUTH_TOKEN=$(gcloud auth print-access-token)
    DISCOVERY_ENGINE_API_BASE_URL="https://discoveryengine.googleapis.com"
    AGENTS_API_ENDPOINT="${DISCOVERY_ENGINE_API_BASE_URL}/v1alpha/projects/${GOOGLE_CLOUD_PROJECT}/locations/global/collections/default_collection/engines/${AS_APP}/assistants/${ASSISTANT_ID}/agents"
    
    # Check if agent exists
    echo "🔎 Checking for agent with display name: '${AGENT_DISPLAY_NAME:-$AGENT_NAME}'..."
    response=$(curl -s -X GET \
      -H "Authorization: Bearer ${AUTH_TOKEN}" \
      -H "Content-Type: application/json" \
      -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT}" \
      "${AGENTS_API_ENDPOINT}")
    
    # Debug: Show available agents
    echo "Available agents:"
    echo "$response" | jq -r '.agents[] | "\(.displayName) -> \(.name)"' 2>/dev/null || echo "Could not parse agents list"
    
    # Extract the full agent resource name
    AGENT_RESOURCE=$(echo "$response" | jq -r --arg NAME "${AGENT_DISPLAY_NAME:-$AGENT_NAME}" '.agents[] | select(.displayName == $NAME) | .name' 2>/dev/null)
    
    if [ -n "$AGENT_RESOURCE" ] && [ "$AGENT_RESOURCE" != "null" ]; then
        # Extract just the numeric agent ID from the end of the resource path
        AGENT_ID=$(echo "$AGENT_RESOURCE" | awk -F'/' '{print $NF}')
        echo "Found agent resource: $AGENT_RESOURCE"
        echo "Agent ID: $AGENT_ID"
        echo "Deleting agent from AgentSpace..."
        
        delete_response=$(curl -s -w "\n%{http_code}" -X DELETE \
          -H "Authorization: Bearer ${AUTH_TOKEN}" \
          -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT}" \
          "${AGENTS_API_ENDPOINT}/${AGENT_ID}")
        
        http_code=$(echo "$delete_response" | tail -n1)
        response_body=$(echo "$delete_response" | sed '$d')
        
        if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 204 ]; then
            echo -e "${GREEN}✅ Agent removed from AgentSpace${NC}"
        else
            echo -e "${YELLOW}⚠️  Could not remove agent from AgentSpace (HTTP $http_code)${NC}"
            if [ -n "$response_body" ]; then
                echo "   Error details: $response_body"
            fi
            echo "   You may need to remove it manually from the AgentSpace console"
        fi
    else
        echo "No agent found in AgentSpace to delete"
    fi
else
    echo ""
    echo "STEP 1: Skipping AgentSpace cleanup (not configured)"
fi

# --- Step 2: Delete GCP Authorization ---
if [ -n "${AUTH_ID:-}" ]; then
    echo ""
    echo -e "${YELLOW}STEP 2: Deleting GCP Authorization resource...${NC}"
    echo "   Auth ID: $AUTH_ID"
    
    AUTH_TOKEN=$(gcloud auth print-access-token)
    DISCOVERY_ENGINE_API_BASE_URL="https://discoveryengine.googleapis.com/v1alpha"
    
    # Check if authorization exists
    check_response=$(curl -s -w "\n%{http_code}" -X GET \
         -H "Authorization: Bearer ${AUTH_TOKEN}" \
         -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT}" \
         "${DISCOVERY_ENGINE_API_BASE_URL}/projects/${GOOGLE_CLOUD_PROJECT}/locations/global/authorizations/${AUTH_ID}")
    
    http_code=$(echo "$check_response" | tail -n1)
    
    if [ "$http_code" -eq 200 ]; then
        echo "Authorization found, deleting..."
        
        delete_response=$(curl -s -w "\n%{http_code}" -X DELETE \
             -H "Authorization: Bearer ${AUTH_TOKEN}" \
             -H "X-Goog-User-Project: ${GOOGLE_CLOUD_PROJECT}" \
             "${DISCOVERY_ENGINE_API_BASE_URL}/projects/${GOOGLE_CLOUD_PROJECT}/locations/global/authorizations/${AUTH_ID}")
        
        http_code=$(echo "$delete_response" | tail -n1)
        response_body=$(echo "$delete_response" | sed '$d')
        
        if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 204 ]; then
            echo -e "${GREEN}✅ Authorization resource deleted${NC}"
        else
            echo -e "${YELLOW}⚠️  Could not delete authorization (HTTP $http_code)${NC}"
            if [ -n "$response_body" ]; then
                echo "   Error details:"
                echo "$response_body" | jq . 2>/dev/null || echo "$response_body"
            fi
            if [ "$http_code" -eq 400 ]; then
                echo "   This usually means the authorization is still in use by an agent."
                echo "   Try deleting the agent from AgentSpace first."
            fi
            echo "   You may need to delete it manually"
        fi
    else
        echo "No authorization found to delete"
    fi
else
    echo ""
    echo "STEP 2: Skipping Authorization cleanup (AUTH_ID not set)"
fi

# --- Step 3: Delete Reasoning Engine ---
if [ -n "${REASONING_ENGINE:-}" ]; then
    echo ""
    echo -e "${YELLOW}STEP 3: Deleting Reasoning Engine (Agent Engine)...${NC}"
    echo "   URI: $REASONING_ENGINE"
    
    # Extract the resource name from the URI
    # Format: projects/PROJECT_ID/locations/LOCATION/reasoningEngines/ENGINE_ID
    if [[ $REASONING_ENGINE =~ projects/([^/]+)/locations/([^/]+)/reasoningEngines/([^/]+) ]]; then
        PROJECT="${BASH_REMATCH[1]}"
        LOCATION="${BASH_REMATCH[2]}"
        ENGINE_ID="${BASH_REMATCH[3]}"
        
        echo "Deleting reasoning engine ID: $ENGINE_ID"
        
        # Use REST API to delete the reasoning engine since gcloud doesn't have this command
        AUTH_TOKEN=$(gcloud auth print-access-token)
        VERTEX_API_BASE_URL="https://${LOCATION}-aiplatform.googleapis.com/v1beta1"
        
        delete_response=$(curl -s -w "\n%{http_code}" -X DELETE \
            -H "Authorization: Bearer ${AUTH_TOKEN}" \
            -H "Content-Type: application/json" \
            "${VERTEX_API_BASE_URL}/projects/${PROJECT}/locations/${LOCATION}/reasoningEngines/${ENGINE_ID}")
        
        http_code=$(echo "$delete_response" | tail -n1)
        response_body=$(echo "$delete_response" | sed '$d')
        
        if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 204 ]; then
            echo -e "${GREEN}✅ Reasoning Engine deleted${NC}"
            
            # Remove REASONING_ENGINE from .env
            echo "Removing REASONING_ENGINE from .env..."
            grep -v "^REASONING_ENGINE=" snow_agent/.env > snow_agent/.env.tmp
            mv snow_agent/.env.tmp snow_agent/.env
            echo -e "${GREEN}✅ Removed REASONING_ENGINE from .env${NC}"
        else
            echo -e "${YELLOW}⚠️  Could not delete reasoning engine (HTTP $http_code)${NC}"
            if [ -n "$response_body" ]; then
                echo "   Error details:"
                echo "$response_body" | jq . 2>/dev/null || echo "$response_body"
            fi
            echo "   Common issues:"
            echo "   - Permission denied: Ensure you have 'Vertex AI Administrator' role"
            echo "   - Resource in use: The engine might be referenced by AgentSpace"
            echo "   - 404 error: The engine might already be deleted"
            echo "   You may need to delete it manually from the Vertex AI console"
        fi
    else
        echo -e "${RED}❌ Could not parse REASONING_ENGINE URI${NC}"
        echo "   Please delete the reasoning engine manually"
    fi
else
    echo ""
    echo "STEP 3: Skipping Reasoning Engine cleanup (REASONING_ENGINE not set)"
    echo "   If you have deployed an agent, you may need to delete it manually"
fi

# --- Step 4: Optional - Clean up staging bucket ---
echo ""
echo -e "${YELLOW}STEP 4: Staging Bucket Cleanup${NC}"
BUCKET_NAME="${GOOGLE_CLOUD_PROJECT}-agent-staging"
echo "   Bucket: gs://$BUCKET_NAME"

read -p "Do you want to delete the staging bucket? (yes/no): " -r
if [[ $REPLY =~ ^[Yy]es$ ]]; then
    if gsutil ls -b gs://${BUCKET_NAME} &> /dev/null; then
        echo "Deleting staging bucket..."
        if gsutil -m rm -r gs://${BUCKET_NAME} 2>/dev/null; then
            echo -e "${GREEN}✅ Staging bucket deleted${NC}"
        else
            echo -e "${YELLOW}⚠️  Could not delete staging bucket${NC}"
            echo "   You may need to delete it manually"
        fi
    else
        echo "Staging bucket not found"
    fi
else
    echo "Keeping staging bucket"
fi

echo ""
echo -e "${GREEN}🎉 Cleanup complete!${NC}"
echo ""
echo "Summary:"
echo "- AgentSpace agent: Removed (if configured)"
echo "- GCP Authorization: Deleted"
echo "- Reasoning Engine: Deleted"
echo "- Staging bucket: Based on your choice"
echo ""
echo "All deployed resources have been cleaned up."
