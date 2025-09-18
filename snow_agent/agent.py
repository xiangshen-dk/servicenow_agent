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
import sys
from typing import Optional

from google.adk import Agent

from .settings import ServiceNowSettings, AgentSettings
from .servicenow_tool import create_servicenow_tool
from .prompts import GLOBAL_INSTRUCTION, INSTRUCTION

# Configure logging to output to stdout with "ServiceNow Agent: " prefix
# This ensures logs appear in Cloud Logging when deployed to Agent Engine
# Set to DEBUG for detailed logging, or INFO for production
import os
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='ServiceNow Agent: %(levelname)s - %(name)s - %(message)s',
    stream=sys.stdout,
    force=True  # Force reconfiguration even if logging was already configured
)

# Reduce noise from HTTP libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def create_servicenow_agent(
    servicenow_settings: Optional[ServiceNowSettings] = None,
    agent_settings: Optional[AgentSettings] = None
) -> Agent:
    """Create and configure the ServiceNow agent with NLP capabilities."""
    
    # Load settings if not provided
    if not servicenow_settings:
        servicenow_settings = ServiceNowSettings()
    if not agent_settings:
        agent_settings = AgentSettings()
    
    # Create the ServiceNow tool
    servicenow_tool = create_servicenow_tool(servicenow_settings)
    
    # Create the agent
    try:
        agent = Agent(
            name=agent_settings.agent_name,
            model=agent_settings.model,
            description=agent_settings.agent_description,
            global_instruction=GLOBAL_INSTRUCTION,
            instruction=INSTRUCTION,
            tools=[servicenow_tool]
        )
        
        logger.info(f"ServiceNow agent created successfully with model: {agent_settings.model}")
        return agent
        
    except Exception as e:
        logger.error(f"Failed to create ServiceNow agent: {e}")
        raise RuntimeError(f"Failed to create agent: {str(e)}")


# Lazy initialization pattern for the root agent
_root_agent = None
_root_agent_error = None

def get_root_agent() -> Agent:
    """
    Get or create the singleton root agent instance.
    Uses lazy initialization to avoid import-time side effects.
    
    Returns:
        Agent: The configured ServiceNow agent
        
    Raises:
        RuntimeError: If agent creation fails
    """
    global _root_agent, _root_agent_error
    
    if _root_agent is not None:
        return _root_agent
    
    if _root_agent_error is not None:
        # Re-raise the cached error to avoid repeated initialization attempts
        raise _root_agent_error
    
    try:
        # Try to load settings from environment
        servicenow_settings = ServiceNowSettings()
        agent_settings = AgentSettings()
        _root_agent = create_servicenow_agent(servicenow_settings, agent_settings)
        logger.info("Root agent initialized successfully")
        return _root_agent
    except Exception as e:
        # Cache the error to avoid repeated failed attempts
        _root_agent_error = RuntimeError(f"Failed to initialize root agent: {str(e)}")
        logger.error(f"Could not create ServiceNow agent: {e}")
        
        # Create a basic fallback agent if needed
        try:
            agent_settings = AgentSettings()
            model = agent_settings.model
        except:
            model = "gemini-2.5-flash"
        
        _root_agent = Agent(
            name="ServiceNow_Agent_Unconfigured",
            model=model,
            description="ServiceNow agent awaiting configuration",
            instruction="I am a ServiceNow agent but I'm not yet configured. Please provide ServiceNow credentials and instance URL."
        )
        return _root_agent

# Create root_agent for Google ADK framework compatibility
# The framework requires a module-level 'root_agent' variable that is an Agent instance
# We need to create it at module level for the framework to find it
try:
    # Try to load settings from environment
    _servicenow_settings = ServiceNowSettings()
    _agent_settings = AgentSettings()
    root_agent = create_servicenow_agent(_servicenow_settings, _agent_settings)
    logger.info("Root agent created for Google ADK framework")
except Exception as e:
    # If configuration is missing, create a minimal agent
    # This allows the module to be imported and the framework to load
    logger.warning(f"Creating minimal agent due to missing configuration: {e}")
    try:
        _agent_settings = AgentSettings()
        model = _agent_settings.model
    except:
        model = "gemini-2.5-flash"
    
    root_agent = Agent(
        name="ServiceNow_Agent",
        model=model,
        description="ServiceNow agent awaiting configuration",
        instruction="I am a ServiceNow agent but I'm not yet configured. Please provide ServiceNow credentials and instance URL."
    )
