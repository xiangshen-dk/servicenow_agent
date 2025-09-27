# ServiceNow Agent Deployment Guide

This guide provides comprehensive instructions for deploying the ServiceNow agent to Google Cloud's Vertex AI Agent Engine with OAuth authentication.

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Environment Configuration](#environment-configuration)
4. [Deployment Process](#deployment-process)
5. [Troubleshooting](#troubleshooting)
6. [Post-Deployment](#post-deployment)

## Overview

The ServiceNow agent is an AI-powered tool that enables natural language interaction with ServiceNow instances for performing CRUD operations on records. It uses OAuth 2.0 authentication via GCP Authorization for secure access.

### Key Features
- Natural language processing for ServiceNow operations
- Full CRUD support (Create, Read, Update, Delete)
- OAuth 2.0 authentication via GCP Authorization
- Support for multiple ServiceNow tables
- Comprehensive error handling and logging

## Prerequisites

### Required Setup
1. **Google Cloud Project** with billing enabled
2. **ServiceNow Instance** with OAuth 2.0 client configured
3. **Local Environment**:
   - Python 3.13+
   - Google Cloud SDK (`gcloud`)
   - UV package manager

### ServiceNow OAuth Setup
1. In ServiceNow, create an OAuth 2.0 client application
2. Note the Client ID and Client Secret
3. Configure the OAuth endpoint for client credentials flow

### Required Google Cloud APIs
The deployment script automatically enables these APIs:
- Vertex AI API (`aiplatform.googleapis.com`)
- Discovery Engine API (`discoveryengine.googleapis.com`)
- Cloud Storage APIs (`storage-api.googleapis.com`, `storage-component.googleapis.com`)
- Cloud Resource Manager API (`cloudresourcemanager.googleapis.com`)

## Environment Configuration

### 1. Create Configuration File
```bash
cp snow_agent/.env.example snow_agent/.env
```

### 2. Edit snow_agent/.env with your values:
```bash
# Google Cloud / Vertex AI Configuration
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1

# AgentSpace Configuration (if using AgentSpace)
AS_APP=your-agent-space-app-id
ASSISTANT_ID=your-assistant-id

# ServiceNow OAuth Configuration
SERVICENOW_INSTANCE_URL=https://dev123456.service-now.com
SERVICENOW_CLIENT_ID=your-servicenow-client-id
SERVICENOW_CLIENT_SECRET=your-servicenow-client-secret

# Agent Configuration
AGENT_NAME=servicenow_agent
AGENT_DISPLAY_NAME="ServiceNow Agent"
AGENT_DESCRIPTION="An AI agent for managing ServiceNow records through natural language"
TOOL_DESCRIPTION="A tool to perform Create, Read, Update, and Delete operations on ServiceNow records."
AGENT_MODEL=gemini-2.5-flash
AGENT_VERSION=20250918.1

# GCP Authorization Configuration
AUTH_ID=servicenow-oauth-auth
```

## Deployment Process

The deployment is a three-step process orchestrated by the `deploy.sh` script:

### Quick Deploy
```bash
# Run the deployment script
./scripts/deploy.sh
```

### What the Script Does

#### Step 1: Deploy Agent to Agent Engine
- Deploys the agent code to Vertex AI Agent Engine
- Creates a reasoning engine resource
- Returns a reasoning engine URI

#### Step 2: Create GCP Authorization
- Creates an OAuth 2.0 authorization resource in GCP
- Stores ServiceNow client credentials securely
- Links to the ServiceNow OAuth endpoints

#### Step 3: Patch Agent with Authorization
- Dynamically retrieves the project number from the project ID
- Links the deployed agent to the authorization resource
- Enables the agent to use OAuth for ServiceNow access

### Manual Deployment (Advanced)

If you need to run the steps individually:

```bash
# Step 1: Deploy the agent (output will be shown via tee)
TEMP_OUTPUT=$(mktemp)
python deploy_to_agent_engine.py 2>&1 | tee "$TEMP_OUTPUT"
REASONING_ENGINE_URI=$(tail -n 1 "$TEMP_OUTPUT")
rm -f "$TEMP_OUTPUT"

# Step 2: Create authorization
./scripts/create_authorization.sh

# Step 3: Link agent to authorization (automatically gets project number)
export REASONING_ENGINE=$REASONING_ENGINE_URI
./scripts/create_or_patch_agent.sh
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Authentication Error
**Error**: `No access token found for auth_id: None`

**Solution**: Ensure AUTH_ID is set in your .env file and matches the authorization resource ID.

#### 2. Serialization Error
**Error**: `Failed to serialize agent engine`

**Solution**: This has been fixed in the latest version. Ensure you're using the updated code.

#### 3. OAuth Token Error
**Error**: `OAuthProblemException`

**Solution**: 
- Verify ServiceNow OAuth client is configured for client credentials flow
- Check that client ID and secret are correct
- Ensure ServiceNow instance URL is correct

#### 4. Checking Deployment Logs

View detailed logs in Cloud Console:
```
https://console.cloud.google.com/logs/query?project=YOUR_PROJECT_ID
```

Use this query to find deployment logs:
```
resource.type="aiplatform.googleapis.com/ReasoningEngine"
```

### Requirements File

The `deploy_requirements.txt` contains all necessary dependencies:
```
google-cloud-aiplatform[adk,agent-engines]>=1.114.0
google-adk>=1.14.1
httpx>=0.27.0
pydantic>=2.11.9
pydantic-settings>=2.0.0
python-dotenv>=1.0.0
cloudpickle>=3.1.1
```

## Post-Deployment

### 1. Verify Deployment
- Check that all three steps completed successfully
- The reasoning engine URI is saved in your .env file
- Authorization resource is created in GCP

### 2. Test the Agent
Access the agent through:
- AgentSpace web interface (if configured)
- Vertex AI console
- Direct API calls

### 3. Example Commands
Test with these ServiceNow operations:
- "Create a new incident with short description 'Printer not working'"
- "Show me all open incidents"
- "Update incident INC0010001 priority to high"
- "Close incident INC0010001 with resolution 'Fixed'"

### 4. Security Features
- **OAuth 2.0**: Secure authentication using client credentials flow
- **GCP Authorization**: Credentials stored securely in GCP, not in code
- **Token Management**: Access tokens are managed by the runtime
- **No Plain Text Secrets**: All sensitive data is encrypted

## Agent Capabilities

### Supported Operations
- **Create**: New ServiceNow records with specified fields
- **Read**: Search and retrieve existing records
- **Update**: Modify record fields and states
- **Delete**: Remove records from ServiceNow

### Supported Tables
- incident
- change_request
- problem
- sc_task
- sc_req_item
- cmdb_ci

## Important Notes

1. **OAuth Flow**: The agent uses OAuth 2.0 client credentials flow, not username/password
2. **Project Number**: Automatically retrieved from project ID during deployment - no manual configuration needed
3. **Environment Variables**: Critical variables like AUTH_ID must be set for proper operation
4. **Runtime Token Management**: The agent retrieves OAuth tokens at runtime from GCP
5. **No Local Testing**: OAuth flow requires deployment to Agent Engine

## Support

For additional help:
1. Review Google Cloud logs for detailed error messages
2. Verify ServiceNow OAuth client configuration
3. Check that all environment variables are set correctly
4. Ensure all required Google Cloud APIs are enabled

---

Last Updated: September 2025
