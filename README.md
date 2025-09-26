# ServiceNow Agent

An AI-powered agent that enables natural language interaction with ServiceNow instances for performing CRUD operations on records.

## Features

- 🤖 Natural language processing for ServiceNow operations
- 📝 Full CRUD support (Create, Read, Update, Delete)
- 🔒 Secure OAuth 2.0 authentication via GCP Authorization
- 📊 Support for multiple ServiceNow tables
- ☁️ Deployable to Google Cloud Agent Engine

## Quick Start

### Prerequisites

- Python 3.13+
- Google Cloud SDK with ADK
- ServiceNow instance with an OAuth 2.0 client ID and secret
- Google Cloud project with billing enabled

### Setup

1. **Clone and install**:
```bash
git clone <repository-url>
cd servicenow_agent
pip install uv
uv sync
source .venv/bin/activate
```

2. **Configure credentials**:
```bash
cp snow_agent/.env.example snow_agent/.env
# Edit snow_agent/.env with your GCP and ServiceNow OAuth credentials
```

3. **Run locally**:
The new OAuth flow requires deployment to Agent Engine to function correctly, as it relies on the runtime to provide the access token. Local execution with `adk web` is not supported with this authentication method.

## Deployment

The deployment process is orchestrated by the `deploy.sh` script, which reads all configuration from your `.env` file.

1.  **Run Deployment Script**:
    ```bash
    ./scripts/deploy.sh
    ```

This script will:
1.  Deploy the agent code to Agent Engine.
2.  Create a GCP Authorization resource with your ServiceNow OAuth credentials.
3.  Patch the deployed agent to link it to the new authorization.

### Cleanup

To remove all deployed resources:
```bash
./scripts/cleanup.sh
```

This will:
- Remove the agent from AgentSpace (if configured)
- Delete the GCP Authorization resource
- Delete the Reasoning Engine from Vertex AI
- Optionally delete the staging bucket

For detailed instructions, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

## Configuration

Create `snow_agent/.env` with the following variables:

```
# Google Cloud / Vertex AI Configuration
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1

# AgentSpace Configuration
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
- **Python 3.13+**: Async support

## Security

- **OAuth 2.0**: Uses the secure OAuth 2.0 client credentials flow for authentication.
- **GCP Authorization**: ServiceNow client ID and secret are securely stored in a GCP Authorization resource, not in the agent's code or environment.
- **Automatic IAM Configuration**: The deployment script handles the necessary IAM permissions for the agent to access the authorization resource.
- **Managed Access Tokens**: The Agent Engine runtime manages the OAuth access token lifecycle, including fetching and refreshing tokens. The agent code only handles short-lived access tokens.
- **HTTPS Communications**: All ServiceNow API calls use secure HTTPS.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
