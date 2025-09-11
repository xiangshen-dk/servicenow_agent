# Copyright 2022 Google LLC
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
from typing import Optional

from google.adk import Agent

from .settings import ServiceNowSettings, AgentSettings
from .servicenow_tool import create_servicenow_tool
from .prompts import GLOBAL_INSTRUCTION, INSTRUCTION


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


# Create a default agent instance
try:
    # Try to load settings from environment
    servicenow_settings = ServiceNowSettings()
    agent_settings = AgentSettings()
    root_agent = create_servicenow_agent(servicenow_settings, agent_settings)
except Exception as e:
    # Create a basic agent without ServiceNow integration if settings are missing
    import traceback
    logger.warning(f"Could not create ServiceNow agent with full configuration: {e}")
    logger.debug(f"Full traceback: {traceback.format_exc()}")
    # Still try to load agent settings for the model configuration
    try:
        agent_settings = AgentSettings()
        model = agent_settings.model
    except:
        # If even agent settings fail, use the default
        model = "gemini-2.5-flash"
    
    root_agent = Agent(
        name="ServiceNow_Agent_Unconfigured",
        model=model,
        description="ServiceNow agent awaiting configuration",
        instruction="I am a ServiceNow agent but I'm not yet configured. Please provide ServiceNow credentials and instance URL."
    )
