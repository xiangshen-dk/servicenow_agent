# ServiceNow Agent

An AI-powered agent that enables natural language interaction with ServiceNow instances for performing CRUD operations on records.

## Features

- 🤖 Natural language processing for ServiceNow operations
- 📝 Full CRUD support (Create, Read, Update, Delete)
- 🔒 Secure credential management via Google Secret Manager
- 📊 Support for multiple ServiceNow tables
- ☁️ Deployable to Google Cloud Agent Engine

## Quick Start

### Prerequisites

- Python 3.10+
- Google Cloud SDK with ADK
- ServiceNow instance with API access
- Google Cloud project with billing enabled

### Setup

1. **Clone and install**:
```bash
git clone <repository-url>
cd servicenow-agent
pip install uv
uv sync
```

2. **Configure credentials**:
```bash
cp snow_agent/.env.example snow_agent/.env
# Edit snow_agent/.env with your ServiceNow credentials
```

3. **Run locally**:
```bash
adk web
```

## Deployment

### Quick Deploy

```bash
export PROJECT_ID=your-gcp-project
./deploy.sh
```

### Manual Deploy

```bash
export PROJECT_ID=your-gcp-project
export BUCKET_NAME=${PROJECT_ID}-agent-staging

adk deploy agent_engine --project=$PROJECT_ID \
    --region=us-central1 \
    --staging_bucket=gs://${BUCKET_NAME} \
    --display_name="ServiceNow Agent" ./snow_agent
```

For detailed instructions, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

## Usage Examples

### Basic Commands
- **Create**: "Create a new incident with short description 'Printer not working'"
- **Read**: "List all open incidents"
- **Update**: "Update incident INC0010001 priority to high"
- **Delete**: "Delete problem INC0010001"

## Configuration

Create `snow_agent/.env` with:
```
SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com
SERVICENOW_USERNAME=your-username
SERVICENOW_PASSWORD=your-password
GOOGLE_CLOUD_PROJECT=your-project-id
```

## Supported Tables

- incident
- change_request
- problem
- sc_task
- sc_req_item
- cmdb_ci

## Architecture

Built with:
- **Google ADK**: Agent Development Kit
- **Gemini Models**: Natural language understanding
- **ServiceNow REST API**: CRUD operations
- **Python 3.10+**: Async support

## Security

- **Secret Manager Integration**: ServiceNow password automatically stored in Google Secret Manager during deployment
- **No Plain Text Passwords**: Password is never stored in plain text on the deployed agent
- **Automatic IAM Configuration**: Service account permissions are automatically set up
- **Runtime Secret Access**: Password is fetched from Secret Manager only when needed
- **HTTPS Communications**: All ServiceNow API calls use secure HTTPS

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
