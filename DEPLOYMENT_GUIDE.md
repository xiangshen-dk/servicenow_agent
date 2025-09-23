# ServiceNow Agent Deployment Guide

This guide provides comprehensive deployment instructions for the ServiceNow agent to Google Cloud's Vertex AI Agent Engine.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Deployment Methods](#deployment-methods)
4. [Script Management Tools](#script-management-tools)
5. [Troubleshooting](#troubleshooting)
6. [Security](#security)

## Prerequisites

### Required Setup
- **Google Cloud Project** with billing enabled
- **ServiceNow Instance** with API access
- **Python 3.10+** with pip/uv
- **Google Cloud SDK** (`gcloud`) authenticated
- **ADK** installed (`pip install google-adk`)

### Environment Configuration

```bash
# Copy and configure environment file
cp snow_agent/.env.example snow_agent/.env

# Edit snow_agent/.env with your values:
# GOOGLE_CLOUD_PROJECT=your-project-id
# GOOGLE_CLOUD_LOCATION=us-central1
# SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com
# SERVICENOW_USERNAME=your-username
# SERVICENOW_PASSWORD=your-password
```

## Quick Start

```bash
# 1. Configure environment
cp snow_agent/.env.example snow_agent/.env
# Edit .env with your credentials

# 2. Deploy the agent
./deploy.sh

# The script automatically:
# - Enables required Google Cloud APIs
# - Creates staging bucket
# - Deploys to Vertex AI Agent Engine
# - Configures Secret Manager
# - Sets up IAM permissions
```

## Deployment Methods

### Method 1: Automated Script (Recommended)

```bash
./deploy.sh
```

Features:
- ✅ Automatic API enablement
- ✅ Staging bucket creation
- ✅ Secret Manager integration
- ✅ IAM configuration
- ✅ Color-coded output
- ✅ Error handling

### Method 2: Manual ADK CLI

```bash
export PROJECT_ID=your-project-id
export BUCKET_NAME=${PROJECT_ID}-agent-staging

# Create bucket if needed
gsutil mb -p ${PROJECT_ID} gs://${BUCKET_NAME}

# Deploy
adk deploy agent_engine --project=$PROJECT_ID \
    --region=us-central1 \
    --staging_bucket=gs://${BUCKET_NAME} \
    --display_name="ServiceNow Agent" ./snow_agent
```

## Script Management Tools

### Project Structure
```
/
├── deploy.sh                       # Main deployment script
├── deploy_to_agent_engine.py      # Python deployment module
├── scripts/
│   ├── register_agent.sh          # AgentSpace registration
│   └── remove_agent_engine.sh     # Engine removal tool
└── snow_agent/
    └── requirements.txt            # Dependencies
```

### Agent Registration

Register or unregister agents with AgentSpace apps:

```bash
# Register agent to app
./scripts/register_agent.sh --register \
  <reasoning_engine_uri> <app_id>

# Unregister agent from app
./scripts/register_agent.sh --unregister <app_id> [agent_name]
```

### Agent Engine Removal

Remove deployed reasoning engines:

```bash
# Remove by full URI
./scripts/remove_agent_engine.sh <reasoning_engine_uri>

# Remove by ID (uses .env for project/location)
./scripts/remove_agent_engine.sh <engine_id>
```

⚠️ **Warning**: Deletion is permanent. Script requires typing "DELETE" to confirm.

## Troubleshooting

### Common Issues

#### Agent Failed to Start
- Check all dependencies in `snow_agent/requirements.txt`
- Verify environment variables in `.env`
- Use stable model versions (e.g., `gemini-1.5-flash`)
- Review deployment logs in Cloud Console

#### Import Errors
- Use absolute imports (not relative)
- Ensure code is in `snow_agent/` directory
- Include all transitive dependencies

### Viewing Logs

```bash
# Cloud Console logs
https://console.cloud.google.com/logs/query?project=YOUR_PROJECT_ID

# Log query for deployment issues
resource.type="aiplatform.googleapis.com/ReasoningEngine"
resource.labels.reasoning_engine_id="YOUR_ENGINE_ID"
```

### Required APIs

The deployment script automatically enables:
- `aiplatform.googleapis.com`
- `secretmanager.googleapis.com`
- `storage-api.googleapis.com`
- `storage-component.googleapis.com`
- `cloudresourcemanager.googleapis.com`

Manual enablement if needed:
```bash
gcloud services enable aiplatform.googleapis.com \
  secretmanager.googleapis.com storage-api.googleapis.com \
  storage-component.googleapis.com cloudresourcemanager.googleapis.com \
  --project=YOUR_PROJECT_ID
```

## Security

### Automatic Security Features
- **Secret Manager**: Password stored securely, never in plain text
- **IAM Configuration**: Service account permissions auto-configured
- **Runtime Access**: Credentials fetched only when needed
- **HTTPS Only**: All ServiceNow API calls use secure connections

### Post-Deployment Verification
1. Verify Secret Manager contains password
2. Check service account has `secretmanager.secretAccessor` role
3. Test agent with simple query: "List all open incidents"
4. Monitor logs for any permission issues

## Agent Capabilities

### Supported Operations
- **Create**: New ServiceNow records
- **Read**: Search and retrieve records
- **Update**: Modify record fields
- **Delete**: Remove records

### Example Commands
```
"Create a new incident with short description 'Printer issue'"
"Show all incidents assigned to john.doe"
"Update INC0010001 priority to high"
"Resolve INC0010001 with resolution 'Fixed'"
```

### Supported Tables
- incident
- change_request
- problem
- sc_task
- sc_req_item
- cmdb_ci

## Requirements File

The `snow_agent/requirements.txt` should contain:
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

---

Last Updated: September 2025
