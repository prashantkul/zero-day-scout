#!/usr/bin/env python
"""
Test script for the sequential agent workflow in Zero-Day Scout.

This script tests the complete sequential workflow from planner to researcher to analyst.
"""

import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# Add the project root to the path if running directly
if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.scout_agent.agent import OrchestratorAgent

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("sequential-agent-test")


async def test_sequential_workflow():
    """Test the complete sequential agent workflow."""
    # Initialize the agent
    print("\n🔄 Initializing the Orchestrator Agent...")
    agent = OrchestratorAgent(model_name="gemini-2.5-flash-preview-04-17")
    
    # Test query
    query = "What are the latest zero-day vulnerabilities in web browsers?"
    print(f"\n🔍 Testing with query: '{query}'")
    
    # Process the query
    print("\n⏳ Starting sequential workflow execution...")
    print("\n--- This should execute: Planner -> Researcher -> Analyst ---\n")
    
    try:
        # Execute the query
        response = await agent.process_query(query)
        
        # Print the result
        print("\n✅ Sequential workflow execution completed!")
        print("\n--- Final Response ---")
        print(response)
        print("\n--- End of Response ---")
        
    except Exception as e:
        print(f"\n❌ Error in sequential workflow: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    print("\n===== Testing Sequential Agent Workflow =====")
    asyncio.run(test_sequential_workflow())
    print("\n===== Test Completed =====")