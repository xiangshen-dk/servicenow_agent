#!/bin/bash

# ServiceNow Agent Deployment Script
set -euo pipefail  # Exit on error, undefined variables, and pipe failures

# Set up error trap for better error handling
trap 'echo "❌ Deployment failed at line $LINENO. Check logs for details."; exit 1' ERR

echo "🚀 ServiceNow Agent Deployment Script"
echo "===================================="

# Check if PROJECT_ID is set
if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: PROJECT_ID environment variable is not set"
    echo "Please run: export PROJECT_ID=your-project-id"
    exit 1
fi

# Set bucket name
BUCKET_NAME=${PROJECT_ID}-agent-staging

echo "📋 Deployment Configuration:"
echo "  Project ID: $PROJECT_ID"
echo "  Region: us-central1"
echo "  Staging Bucket: gs://$BUCKET_NAME"
echo ""

# Enable required Google Cloud APIs
echo "🔧 Enabling required Google Cloud APIs..."
REQUIRED_APIS=(
    "aiplatform.googleapis.com"
    "discoveryengine.googleapis.com"
    "storage-api.googleapis.com"
    "storage-component.googleapis.com"
    "cloudresourcemanager.googleapis.com"
)
for api in "${REQUIRED_APIS[@]}"; do
    echo "  Enabling $api..."
    gcloud services enable $api --project=$PROJECT_ID --quiet
done
echo "✅ All required APIs enabled"
echo ""

# Check if .env file exists
if [ ! -f "snow_agent/.env" ]; then
    echo "⚠️  Warning: snow_agent/.env file not found"
    echo "Creating from example..."
    cp snow_agent/.env.example snow_agent/.env
    echo "❗ Please edit snow_agent/.env with your ServiceNow credentials and other settings before deploying"
    exit 1
fi

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

# Check if bucket exists, create if not
echo "🪣 Checking staging bucket..."
if ! gsutil ls -b gs://${BUCKET_NAME} &> /dev/null; then
    echo "Creating staging bucket..."
    gsutil mb -p ${PROJECT_ID} gs://${BUCKET_NAME}
else
    echo "✅ Staging bucket already exists"
fi

# --- DEPLOYMENT WORKFLOW ---

# Step 1: Deploy the agent to get the reasoning engine URI
echo ""
echo "STEP 1: Deploying Agent to Agent Engine..."
# Run deployment and capture output, then extract just the URI from the last line
DEPLOYMENT_OUTPUT=$(python deploy_to_agent_engine.py 2>&1)
DEPLOYMENT_EXIT_CODE=$?
if [ $DEPLOYMENT_EXIT_CODE -ne 0 ]; then
    echo "❌ Agent deployment failed."
    echo "$DEPLOYMENT_OUTPUT"
    exit 1
fi
# Extract the URI from the last line of output
REASONING_ENGINE_URI=$(echo "$DEPLOYMENT_OUTPUT" | tail -n 1)
echo "✅ Agent deployed successfully."
echo "   Reasoning Engine URI: $REASONING_ENGINE_URI"

# Save the reasoning engine URI to .env for recovery/future use
echo ""
echo "💾 Saving Reasoning Engine URI to .env file..."
if grep -q "^REASONING_ENGINE=" snow_agent/.env; then
    # Update existing REASONING_ENGINE line
    # Use a more robust approach: delete the old line and add the new one
    grep -v "^REASONING_ENGINE=" snow_agent/.env > snow_agent/.env.tmp
    echo "REASONING_ENGINE=$REASONING_ENGINE_URI" >> snow_agent/.env.tmp
    mv snow_agent/.env.tmp snow_agent/.env
    echo "✅ Updated REASONING_ENGINE in .env"
else
    # Add REASONING_ENGINE if it doesn't exist
    echo "REASONING_ENGINE=$REASONING_ENGINE_URI" >> snow_agent/.env
    echo "✅ Added REASONING_ENGINE to .env"
fi

# Step 2: Create the authorization resource
echo ""
echo "STEP 2: Creating GCP Authorization resource..."
./scripts/create_authorization.sh
if [ $? -ne 0 ]; then
    echo "❌ Authorization creation failed."
    exit 1
fi
echo "✅ Authorization resource created successfully."

# Step 3: Patch the agent with the authorization
echo ""
echo "STEP 3: Patching agent with authorization..."
export REASONING_ENGINE=$REASONING_ENGINE_URI
./scripts/create_or_patch_agent.sh
if [ $? -ne 0 ]; then
    echo "❌ Agent patching failed."
    exit 1
fi
echo "✅ Agent patched successfully."

echo ""
echo "🎉 Deployment and configuration complete!"
echo ""
echo "📝 Next steps:"
echo "1. Test the agent in the AgentSpace web interface or via the API."
echo "2. Monitor the agent's performance and logs in Google Cloud Console."
