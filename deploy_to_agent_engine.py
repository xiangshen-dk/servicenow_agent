#!/usr/bin/env python3
"""
Deploy ServiceNow Agent to Vertex AI Agent Engine

This script deploys the snow_agent to Google Cloud's Vertex AI Agent Engine.
It handles configuration, packaging, and deployment following the official documentation.
"""

import os
import sys
import logging
import argparse
from typing import Optional, Dict, List, Any
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from google.cloud import aiplatform
import vertexai
from vertexai import agent_engines
from snow_agent.agent import create_servicenow_agent
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_environment_variables(env_file: Optional[str] = None) -> None:
    """Load environment variables from .env file"""
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv("snow_agent/.env")  # Load from default .env file
    
    # Validate required environment variables
    required_vars = [
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
        "SERVICENOW_INSTANCE_URL",
        "SERVICENOW_USERNAME",
        "SERVICENOW_PASSWORD"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.info("Please set these variables in your .env file or environment")
        sys.exit(1)


def get_package_requirements() -> str:
    """Define the package requirements for deployment"""
    # Use a clean requirements file without comments
    return "deploy_requirements.txt"


def get_extra_packages() -> List[str]:
    """Define additional local packages to include"""
    # Include the entire snow_agent package directory
    extra_packages = [
        "snow_agent",  # This will include the entire snow_agent directory
    ]
    return extra_packages


def get_environment_variables() -> Dict[str, Any]:
    """Define environment variables for the deployed agent"""
    env_vars = {
        # ServiceNow configuration from environment
        "SERVICENOW_INSTANCE_URL": os.getenv("SERVICENOW_INSTANCE_URL"),
        "SERVICENOW_USERNAME": os.getenv("SERVICENOW_USERNAME"),
        # ServiceNow password will be stored as a secret
        "SERVICENOW_PASSWORD": {
            "secret": "servicenow-password",
            "version": "latest"
        },
        
        # Agent configuration
        "AGENT_NAME": os.getenv("AGENT_NAME", "ServiceNow Agent"),
        "AGENT_DESCRIPTION": os.getenv("AGENT_DESCRIPTION", "AI agent for managing ServiceNow records through natural language"),
        "AGENT_MODEL": os.getenv("AGENT_MODEL", "gemini-2.0-flash-exp"),
        
        # Optional configurations
        "SERVICENOW_ALLOWED_TABLES": os.getenv("SERVICENOW_ALLOWED_TABLES", "incident,change_request,problem,sc_task,sc_req_item,cmdb_ci"),
        "SERVICENOW_API_TIMEOUT": os.getenv("SERVICENOW_API_TIMEOUT", "30"),
        "SERVICENOW_MAX_RECORDS": os.getenv("SERVICENOW_MAX_RECORDS", "100"),
        
        # Logging configuration for production (structured JSON logs, no colors)
        "ENVIRONMENT": "production",
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
        
        # Vertex AI configuration
        "GOOGLE_GENAI_USE_VERTEXAI": "1",
    }
    
    # Remove None values
    env_vars = {k: v for k, v in env_vars.items() if v is not None}
    
    return env_vars


def create_secret_if_not_exists(project_id: str, secret_id: str, secret_value: str) -> None:
    """Create a secret in Secret Manager if it doesn't exist"""
    from google.cloud import secretmanager
    
    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{project_id}"
    
    # Check if secret exists
    try:
        secret_name = f"{parent}/secrets/{secret_id}"
        client.get_secret(request={"name": secret_name})
        logger.info(f"Secret '{secret_id}' already exists")
        
        # Add a new version with the current value
        client.add_secret_version(
            request={
                "parent": secret_name,
                "payload": {"data": secret_value.encode("UTF-8")}
            }
        )
        logger.info(f"Updated secret '{secret_id}' with new version")
    except Exception:
        # Secret doesn't exist, create it
        try:
            client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_id,
                    "secret": {"replication": {"automatic": {}}},
                }
            )
            
            # Add the secret version
            secret_name = f"{parent}/secrets/{secret_id}"
            client.add_secret_version(
                request={
                    "parent": secret_name,
                    "payload": {"data": secret_value.encode("UTF-8")}
                }
            )
            logger.info(f"Created secret '{secret_id}' in Secret Manager")
        except Exception as e:
            logger.error(f"Failed to create secret '{secret_id}': {e}")
            raise


def create_agent_for_deployment():
    """Create the agent instance for deployment."""
    # This function will be executed in the cloud environment
    from snow_agent.agent import create_servicenow_agent
    return create_servicenow_agent()


def get_service_account_email(project_id: str, location: str) -> str:
    """Get the service account email for the Agent Engine."""
    # The service account format for Agent Engine
    project_number = get_project_number(project_id)
    return f"service-{project_number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"


def get_project_number(project_id: str) -> str:
    """Get the project number from project ID."""
    from google.cloud import resourcemanager_v3
    
    client = resourcemanager_v3.ProjectsClient()
    project = client.get_project(name=f"projects/{project_id}")
    return project.name.split('/')[-1]  # Extract project number from name


def grant_secret_access(project_id: str, service_account_email: str, secret_id: str) -> None:
    """Grant the service account access to the secret."""
    from google.cloud import secretmanager
    from google.iam.v1 import iam_policy_pb2, policy_pb2
    
    client = secretmanager.SecretManagerServiceClient()
    secret_name = f"projects/{project_id}/secrets/{secret_id}"
    
    try:
        # Get the current IAM policy
        policy = client.get_iam_policy(request={"resource": secret_name})
        
        # Add the service account with secretAccessor role
        binding = policy_pb2.Binding()
        binding.role = "roles/secretmanager.secretAccessor"
        binding.members.append(f"serviceAccount:{service_account_email}")
        
        # Check if binding already exists
        existing_binding = None
        for b in policy.bindings:
            if b.role == binding.role:
                existing_binding = b
                break
        
        if existing_binding:
            # Add member to existing binding if not already present
            if f"serviceAccount:{service_account_email}" not in existing_binding.members:
                existing_binding.members.append(f"serviceAccount:{service_account_email}")
                logger.info(f"Added {service_account_email} to existing binding for {secret_id}")
            else:
                logger.info(f"{service_account_email} already has access to {secret_id}")
        else:
            # Add new binding
            policy.bindings.append(binding)
            logger.info(f"Created new binding for {service_account_email} to access {secret_id}")
        
        # Update the policy
        client.set_iam_policy(request={"resource": secret_name, "policy": policy})
        logger.info(f"Successfully granted Secret Manager access to {service_account_email}")
        
    except Exception as e:
        logger.error(f"Failed to grant secret access: {e}")
        raise


def enable_required_apis(project_id: str) -> None:
    """Enable required Google Cloud APIs for the deployment."""
    from google.cloud import serviceusage_v1
    
    logger.info("Enabling required Google Cloud APIs...")
    
    # List of required APIs
    required_apis = [
        "aiplatform.googleapis.com",
        "secretmanager.googleapis.com",
        "storage-api.googleapis.com",
        "storage-component.googleapis.com",
        "cloudresourcemanager.googleapis.com",
    ]
    
    client = serviceusage_v1.ServiceUsageClient()
    
    for api in required_apis:
        service_name = f"projects/{project_id}/services/{api}"
        try:
            # Check if the service is already enabled
            service = client.get_service(name=service_name)
            if service.state == serviceusage_v1.Service.State.ENABLED:
                logger.info(f"✓ {api} is already enabled")
            else:
                logger.info(f"Enabling {api}...")
                operation = client.enable_service(name=service_name)
                logger.info(f"✓ {api} enabled successfully")
        except Exception as e:
            logger.warning(f"Could not check/enable {api}: {e}")
            logger.info(f"Please ensure {api} is enabled in your project")


def deploy_agent(
    project_id: str,
    location: str,
    staging_bucket: Optional[str] = None,
    display_name: Optional[str] = None,
    description: Optional[str] = None,
    gcs_dir_name: Optional[str] = None
) -> Any:
    """Deploy the agent to Vertex AI Agent Engine"""
    
    # Enable required APIs
    try:
        enable_required_apis(project_id)
    except Exception as e:
        logger.warning(f"Could not automatically enable APIs: {e}")
        logger.info("Please ensure all required APIs are enabled manually")
    
    # Create default staging bucket name if not provided
    if not staging_bucket:
        staging_bucket = f"gs://{project_id}-agent-staging"
        logger.info(f"No staging bucket provided, using default: {staging_bucket}")
    
    # Initialize Vertex AI with staging bucket
    aiplatform.init(project=project_id, location=location, staging_bucket=staging_bucket)
    vertexai.init(project=project_id, location=location, staging_bucket=staging_bucket)
    
    # Create ServiceNow password secret
    servicenow_password = os.getenv("SERVICENOW_PASSWORD")
    if servicenow_password:
        logger.info("Creating/updating ServiceNow password secret...")
        create_secret_if_not_exists(project_id, "servicenow-password", servicenow_password)
        
        # Get the service account and grant access
        try:
            service_account_email = get_service_account_email(project_id, location)
            logger.info(f"Granting secret access to service account: {service_account_email}")
            grant_secret_access(project_id, service_account_email, "servicenow-password")
        except Exception as e:
            logger.warning(f"Could not automatically grant secret access: {e}")
            logger.info("You may need to manually grant the service account access to the secret")
    
    # Get configurations
    requirements = get_package_requirements()
    extra_packages = get_extra_packages()
    env_vars = get_environment_variables()
    
    # Set display name and description
    if not display_name:
        display_name = os.getenv("AGENT_NAME", "ServiceNow Agent")
    
    if not description:
        description = os.getenv(
            "AGENT_DESCRIPTION",
            "AI agent for managing ServiceNow records through natural language. "
            "Supports creating, reading, updating, and deleting records in ServiceNow tables."
        )
    
    logger.info(f"Deploying agent '{display_name}' to project '{project_id}' in location '{location}'")
    logger.info(f"Requirements: {requirements}")
    logger.info(f"Extra packages: {extra_packages}")
    logger.info(f"Environment variables: {list(env_vars.keys())}")
    
    from vertexai.preview import reasoning_engines

    app = reasoning_engines.AdkApp(
        agent=create_servicenow_agent(),
        enable_tracing=True,
    )

    try:
        # Deploy the agent
        
        remote_agent = agent_engines.create(
            agent_engine=app,
            requirements=requirements,
        )
        
        logger.info("Agent deployed successfully!")
        logger.info(f"Resource name: {remote_agent.resource_name}")
        
        # Extract resource ID from resource name
        resource_id = remote_agent.resource_name.split('/')[-1]
        logger.info(f"Resource ID: {resource_id}")
        
        return remote_agent
        
    except Exception as e:
        logger.error(f"Failed to deploy agent: {e}")
        raise


def main():
    """Main function to handle command line arguments and deploy the agent"""
    parser = argparse.ArgumentParser(
        description="Deploy ServiceNow Agent to Vertex AI Agent Engine"
    )
    
    parser.add_argument(
        "--project-id",
        help="Google Cloud project ID (defaults to GOOGLE_CLOUD_PROJECT env var)",
        default=os.getenv("GOOGLE_CLOUD_PROJECT")
    )
    
    parser.add_argument(
        "--location",
        help="Google Cloud location/region (defaults to GOOGLE_CLOUD_LOCATION env var)",
        default=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    )
    
    parser.add_argument(
        "--staging-bucket",
        help="Cloud Storage bucket for staging artifacts (optional)",
        default=None
    )
    
    parser.add_argument(
        "--display-name",
        help="Display name for the agent (defaults to AGENT_NAME env var)",
        default=None
    )
    
    parser.add_argument(
        "--description",
        help="Description for the agent (defaults to AGENT_DESCRIPTION env var)",
        default=None
    )
    
    parser.add_argument(
        "--gcs-dir-name",
        help="Cloud Storage directory name for staging (optional, auto-generated if not provided)",
        default=None
    )
    
    parser.add_argument(
        "--env-file",
        help="Path to .env file (defaults to .env in current directory)",
        default=None
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_environment_variables(args.env_file)
    
    # Validate project ID
    if not args.project_id:
        logger.error("Project ID is required. Set GOOGLE_CLOUD_PROJECT or use --project-id")
        sys.exit(1)
    
    # Deploy the agent
    try:
        remote_agent = deploy_agent(
            project_id=args.project_id,
            location=args.location,
            staging_bucket=args.staging_bucket,
            display_name=args.display_name,
            description=args.description,
            gcs_dir_name=args.gcs_dir_name
        )
        
        print("\n" + "="*60)
        print("DEPLOYMENT SUCCESSFUL!")
        print("="*60)
        print(f"Agent Name: {args.display_name or os.getenv('AGENT_NAME', 'ServiceNow Agent')}")
        print(f"Project: {args.project_id}")
        print(f"Location: {args.location}")
        print(f"Resource Name: {remote_agent.resource_name}")
        print("\nSecret Manager Configuration:")
        print("- ServiceNow password stored in Secret Manager: servicenow-password")
        print("- IAM permissions automatically granted to the agent service account")
        print("\nNext steps:")
        print("1. Test the agent using the Vertex AI console or API")
        print("2. Monitor the agent's performance and logs")
        print("3. The agent will automatically fetch the password from Secret Manager")
        print("="*60)
        
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
