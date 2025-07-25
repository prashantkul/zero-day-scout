#!/usr/bin/env python
"""
Runner script for the Zero-Day Scout Agentic RAG system.

This module provides a command-line interface to run the agent system.
"""

import os
import sys
import argparse
import asyncio
import logging
import uuid
from datetime import datetime
from dotenv import load_dotenv

# Add the project root to the path if running directly
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from src.scout_agent.agent import OrchestratorAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("scout-agent-runner")


class ScoutAgentRunner:
    """
    Runner for the Zero-Day Scout agent system.
    
    This class handles initialization and execution of the agent
    for security vulnerability research using InMemoryRunner.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        """
        Initialize the Scout Agent runner.
        
        Args:
            model_name: The model to use for the agent
        """
        self.model_name = model_name

        # Initialize the orchestrator agent
        self.orchestrator = OrchestratorAgent(model_name=self.model_name)

        # App name for this application
        self.app_name = "scout_agent"

        # Create a session service for conversation state management
        self.session_service = InMemorySessionService()

        # Create the Runner for the agent
        self.runner = Runner(
            agent=self.orchestrator.root_agent,
            app_name=self.app_name,
            session_service=self.session_service
        )

        logger.info(f"Initialized Scout Agent Runner with model: {model_name}")

    def create_session(self, user_id: str = None, session_id: str = None):
        """
        Create a new session or return an existing one.
        
        Args:
            user_id: User identifier (generated if not provided)
            session_id: Session identifier (generated if not provided)
            
        Returns:
            The session object
        """
        # Generate IDs if not provided
        user_id = user_id or f"user_{uuid.uuid4().hex[:8]}"
        session_id = session_id or f"session_{uuid.uuid4().hex[:8]}"

        # Create or get the session
        session = self.session_service.create_session(
            app_name=self.app_name,
            user_id=user_id,
            session_id=session_id
        )

        logger.info(f"Created session: user={user_id}, session={session_id}")
        return session

    async def process_query(self, query: str, user_id: str = None, session_id: str = None):
        """
        Process a security query with the agent.
        
        Args:
            query: The security query to process
            user_id: User identifier (generated if not provided)
            session_id: Session identifier (generated if not provided)
            
        Returns:
            The agent's response
        """
        # Create a session if user_id or session_id not provided
        if not user_id or not session_id:
            session = self.create_session(user_id, session_id)
            user_id = session.user_id
            session_id = session.id

        logger.info(f"Processing query for user={user_id}, session={session_id}")

        # Delegate directly to the OrchestratorAgent for sequential processing
        response = await self.orchestrator.process_query(query)

        return response


async def interactive_mode(runner: ScoutAgentRunner, verbose: bool = False):
    """
    Run the agent in interactive mode.
    
    Args:
        runner: ScoutAgentRunner instance
        verbose: Whether to show detailed agent workflow information
    """
    print("\n===== Zero-Day Scout Agent Interactive Mode =====")
    print("Type your security queries and get responses from the agent.")
    print("Type 'exit' or 'quit' to end the session.\n")
    
    # Create a session for this interactive session
    session = runner.create_session()
    user_id = session.user_id
    session_id = session.id
    
    print(f"Session Info:")
    print(f"  User ID: {user_id}")
    print(f"  Session ID: {session_id}")
    print(f"  Model: {runner.model_name}")
    if verbose:
        print(f"  Verbose mode: Enabled (showing detailed agent workflow)")
    print()
    
    while True:
        # Get the user's query
        try:
            query = input("\n>>> ")
        except EOFError:
            break
        
        # Check for exit command
        if query.lower() in ["exit", "quit", "bye", "q"]:
            print("Exiting interactive mode.")
            break
        
        if not query.strip():
            continue
        
        try:
            # Process the query using call_agent_async
            await call_agent_async(query, runner.runner, user_id, session_id, verbose=verbose)
        except Exception as e:
            print(f"\nError: {str(e)}")


async def call_agent_async(query: str, runner, user_id, session_id, verbose=False):
    """
    Sends a query to the agent and prints the final response.
    
    Args:
        query: The user's query
        runner: The Runner instance
        user_id: User identifier
        session_id: Session identifier
        verbose: Whether to print all events
    
    Returns:
        The final response text
    """
    print(f"\n>>> User Query: {query}")

    # Prepare the user's message in ADK format
    content = types.Content(role='user', parts=[types.Part(text=query)])

    final_response_text = "Agent did not produce a final response." # Default
    
    # Track subagent outputs for debugging
    subagent_outputs = {}
    last_agent = None

    # Key Concept: run_async executes the agent logic and yields Events.
    # We iterate through events to monitor the execution flow.
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        # Log all events in verbose mode
        if verbose:
            event_type = type(event).__name__
            is_final = event.is_final_response()
            print(f"  [Event] Author: {event.author}, Type: {event_type}, Final: {is_final}")
            
            # Show content for MessageEvent
            if hasattr(event, 'content') and event.content and event.content.parts:
                print(f"  Content preview: {event.content.parts[0].text[:100]}...")
        
        # Track subagent outputs for agent workflow visualization
        if event.author and event.author != last_agent:
            last_agent = event.author
            print(f"\n[Agent: {event.author}] Working on the query...")
            
        # If we have an intermediate agent output, save it
        if hasattr(event, 'content') and event.content and event.content.parts and not event.is_final_response():
            if event.author:
                subagent_outputs[event.author] = event.content.parts[0].text
                
        # Key Concept: is_final_response() marks the concluding message for the turn.
        if event.is_final_response():
            if event.content and event.content.parts:
                # Assuming text response in the first part
                final_response_text = event.content.parts[0].text
            elif event.actions and event.actions.escalate: # Handle potential errors/escalations
                final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
            # Add more checks here if needed (e.g., specific error codes)
            break # Stop processing events once the final response is found

    # Print the agent flow for debugging
    if verbose and subagent_outputs:
        print("\n===== Agent Workflow Summary =====")
        for agent_name, output in subagent_outputs.items():
            print(f"\nAgent '{agent_name}' output preview:")
            print(f"{output[:200]}...\n")
            
    print(f"<<< Final Response: {final_response_text}")
    return final_response_text


async def run_conversation(runner, user_id, session_id, queries, verbose=False):
    """
    Run a sequence of queries in a conversation.
    
    Args:
        runner: The agent runner
        user_id: User identifier
        session_id: Session identifier
        queries: List of queries to process
        verbose: Whether to show detailed agent workflow information
    """
    print("\n===== Starting Conversation =====")
    
    for i, query in enumerate(queries):
        print(f"\n----- Query {i+1}/{len(queries)} -----")
        await call_agent_async(query, runner, user_id, session_id, verbose=verbose)
    
    print("\n===== Conversation Complete =====")


async def main():
    """Run the agent system."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run the Zero-Day Scout agent system")
    parser.add_argument("--query", "-q", type=str, default=None,
                      help="Security query to process (if not provided, runs in interactive mode)")
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default="gemini-2.5-flash",
        help="Model to use for the agent",
    )
    parser.add_argument("--user", "-u", type=str, default=None,
                      help="User ID (generated if not provided)")
    parser.add_argument("--session", "-s", type=str, default=None,
                      help="Session ID (generated if not provided)")
    parser.add_argument("--script", action="store_true",
                      help="Run a sample script of queries")
    parser.add_argument("--verbose", "-v", action="store_true",
                      help="Show detailed agent workflow information")
    parser.add_argument("--debug", "-d", action="store_true",
                      help="Enable debug logging")
    args = parser.parse_args()

    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    # Load environment variables
    load_dotenv()

    try:
        # Initialize the runner
        runner = ScoutAgentRunner(model_name=args.model)

        # Create a session if needed
        session = runner.create_session(args.user, args.session)
        user_id = session.user_id
        session_id = session.id

        if args.query:
            # Process a single query
            response = await call_agent_async(
                args.query, runner.runner, user_id, session_id, verbose=args.verbose
            )

        elif args.script:
            # Run a sample script of queries
            sample_queries = [
                "What are the most common zero-day vulnerabilities in web applications?",
                "How can organizations protect against these vulnerabilities?",
                "Tell me about the Log4Shell vulnerability in detail"
            ]
            await run_conversation(runner.runner, user_id, session_id, sample_queries, verbose=args.verbose)

        else:
            # Run in interactive mode
            await interactive_mode(runner, verbose=args.verbose)

    except Exception as e:
        print(f"\nError: {str(e)}")
        if args.debug:
            import traceback
            print(traceback.format_exc())
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
