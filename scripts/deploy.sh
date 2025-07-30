#!/bin/bash
# Deployment script for ServiceNow Agent to Google AgentSpace

set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-"your-gcp-project"}
REGION=${REGION:-"us-central1"}
IMAGE_NAME="servicenow-agent"
IMAGE_TAG=${IMAGE_TAG:-"latest"}

echo "Deploying ServiceNow Agent to Google AgentSpace"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Image: $IMAGE_NAME:$IMAGE_TAG"

# Build container image
echo "Building container image..."
docker build -t gcr.io/$PROJECT_ID/$IMAGE_NAME:$IMAGE_TAG .

# Push to Google Container Registry
echo "Pushing image to GCR..."
docker push gcr.io/$PROJECT_ID/$IMAGE_NAME:$IMAGE_TAG

# Create secrets if they don't exist
echo "Checking for ServiceNow credentials secret..."
if ! kubectl get secret servicenow-credentials &> /dev/null; then
    echo "Creating servicenow-credentials secret..."
    echo "Please ensure you have set the following environment variables:"
    echo "- SERVICENOW_INSTANCE_URL"
    echo "- SERVICENOW_USERNAME" 
    echo "- SERVICENOW_PASSWORD"
    
    kubectl create secret generic servicenow-credentials \
        --from-literal=instance_url="$SERVICENOW_INSTANCE_URL" \
        --from-literal=username="$SERVICENOW_USERNAME" \
        --from-literal=password="$SERVICENOW_PASSWORD"
fi

# Deploy to AgentSpace
echo "Deploying agent to AgentSpace..."
envsubst < agentspace.yaml | kubectl apply -f -

echo "Deployment complete!"
echo "Agent should be available in AgentSpace shortly."