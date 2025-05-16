#!/usr/bin/env python
"""
Example script demonstrating the Agentic RAG system with Zero-Day Scout.

This script shows how to use the OrchestratorAgent to process security queries
through the multi-agent system.
"""

import os
import sys
import argparse
import asyncio
import logging
from dotenv import load_dotenv

# Add the project root to the path if running directly
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.scout_agent import OrchestratorAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("scout-agent-test")


async def process_security_query(query: str, model_name: str = "gemini-2.5-flash-preview-04-17"):
    """
    Process a security query through the agent system.
    
    Args:
        query: The security query to process
        model_name: The model to use for the agents
        
    Returns:
        The response from the agent system
    """
    # Initialize the orchestrator agent
    print(f"\n🔍 Initializing agent system with model: {model_name}")
    orchestrator = OrchestratorAgent(model_name=model_name)
    
    # Process the query
    print(f"\n🔄 Processing query: '{query}'")
    print("\n⏳ Running sequential agent workflow (planner -> researcher -> analyst)...\n")
    
    # Execute the query processing workflow
    response = await orchestrator.process_query(query)
    
    return response


async def main():
    """Run the agent system demo."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Test the Zero-Day Scout agent system")
    parser.add_argument("--query", "-q", type=str, 
                      default="What are the latest zero-day vulnerabilities in log4j?",
                      help="Security query to process")
    parser.add_argument("--model", "-m", type=str, 
                      default="gemini-2.5-flash-preview-04-17",
                      help="Model to use for the agents")
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Process the query
    print("\n===== Zero-Day Scout Agent System Demo =====")
    
    try:
        response = await process_security_query(args.query, args.model)
        
        # Display the result
        print("\n===== Agent System Response =====\n")
        print(response)
        print("\n======================================")
    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        print(traceback.format_exc())


if __name__ == "__main__":
    asyncio.run(main())