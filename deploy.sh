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

# Check if .env file exists
if [ ! -f "snow_agent/.env" ]; then
    echo "⚠️  Warning: snow_agent/.env file not found"
    echo "Creating from example..."
    cp snow_agent/.env.example snow_agent/.env
    echo "❗ Please edit snow_agent/.env with your ServiceNow credentials before deploying"
    exit 1
fi

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
    echo "📝 Next steps:"
    echo "1. Check the deployment logs in Google Cloud Console"
    echo "2. Test the agent with queries like 'List all open incidents'"
    echo "3. Monitor the agent performance and logs"
else
    echo ""
    echo "❌ Deployment failed. Please check the error messages above."
    echo "For troubleshooting, see DEPLOYMENT_GUIDE.md"
fi
