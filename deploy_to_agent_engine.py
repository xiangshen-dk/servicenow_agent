#!/usr/bin/env python3
"""
Deploy ServiceNow Agent to Vertex AI Agent Engine

This script deploys the snow_agent to Google Cloud's Vertex AI Agent Engine.
It handles configuration, packaging, and deployment with password-based authentication.
"""

import os
import sys
import logging
import argparse
from typing import Optional, Dict, List, Any
from pathlib import Path

# Add the current directory to Python path to import snow_agent
sys.path.insert(0, str(Path(__file__).parent))

from google.cloud import aiplatform
import vertexai
from vertexai import agent_engines
from snow_agent.agent import create_servicenow_agent
from dotenv import load_dotenv
import copy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Store environment variables globally
_env_vars = {}


def clean_env_value(value: str) -> str:
    """Clean environment variable value by removing quotes and variable references"""
    if not value:
        return value
    
    original_value = value
    
    # Strip outer quotes if present
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    
    # Remove any ${VAR} references but keep the rest of the text
    import re
    # This regex removes ${...} patterns
    value = re.sub(r'\$\{[^}]+\}', '', value)
    
    # Clean up any double spaces or trailing/leading spaces
    # But preserve single spaces between words
    value = ' '.join(value.split())
    
    logger.debug(f"clean_env_value: '{original_value}' -> '{value}'")
    
    return value.strip()


def get_environment_variables(env_file: Optional[str] = None) -> Dict[str, str]:
    """Load and return environment variables from .env file"""
    global _env_vars
    
    if not _env_vars:
        if env_file:
            load_dotenv(env_file)
        else:
            # Load from snow_agent/.env
            env_path = Path(__file__).parent / "snow_agent" / ".env"
            load_dotenv(env_path)
        
        # List of environment variables to pass to the deployed agent
        env_var_keys = [
            # ServiceNow Configuration
            "SERVICENOW_INSTANCE_URL",
            "SERVICENOW_USERNAME",
            "SERVICENOW_ALLOWED_TABLES",
            "SERVICENOW_API_TIMEOUT",
            "SERVICENOW_MAX_RECORDS",
            
            # Agent Configuration
            "AGENT_NAME",
            "AGENT_DISPLAY_NAME",
            "AGENT_DESCRIPTION",
            "AGENT_MODEL",
            "AGENT_VERSION",
            
            # Google Cloud Configuration (for reference)
            "GOOGLE_CLOUD_PROJECT",
            "GOOGLE_CLOUD_LOCATION",
            "GOOGLE_GENAI_USE_VERTEXAI",
            
            # Logging configuration
            "ENVIRONMENT",
            "LOG_LEVEL",
        ]
        
        for key in env_var_keys:
            if value := os.environ.get(key):
                # For AGENT_NAME and AGENT_DESCRIPTION, be more careful with cleaning
                if key in ["AGENT_NAME", "AGENT_DESCRIPTION"]:
                    # Only clean if there are quotes or variable references
                    if '"' in value or "'" in value or "${" in value:
                        _env_vars[key] = clean_env_value(value)
                    else:
                        # Keep the value as-is, just strip whitespace
                        _env_vars[key] = value.strip()
                else:
                    # Clean other values normally
                    _env_vars[key] = clean_env_value(value)
        
        # Set production environment for proper logging
        _env_vars["ENVIRONMENT"] = "production"
        _env_vars["LOG_LEVEL"] = os.environ.get("LOG_LEVEL", "INFO")
        _env_vars["GOOGLE_GENAI_USE_VERTEXAI"] = "1"
        
        logger.info(f"Loaded environment variables: {list(_env_vars.keys())}")
    
    return _env_vars


def load_environment_variables(env_file: Optional[str] = None) -> None:
    """Load environment variables and validate required ones"""
    get_environment_variables(env_file)
    
    required_vars = [
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
        "SERVICENOW_INSTANCE_URL",
        "SERVICENOW_USERNAME",
        "SERVICENOW_PASSWORD",  # Required for Secret Manager setup
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)


def get_package_requirements() -> str:
    """Define the package requirements for deployment"""
    # Use the requirements file from snow_agent directory
    return str(Path(__file__).parent / "snow_agent" / "requirements.txt")


def get_extra_packages() -> List[str]:
    """Define additional local packages to include"""
    # Return the package name - this works when script is in root directory
    return ["snow_agent"]


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


def deploy_agent(
    project_id: str,
    location: str,
    staging_bucket: Optional[str] = None,
    display_name: Optional[str] = None,
) -> Any:
    """Deploy the agent to Vertex AI Agent Engine"""
    
    if not staging_bucket:
        staging_bucket = f"gs://{project_id}-agent-staging"
    
    # Initialize Vertex AI
    aiplatform.init(project=project_id, location=location, staging_bucket=staging_bucket)
    vertexai.init(project=project_id, location=location, staging_bucket=staging_bucket)
    
    # Grant IAM permissions for the secret (secret is created by deploy.sh)
    # We still need to grant the service account access to read the secret
    try:
        service_account_email = get_service_account_email(project_id, location)
        logger.info(f"Granting secret access to service account: {service_account_email}")
        grant_secret_access(project_id, service_account_email, "servicenow-password-prod")
    except Exception as e:
        logger.warning(f"Could not automatically grant secret access: {e}")
        logger.info("You may need to manually grant the service account access to the secret")
    
    # Get configurations
    requirements = get_package_requirements()
    extra_packages = get_extra_packages()
    
    # Construct display name if not provided
    if not display_name:
        # Get values directly from environment
        display_name = os.getenv("AGENT_NAME", "ServiceNow Agent")
        
        # Strip quotes if present (since shell script preserves them)
        display_name = display_name.strip('"').strip("'")
        
        logger.info(f"AGENT_NAME from env: '{display_name}'")
    
    # Get description and append version
    description = os.getenv("AGENT_DESCRIPTION", 
                           "AI agent for managing ServiceNow records through natural language")
    
    # Strip quotes if present
    description = description.strip('"').strip("'")
    
    agent_version = os.getenv("AGENT_VERSION", "")
    agent_version = agent_version.strip('"').strip("'")
    
    # Append version to description if available
    if agent_version:
        description = f"{description} [Version: {agent_version}]"
    
    logger.info(f"AGENT_VERSION from env: '{agent_version}'")
    
    # Log the final values for verification
    logger.info(f"Final display_name: '{display_name}' (length: {len(display_name)} chars)")
    logger.info(f"Final description: '{description}' (length: {len(description)} chars)")
    
    logger.info(f"Deploying agent '{display_name}' to project '{project_id}' in location '{location}'")
    
    from vertexai.preview import reasoning_engines
    
    # Get all environment variables
    env_vars = get_environment_variables()
    
    # Create the agent using create_servicenow_agent function
    app = reasoning_engines.AdkApp(
        agent=create_servicenow_agent(),  # Use the function that creates the agent
        enable_tracing=True,
        env_vars=env_vars,  # Pass all env vars to AdkApp
    )
    
    # CRUCIAL: Call set_up() before deployment to prepare the app
    app.set_up()
    
    # Create a copy of env_vars and remove special variables for deployment
    deployment_env_vars = copy.deepcopy(env_vars)
    # Remove these as they're set by the runtime
    deployment_env_vars.pop("GOOGLE_CLOUD_PROJECT", None)
    deployment_env_vars.pop("GOOGLE_CLOUD_LOCATION", None)
    deployment_env_vars.pop("GOOGLE_GENAI_USE_VERTEXAI", None)
    # Add Secret Manager reference for password
    deployment_env_vars["SERVICENOW_PASSWORD"] = {
        "secret": "servicenow-password-prod",
        "version": "latest"
    }
    
    # Deploy with proper parameters - matching oauth branch approach
    remote_agent = agent_engines.create(
        agent_engine=app,  # Use agent_engine parameter name
        requirements=requirements,
        extra_packages=extra_packages,
        env_vars=deployment_env_vars,  # Pass filtered env vars
        display_name=display_name,  # Pass the display name directly
        description=description,  # Pass the description directly
    )
    
    return remote_agent


def main():
    """Main function to handle command line arguments and deploy the agent"""
    parser = argparse.ArgumentParser(description="Deploy ServiceNow Agent to Vertex AI Agent Engine")
    parser.add_argument("--project-id", default=os.getenv("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument("--location", default=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"))
    parser.add_argument("--staging-bucket", default=None)
    parser.add_argument("--display-name", default=None)
    parser.add_argument("--env-file", default=None)
    args = parser.parse_args()
    
    load_environment_variables(args.env_file)
    
    if not args.project_id:
        logger.error("Project ID is required. Set GOOGLE_CLOUD_PROJECT or use --project-id")
        sys.exit(1)
    
    try:
        remote_agent = deploy_agent(
            project_id=args.project_id,
            location=args.location,
            staging_bucket=args.staging_bucket,
            display_name=args.display_name,
        )
        
        # Print only the resource name to stdout for the shell script to capture
        print(remote_agent.resource_name)
        
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
