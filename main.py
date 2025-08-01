import os
import logging
from pathlib import Path
import uuid
import asyncio

from dotenv import load_dotenv
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from snow_agent.agent import root_agent
from snow_agent.utils.logging import setup_logging


async def main():
    """Main entry point for the ServiceNow agent."""
    # Load environment variables
    env_file = Path("snow_agent/.env")
    if env_file.exists():
        load_dotenv(env_file)
        print(f"Loaded environment from {env_file}")
    else:
        print("No .env file found. Using environment variables.")
    
    # Setup logging
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_file = os.getenv("LOG_FILE")
    setup_logging(level=log_level, log_file=log_file)
    
    logger = logging.getLogger(__name__)
    logger.info("Starting ServiceNow Agent...")
    
    # Check if we have ServiceNow credentials
    if not os.getenv("SERVICENOW_INSTANCE_URL"):
        logger.warning(
            "SERVICENOW_INSTANCE_URL not set. Agent will run in limited mode. "
            "Please set up your .env file based on .env.example"
        )
    
    # Start the agent
    try:
        # Create a session service
        session_service = InMemorySessionService()
        
        # Create and start the runner
        runner = Runner(
            app_name="servicenow_agent",
            agent=root_agent,
            session_service=session_service
        )
        # For a simple CLI interface, we can use a basic interaction loop
        print("\nServiceNow Agent is ready! Type your requests or 'quit' to exit.\n")
        
        # Create a session for the conversation
        user_id = "cli_user"
        session_id = str(uuid.uuid4())
        
        # Create the session in the session service
        await session_service.create_session(
            app_name="servicenow_agent",
            user_id=user_id,
            session_id=session_id
        )
        
        while True:
            try:
                user_input = input("You: ")
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                
                # Create a content message with the user's actual input
                message = types.Content(
                    parts=[types.Part(text=user_input)],
                    role="user"
                )
                
                # Run the agent with the user input
                response_parts = []
                async for event in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=message
                ):
                    # Debug: print event type
                    logger.debug(f"Event type: {type(event).__name__}, Event: {event}")
                    
                    # Check if event has content with parts
                    if hasattr(event, 'content') and event.content:
                        if hasattr(event.content, 'parts'):
                            for part in event.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    response_parts.append(part.text)
                        else:
                            response_parts.append(str(event.content))
                    elif hasattr(event, 'text') and event.text:
                        response_parts.append(event.text)
                    elif hasattr(event, 'message') and event.message:
                        response_parts.append(str(event.message))
                
                if response_parts:
                    print(f"\nAgent: {''.join(response_parts)}\n")
                else:
                    print("\nAgent: [No response]\n")
                
            except EOFError:
                break
            except Exception as e:
                logger.error(f"Error processing request: {e}")
                print(f"\nError: {e}\n")
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
