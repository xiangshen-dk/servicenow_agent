# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
from typing import Optional

from google.adk import Agent

from .settings import ServiceNowSettings, AgentSettings
from .servicenow_tool import create_servicenow_tool
from .prompts import GLOBAL_INSTRUCTION, INSTRUCTION
from .logging_config import setup_logging

# Setup logging
setup_logging()

logger = logging.getLogger(__name__)

# Log all environment variables at startup for debugging
logger.info("=== Environment Variables at Agent Startup ===")
env_vars = {k: v for k, v in os.environ.items() if k.startswith(('SERVICENOW_', 'AGENT_', 'AUTH_', 'GOOGLE_'))}
for key, value in sorted(env_vars.items()):
    # Mask sensitive values
    if 'SECRET' in key or 'TOKEN' in key:
        masked_value = value[:4] + '...' + value[-4:] if len(value) > 8 else '***'
        logger.info(f"  {key}: {masked_value}")
    else:
        logger.info(f"  {key}: {value}")
logger.info("=== End Environment Variables ===")


def create_servicenow_agent(
    servicenow_settings: Optional[ServiceNowSettings] = None,
    agent_settings: Optional[AgentSettings] = None
) -> Agent:
    """Create and configure the ServiceNow agent with NLP capabilities."""
    
    if not servicenow_settings:
        servicenow_settings = ServiceNowSettings()
    if not agent_settings:
        agent_settings = AgentSettings()
    
    servicenow_tool = create_servicenow_tool(servicenow_settings)
    
    try:
        agent = Agent(
            name=agent_settings.agent_name,
            model=agent_settings.model,
            description=f"{agent_settings.agent_description} (Version: {agent_settings.agent_version})",
            global_instruction=GLOBAL_INSTRUCTION,
            instruction=INSTRUCTION,
            tools=[servicenow_tool]
        )
        
        logger.info(f"ServiceNow agent created successfully with model: {agent_settings.model}")
        return agent
        
    except Exception as e:
        logger.error(f"Failed to create ServiceNow agent: {e}")
        raise RuntimeError(f"Failed to create agent: {str(e)}")


# Create root_agent for Google ADK framework compatibility
try:
    # Try to create settings objects separately to identify which one fails
    logger.info("Attempting to create ServiceNowSettings...")
    try:
        servicenow_settings = ServiceNowSettings()
        logger.info(f"ServiceNowSettings created successfully with instance_url: {servicenow_settings.instance_url}")
    except Exception as sn_error:
        logger.error(f"Failed to create ServiceNowSettings: {sn_error}")
        logger.error(f"Required SERVICENOW_INSTANCE_URL env var present: {'SERVICENOW_INSTANCE_URL' in os.environ}")
        if 'SERVICENOW_INSTANCE_URL' in os.environ:
            logger.error(f"SERVICENOW_INSTANCE_URL value: {os.environ['SERVICENOW_INSTANCE_URL']}")
        raise
    
    logger.info("Attempting to create AgentSettings...")
    try:
        agent_settings = AgentSettings()
        logger.info(f"AgentSettings created successfully with version: {agent_settings.agent_version}")
    except Exception as ag_error:
        logger.error(f"Failed to create AgentSettings: {ag_error}")
        raise
    
    # Now create the agent with both settings
    root_agent = create_servicenow_agent(servicenow_settings, agent_settings)
    logger.info("Root agent created successfully for Google ADK framework")
    
except Exception as e:
    logger.error(f"Failed to create configured agent: {type(e).__name__}: {str(e)}")
    logger.warning("Creating minimal fallback agent due to missing configuration")
    
    # Create a more informative fallback agent
    try:
        agent_settings = AgentSettings()
        model = agent_settings.model
        version = agent_settings.agent_version
    except:
        model = "gemini-2.5-flash"
        version = "unknown"
    
    # Provide detailed error information in the fallback agent
    error_details = f"Configuration error: {str(e)}"
    if 'SERVICENOW_INSTANCE_URL' not in os.environ:
        error_details = "Missing SERVICENOW_INSTANCE_URL environment variable"
    
    root_agent = Agent(
        name="ServiceNow_Agent_Unconfigured",
        model=model,
        description=f"ServiceNow agent awaiting configuration (v{version})",
        instruction=f"I am a ServiceNow agent but I'm not yet configured to interact with ServiceNow. {error_details}. Please ensure all required environment variables are set."
    )
