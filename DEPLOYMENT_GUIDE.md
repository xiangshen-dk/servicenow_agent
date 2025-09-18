# ServiceNow Agent Deployment Guide

This guide consolidates all deployment information for the ServiceNow agent to Google Cloud's Vertex AI Agent Engine.

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Deployment Methods](#deployment-methods)
4. [Troubleshooting](#troubleshooting)
5. [Post-Deployment](#post-deployment)

## Overview

The ServiceNow agent is an AI-powered tool that enables natural language interaction with ServiceNow instances for performing CRUD operations on records. It has been prepared for deployment to Google Cloud's Vertex AI Agent Engine.

### Key Features
- Natural language processing for ServiceNow operations
- Full CRUD support (Create, Read, Update, Delete)
- Secure credential management via Google Secret Manager
- Support for multiple ServiceNow tables
- Comprehensive error handling and logging

## Prerequisites

### Required Setup
1. **Google Cloud Project** with billing enabled
2. **ServiceNow Instance** with API access
3. **Local Environment**:
   - Python 3.10+
   - Google Cloud SDK (`gcloud`)
   - ADK installed

### Automatic API Enablement
The deployment scripts automatically enable these required APIs:
- Vertex AI API (`aiplatform.googleapis.com`)
- Secret Manager API (`secretmanager.googleapis.com`)
- Cloud Storage API (`storage-api.googleapis.com`)
- Cloud Storage Component API (`storage-component.googleapis.com`)
- Cloud Resource Manager API (`cloudresourcemanager.googleapis.com`)

If automatic enablement fails, you can manually enable them:
```bash
gcloud services enable aiplatform.googleapis.com secretmanager.googleapis.com \
  storage-api.googleapis.com storage-component.googleapis.com \
  cloudresourcemanager.googleapis.com --project=YOUR_PROJECT_ID
```

### Environment Configuration

Create a `snow_agent/.env` file with your credentials:
```bash
cp snow_agent/.env.example snow_agent/.env
# Then edit snow_agent/.env with your values:
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com
SERVICENOW_USERNAME=your-username
SERVICENOW_PASSWORD=your-password
```

## Deployment Methods

### Method 1: ADK CLI (Recommended)

The simplest and most reliable deployment method uses the ADK CLI directly:

```bash
# Step 1: Set up environment variables
export PROJECT_ID=your-project-id
export BUCKET_NAME=${PROJECT_ID}-agent-staging

# Step 2: Create staging bucket (if it doesn't exist)
gsutil mb -p ${PROJECT_ID} gs://${BUCKET_NAME}

# Step 3: Deploy the agent
adk deploy agent_engine --project=$PROJECT_ID \
    --region=us-central1 \
    --staging_bucket=gs://${BUCKET_NAME} \
    --display_name="ServiceNow Agent" ./snow_agent
```

**Note**: ADK automatically reads the `.env` file from `snow_agent/.env` during deployment.

### Method 2: Python Script (Alternative)

For automated deployment with additional validation:

```bash
python deploy_to_agent_engine.py
```

The script provides:
- Environment variable validation
- Automatic Secret Manager integration
- Detailed error handling and logging
- Automated bucket creation

## Troubleshooting

### Common Issues and Solutions

#### 1. Agent Failed to Start
**Error**: `Reasoning Engine resource [...] failed to start and cannot serve traffic`

**Solutions**:
- Ensure all dependencies are in `deploy_requirements.txt`
- Use stable model versions (e.g., `gemini-1.5-flash`)
- Check for import errors in the deployment logs
- Verify environment variables are correctly set

#### 2. Import Errors
**Issue**: Module import failures in deployment environment

**Solutions**:
- Use absolute imports instead of relative imports
- Ensure the agent code is in `snow_agent/` directory (not `src/snow_agent/`)
- Include all transitive dependencies

#### 3. Checking Deployment Logs

View detailed logs in Cloud Console:
```
https://console.cloud.google.com/logs/query?project=YOUR_PROJECT_ID
```

Use this query to find deployment logs:
```
resource.type="aiplatform.googleapis.com/ReasoningEngine"
resource.labels.reasoning_engine_id="YOUR_RESOURCE_ID"
```

### Requirements File

The `deploy_requirements.txt` must be clean without comments:
```
google-cloud-aiplatform[adk,agent-engines]>=1.114.0
google-adk>=1.14.1
httpx>=0.27.0
pydantic>=2.11.9
pydantic-settings>=2.0.0
python-dotenv>=1.0.0
cloudpickle>=3.1.1
google-cloud-secret-manager>=2.24.0
```

## Post-Deployment

### 1. Automatic Security Configuration
The deployment process automatically:
- Stores the ServiceNow password in Google Secret Manager
- Grants the agent service account access to the secret
- Configures the agent to fetch the password at runtime

No manual IAM configuration is required for Secret Manager access.

### 2. Test the Agent
- Access the agent through Vertex AI console
- Test basic operations like "List all open incidents"
- Monitor logs for any runtime issues

### 3. Security Features
- **Password Security**: ServiceNow password is never stored in plain text on the deployed agent
- **Secret Manager Integration**: Password is securely stored in Google Secret Manager
- **Automatic IAM**: Service account permissions are automatically configured during deployment
- **Runtime Fetching**: Password is fetched from Secret Manager only when needed

### 4. Agent Capabilities
The deployed agent can:
- **Create**: New ServiceNow records with specified fields
- **Read**: Search and retrieve existing records
- **Update**: Modify record fields and states
- **Delete**: Remove records from ServiceNow

### Example Commands
- "Create a new incident with short description 'Printer not working'"
- "Show me all incidents assigned to john.doe"
- "Update incident INC0010001 priority to high"
- "Resolve INC0010001 with resolution code 'Solved'"

## Important Notes

1. **Security**: 
   - ServiceNow password is automatically uploaded to Google Secret Manager during deployment
   - The password in .env file is only used during deployment, not stored on the agent
   - IAM permissions are automatically configured for the agent service account
2. **File Structure**: Agent code must be in `snow_agent/` directory
3. **Model Selection**: Use stable models for production deployments
4. **Error Handling**: Check logs immediately after deployment for any issues

## Support

For additional help:
1. Review Google Cloud logs for detailed error messages
2. Ensure all prerequisites are met
3. Verify ServiceNow credentials and API access
4. Check that all required Google Cloud APIs are enabled

## Quick Reference

Based on successful deployment example:
```bash
# Complete deployment in 3 commands
PROJECT_ID=your-project-id
BUCKET_NAME=${PROJECT_ID}-agent-staging

# Deploy (bucket will be created automatically if needed)
adk deploy agent_engine --project=$PROJECT_ID \
    --region=us-central1 \
    --staging_bucket=gs://${BUCKET_NAME} \
    --display_name="ServiceNow Agent" ./snow_agent
```

---

Last Updated: August 2025
