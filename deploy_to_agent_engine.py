#!/usr/bin/env python3
"""
Deploy ServiceNow Agent to Vertex AI Agent Engine

This script deploys the snow_agent to Google Cloud's Vertex AI Agent Engine.
It is the first step in the deployment process and will output the reasoning engine URI.
"""

import os
import sys
import logging
import argparse
from typing import Optional, Dict, List, Any
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

# CRITICAL: Load environment variables BEFORE importing the agent
# This ensures the agent has access to all required environment variables during creation
from dotenv import load_dotenv
load_dotenv("snow_agent/.env")

from google.cloud import aiplatform
import vertexai
from vertexai import agent_engines
from snow_agent.agent import root_agent  # Import root_agent - now with env vars loaded
import copy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Store environment variables globally
_env_vars = {}


def get_environment_variables(env_file: Optional[str] = None) -> Dict[str, str]:
    """Load and return environment variables from .env file"""
    global _env_vars
    
    if not _env_vars:
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv("snow_agent/.env")
        
        # List of environment variables to pass to the deployed agent
        env_var_keys = [
            # Critical for OAuth
            "AUTH_ID",
            
            # ServiceNow Configuration
            "SERVICENOW_INSTANCE_URL",
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
        ]
        
        for key in env_var_keys:
            if value := os.environ.get(key):
                _env_vars[key] = value
        
        logger.info(f"Loaded environment variables: {list(_env_vars.keys())}")
    
    return _env_vars


def load_environment_variables(env_file: Optional[str] = None) -> None:
    """Load environment variables and validate required ones"""
    get_environment_variables(env_file)
    
    required_vars = [
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
        "AUTH_ID",  # Critical for OAuth
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)


def get_package_requirements() -> str:
    """Define the package requirements for deployment"""
    return "deploy_requirements.txt"


def get_extra_packages() -> List[str]:
    """Define additional local packages to include"""
    return ["snow_agent"]


def deploy_agent(
    project_id: str,
    location: str,
    staging_bucket: Optional[str] = None,
    display_name: Optional[str] = None,
) -> Any:
    """Deploy the agent to Vertex AI Agent Engine"""
    if not staging_bucket:
        staging_bucket = f"gs://{project_id}-agent-staging"
    
    aiplatform.init(project=project_id, location=location, staging_bucket=staging_bucket)
    vertexai.init(project=project_id, location=location, staging_bucket=staging_bucket)
    
    requirements = get_package_requirements()
    extra_packages = get_extra_packages()
    
    if not display_name:
        display_name = os.getenv("AGENT_DISPLAY_NAME", os.getenv("AGENT_NAME", "ServiceNow Agent"))
    
    logger.info(f"Deploying agent '{display_name}' to project '{project_id}' in location '{location}'")
    
    from vertexai.preview import reasoning_engines

    # Get all environment variables
    env_vars = get_environment_variables()
    
    # Use the root_agent directly, following the working example pattern
    app = reasoning_engines.AdkApp(
        agent=root_agent,  # Use the imported root_agent
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

    # Deploy with proper parameters based on the working example
    remote_agent = agent_engines.create(
        agent_engine=app,  # Use agent_engine parameter name
        requirements=requirements,
        extra_packages=extra_packages,
        env_vars=deployment_env_vars,  # Pass filtered env vars
        display_name=display_name,
        description=os.getenv("AGENT_DESCRIPTION", "AI agent for managing ServiceNow records through natural language"),
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
        logger.error("Project ID is required.")
        sys.exit(1)
    
    try:
        remote_agent = deploy_agent(
            project_id=args.project_id,
            location=args.location,
            staging_bucket=args.staging_bucket,
            display_name=args.display_name,
        )
        # Print the resource name to stdout so it can be captured
        print(remote_agent.resource_name)
        
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
