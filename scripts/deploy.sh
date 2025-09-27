#!/bin/bash

# =============================================================================
# SERVICENOW AGENT DEPLOYMENT SCRIPT
# =============================================================================
# Deploys the ServiceNow agent to Google Cloud with OAuth authentication.
# Steps: 1) Deploy to Agent Engine 2) Create Authorization 3) Link them

set -euo pipefail  # Exit on error, undefined variables, and pipe failures

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 ServiceNow Agent Deployment Script${NC}"
echo "===================================="

# Check if .env file exists
if [ ! -f "snow_agent/.env" ]; then
    echo -e "${RED}❌ Error: snow_agent/.env file not found${NC}"
    echo "Creating from example..."
    cp snow_agent/.env.example snow_agent/.env
    echo -e "${YELLOW}Please edit snow_agent/.env with your configuration and run again${NC}"
    exit 1
fi

# Load environment variables
echo "Loading configuration from .env..."
source snow_agent/.env

# Validate required variables
if [ -z "${GOOGLE_CLOUD_PROJECT:-}" ]; then
    echo -e "${RED}❌ Error: GOOGLE_CLOUD_PROJECT not set in .env${NC}"
    exit 1
fi

PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
BUCKET_NAME="${PROJECT_ID}-agent-staging"

echo "📋 Configuration:"
echo "   Project: $PROJECT_ID"
echo "   Location: ${GOOGLE_CLOUD_LOCATION:-us-central1}"
echo "   Bucket: gs://$BUCKET_NAME"
echo ""

# Enable required APIs
echo "🔧 Enabling required APIs..."
APIS="aiplatform.googleapis.com discoveryengine.googleapis.com storage-api.googleapis.com"
for api in $APIS; do
    gcloud services enable $api --project=$PROJECT_ID --quiet &
done
wait
echo -e "${GREEN}✅ APIs enabled${NC}"

# Create staging bucket if needed
if ! gsutil ls -b gs://${BUCKET_NAME} &> /dev/null; then
    echo "Creating staging bucket..."
    gsutil mb -p ${PROJECT_ID} gs://${BUCKET_NAME}
fi

# --- DEPLOYMENT WORKFLOW ---

echo -e "\n${YELLOW}STEP 1: Deploying to Agent Engine...${NC}"
TEMP_OUTPUT=$(mktemp)
python deploy_to_agent_engine.py 2>&1 | tee "$TEMP_OUTPUT"
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo -e "${RED}❌ Deployment failed${NC}"
    rm -f "$TEMP_OUTPUT"
    exit 1
fi
REASONING_ENGINE_URI=$(tail -n 1 "$TEMP_OUTPUT")
rm -f "$TEMP_OUTPUT"
echo -e "${GREEN}✅ Deployed: $REASONING_ENGINE_URI${NC}"

# Save URI to .env
grep -v "^REASONING_ENGINE=" snow_agent/.env > snow_agent/.env.tmp 2>/dev/null || true
echo "REASONING_ENGINE=$REASONING_ENGINE_URI" >> snow_agent/.env.tmp
mv snow_agent/.env.tmp snow_agent/.env

echo -e "\n${YELLOW}STEP 2: Creating Authorization...${NC}"
./scripts/create_authorization.sh
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Authorization creation failed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Authorization created${NC}"

echo -e "\n${YELLOW}STEP 3: Linking Agent to Authorization...${NC}"
export REASONING_ENGINE=$REASONING_ENGINE_URI
./scripts/create_or_patch_agent.sh
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Agent linking failed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Agent linked${NC}"

echo -e "\n${GREEN}🎉 Deployment complete!${NC}\n"
echo "Next steps:"
echo "• Test in AgentSpace or Vertex AI console"
echo "• Monitor logs in Cloud Console"
echo "• Run ./scripts/cleanup.sh to remove all resources"
