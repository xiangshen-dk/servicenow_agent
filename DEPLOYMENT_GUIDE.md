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
2. **APIs Enabled**:
   - Vertex AI API
   - Secret Manager API
   - Cloud Storage API
3. **ServiceNow Instance** with API access
4. **Local Environment**:
   - Python 3.10+
   - Google Cloud SDK (`gcloud`)
   - ADK installed

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
google-cloud-aiplatform[agent_engines,adk]==1.106.0
google-adk==1.8.0
httpx==0.28.1
pydantic==2.11.7
pydantic-settings==2.10.1
python-dotenv==1.1.1
cloudpickle==3.1.1
google-cloud-secret-manager==2.24.0
```

## Post-Deployment

### 1. Grant Permissions
After deployment, grant necessary permissions to the service agent:
```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor"
```

### 2. Test the Agent
- Access the agent through Vertex AI console
- Test basic operations like "List all open incidents"
- Monitor logs for any runtime issues

### 3. Agent Capabilities
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

1. **Security**: ServiceNow password is stored in Google Secret Manager
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
