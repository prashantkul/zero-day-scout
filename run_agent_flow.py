
import asyncio
import logging
import json
import os
import sys

# Add project root to sys.path to allow direct imports
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from src.scout_agent.agent import OrchestratorAgent
except ImportError:
    print("Error: Could not import OrchestratorAgent. ")
    print("Ensure the script is in the project root and src/scout_agent/agent.py exists.")
    sys.exit(1)

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)] # Ensure logs go to stdout
)
# You can set more verbose logging for ADK components if needed:
# logging.getLogger("google.adk").setLevel(logging.DEBUG)
# logging.getLogger("mcp").setLevel(logging.DEBUG)

async def main():
    """
    Runs the Zero-Day Scout agentic flow with a sample query.
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting simple agent flow client...")

    # --- Configuration ---
    # Set to True to use MCP for CVE lookups (requires streamable_server.py to be running)
    # Set to False to disable MCP and rely on RAG/web search only for CVEs.
    USE_MCP_FOR_CVE = True

    # Sample query - modify as needed
    # query = "What are the latest vulnerabilities in Apache Struts?"
    query = "Tell me about the security implications of CVE-2021-44228 (Log4Shell). Make sure to get detailed information about this vulnerability."
    # query = "Are there any known RCE vulnerabilities in Microsoft Exchange Server from the last 6 months?"

    logger.info(f"Initializing OrchestratorAgent (MCP for CVE: {USE_MCP_FOR_CVE})...")
    orchestrator = None
    try:
        orchestrator = OrchestratorAgent(use_mcp=USE_MCP_FOR_CVE)

        logger.info(f'Processing query: "{query}"')
        # Set a timeout (e.g., 300 seconds = 5 minutes)
        timeout_seconds = 300.0
        result = await orchestrator.process_query(query, timeout=timeout_seconds)

        logger.info("Query processing completed.")

        print("\n" + "="*30 + " FINAL RESPONSE " + "="*30)
        if result.get("final_response"):
            print(result["final_response"])
        else:
            print("No final response received.")
        print("="*76 + "\n")

        print("="*30 + " AGENT OUTPUTS " + "="*30)
        if result.get("agent_outputs"):
            print(json.dumps(result["agent_outputs"], indent=2))
        else:
            print("No agent outputs available.")
        print("="*76 + "\n")

    except Exception as e:
        logger.error(f"An error occurred during the agent flow: {e}", exc_info=True)
    finally:
        if orchestrator:
            logger.info("Cleaning up orchestrator resources...")
            await orchestrator.cleanup_resources()
            logger.info("Orchestrator resources cleaned up.")

if __name__ == "__main__":
    # Ensure the script can find other project modules if run directly
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    # Add src to sys.path as well, if not already present due to being in root
    src_path = os.path.join(current_dir, "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    asyncio.run(main())
