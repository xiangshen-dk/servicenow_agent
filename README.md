# ServiceNow Agent for Google AgentSpace

An AI-powered agent that enables natural language interaction with ServiceNow instances for performing CRUD operations on records.

## Features

- 🤖 Natural language processing for ServiceNow operations
- 📝 Full CRUD support (Create, Read, Update, Delete)
- 🔒 Secure credential management
- 📊 Support for multiple ServiceNow tables
- ☁️ Deployable to Google AgentSpace
- 🛡️ Comprehensive error handling and logging
- 📅 Advanced query support with date ranges and operators
- 🔄 Automatic JSON string parsing for web interface compatibility

## Quick Start

### Prerequisites

- Python 3.13+
- Google ADK access
- ServiceNow instance with API access
- Google Cloud account (for AgentSpace deployment)

### Local Development

1. Clone the repository:
```bash
git clone <repository-url>
cd servicenow-agent
```

2. Install dependencies:
```bash
pip install uv
uv pip install -e .
```

3. Configure environment:
```bash
cp snow_agent/.env.example snow_agent/.env
# Edit snow_agent/.env with your ServiceNow credentials
```

4. Run the agent:
```bash
# Option 1: Run as a module (recommended)
python -m main

# Option 2: Use the run script
python run.py

# Option 3: For development with ADK web interface
adk web
```

**Note**: If you encounter "attempted relative import with no known parent package" error, see [FIX_RELATIVE_IMPORT_ERROR.md](FIX_RELATIVE_IMPORT_ERROR.md) for solutions.

## Usage Examples

The agent understands natural language commands for ServiceNow operations:

### Basic Operations
- **Create**: "Create a new incident with short description 'Printer not working' and urgency high"
- **Read**: "Show me all incidents assigned to john.doe"
- **Update**: "Update incident INC0010001 priority to high"
- **Delete**: "Delete problem PRB0010001"

### Advanced Queries
- **Date-based**: "List open incidents since June 2025"
- **Date ranges**: "Show incidents created between January and March 2025"
- **State filtering**: "List all non-resolved incidents"
- **Complex updates**: "Resolve INC0010001 with resolution code 'Solved (Permanently)' and close notes 'Fixed the configuration'"

### Important Notes
- When resolving or closing incidents, you must provide:
  - Resolution code (for state=Resolved)
  - Close code (for state=Closed)
  - Close notes describing the resolution

## Configuration

### Environment Variables

- `SERVICENOW_INSTANCE_URL`: Your ServiceNow instance URL
- `SERVICENOW_USERNAME`: ServiceNow API username
- `SERVICENOW_PASSWORD`: ServiceNow API password
- `AGENT_MODEL`: Google AI model (default: google/gemini-2.5-flash-lite)
- `SERVICENOW_ALLOWED_TABLES`: Comma-separated list of allowed tables

### Supported Tables

By default, the agent supports:
- incident
- change_request
- problem
- sc_task
- sc_req_item
- cmdb_ci

## Deployment to AgentSpace

1. Set up Google Cloud credentials:
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

2. Deploy the agent:
```bash
export PROJECT_ID=your-gcp-project
python deploy_to_agent_engine.py
```

## Architecture

The agent is built using:
- **Google ADK**: Agent Development Kit for AI capabilities
- **Gemini Models**: For natural language understanding
- **ServiceNow REST API**: For CRUD operations
- **Async Python**: For efficient API calls

## Development

See [CLAUDE.md](CLAUDE.md) for detailed development guidance.

## Security

- Credentials are stored securely using environment variables
- API passwords are handled as secrets
- All communications with ServiceNow use HTTPS
- Deployment uses Google Cloud Secret Manager

## License

[Your License Here]
