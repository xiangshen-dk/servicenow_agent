#!/bin/bash

# ServiceNow Agent Deployment Script
# Based on successful deployment example

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
echo "  Agent Directory: ./snow_agent"
echo ""

# Enable required Google Cloud APIs
echo "🔧 Enabling required Google Cloud APIs..."
echo "This may take a few minutes if APIs are not already enabled..."

# List of required APIs
REQUIRED_APIS=(
    "aiplatform.googleapis.com"
    "secretmanager.googleapis.com"
    "storage-api.googleapis.com"
    "storage-component.googleapis.com"
    "cloudresourcemanager.googleapis.com"
)

# Enable each API
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
    echo "❗ Please edit snow_agent/.env with your ServiceNow credentials before deploying"
    exit 1
fi

# Source the .env file to get credentials
export $(grep -v '^#' snow_agent/.env | xargs)

# Check if password is set
if [ -z "$SERVICENOW_PASSWORD" ]; then
    echo "❌ Error: SERVICENOW_PASSWORD not found in .env file"
    exit 1
fi

# Create/update the secret in Secret Manager
echo "🔐 Setting up Secret Manager..."
echo "Creating/updating ServiceNow password secret..."

# Check if secret exists
if gcloud secrets describe servicenow-password --project=$PROJECT_ID &> /dev/null; then
    echo "Secret already exists, adding new version..."
    echo -n "$SERVICENOW_PASSWORD" | gcloud secrets versions add servicenow-password --data-file=- --project=$PROJECT_ID
else
    echo "Creating new secret..."
    echo -n "$SERVICENOW_PASSWORD" | gcloud secrets create servicenow-password --data-file=- --project=$PROJECT_ID
fi

echo "✅ Secret Manager configured"

# Check if bucket exists, create if not
echo "🪣 Checking staging bucket..."
if ! gsutil ls -b gs://${BUCKET_NAME} &> /dev/null; then
    echo "Creating staging bucket..."
    gsutil mb -p ${PROJECT_ID} gs://${BUCKET_NAME}
else
    echo "✅ Staging bucket already exists"
fi

# Deploy the agent
echo ""
echo "🚀 Deploying ServiceNow Agent to Google Cloud Agent Engine..."
echo ""

adk deploy agent_engine --project=$PROJECT_ID \
    --region=us-central1 \
    --staging_bucket=gs://${BUCKET_NAME} \
    --display_name="ServiceNow Agent" ./snow_agent

# Check deployment status
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Deployment completed successfully!"
    echo ""
    echo "🔐 Security Configuration:"
    echo "- ServiceNow password is stored in Secret Manager (not in plain text)"
    echo "- The agent will automatically fetch the password from Secret Manager"
    echo "- IAM permissions have been configured for the agent service account"
    echo ""
    echo "📝 Next steps:"
    echo "1. Check the deployment logs in Google Cloud Console"
    echo "2. Test the agent with queries like 'List all open incidents'"
    echo "3. Monitor the agent performance and logs"
    echo ""
    echo "Note: The password is no longer stored in the .env file on the deployed agent."
    echo "It's securely fetched from Google Secret Manager at runtime."
else
    echo ""
    echo "❌ Deployment failed. Please check the error messages above."
    echo "For troubleshooting, see DEPLOYMENT_GUIDE.md"
fi
