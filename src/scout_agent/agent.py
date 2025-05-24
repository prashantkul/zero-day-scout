\
"""
Agent classes for the Zero-Day Scout Agentic RAG system.

This module implements the core agents using Google ADK:
- OrchestratorAgent: Main sequential agent that orchestrates the workflow
- ResearchAgent: Specialized LLMAgent for RAG-based information retrieval
- AnalysisAgent: LLMAgent that evaluates information for security insights
"""

from typing import Dict, List, Any, Optional, Tuple
import json
import logging
import os
import asyncio

from google.adk.agents import Agent, LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool
from google.adk.runners import Runner, InMemoryRunner
from google.genai.types import Part, UserContent
from google.adk.sessions import InMemorySessionService
from google.genai import types
from vertexai.generative_models import GenerationConfig

from src.rag.pipeline import VertexRagPipeline
from src.scout_agent.tools import RagQueryTool, VulnerabilityAnalysisTool
from src.scout_agent.web_search_tool import WebSearchTool
from src.scout_agent.cve_agent import CveLookupAgent
from src.scout_agent.prompts import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    RESEARCH_SYSTEM_PROMPT,
    ANALYSIS_SYSTEM_PROMPT,
    PLAN_CREATION_PROMPT,
    RESEARCH_TASK_PROMPT,
    ANALYSIS_TASK_PROMPT,
    RESPONSE_SYNTHESIS_PROMPT,
    PLANNER_SYSTEM_PROMPT
)

logger = logging.getLogger(__name__)

# Create a default root agent instance for ADK web runner
root_agent = None


class OrchestratorAgent:
    """
    Orchestrator Agent - Root sequential agent that coordinates the security analysis workflow.
    
    This sequential agent follows a three-step process:
    1. Plan: Create a structured research plan (Planner Agent)
    2. Research: Retrieve relevant security information (Research Agent)
    3. Analyze: Evaluate findings and generate insights (Analysis Agent)
    """

    def __init__(self, model_name: str = "gemini-2.5-flash-preview-04-17", use_mcp: bool = True):
        """
        Initialize the Orchestrator Agent with its component agents.
        
        Args:
            model_name: The Vertex AI model to use for all agents
            use_mcp: Whether to use MCP server connection for CVE lookups
        """
        self.use_mcp = use_mcp
        self.model_name = model_name # Store for consistency

        # Initialize component agents
        self.cve_agent = CveLookupAgent(model_name=model_name) # This is an instance of your CveLookupAgent class
        self.planner_agent = PlannerAgent(model_name)
        self.research_agent = ResearchAgent(model_name) # Basic initialization
        self.analysis_agent = AnalysisAgent(model_name)
        
        self.root_agent = None # SequentialAgent, will be created after async setup

    async def _initialize_sub_agents_and_create_sequence(self):
        """Connects CVE agent, adds its tool to ResearchAgent, and creates the SequentialAgent."""
        if self.root_agent: # Already initialized
            logger.info("Orchestrator: SequentialAgent (root_agent) already initialized.")
            return

        if self.use_mcp and self.cve_agent:
            logger.info("Orchestrator: Connecting CVE agent to MCP server...")
            try:
                connected = await self.cve_agent.connect()
                if connected:
                    logger.info("Orchestrator: CVE agent connected successfully.")
                    # get_agent_tool() is synchronous and returns the AgentTool instance
                    cve_tool_for_researcher = self.cve_agent.get_agent_tool() 
                    if cve_tool_for_researcher:
                        # add_cve_tool is synchronous and recreates research_agent.agent
                        self.research_agent.add_cve_tool(cve_tool_for_researcher)
                        logger.info("Orchestrator: CVE tool added to ResearchAgent's LlmAgent.")
                    else:
                        logger.warning("Orchestrator: Failed to get CVE tool from CveLookupAgent (get_agent_tool returned None).")
                else:
                    logger.warning("Orchestrator: CVE agent connection failed.")
            except Exception as e:
                logger.error(f"Orchestrator: Error during CVE agent setup: {e}", exc_info=True)
        else:
            logger.info("Orchestrator: MCP for CVE is not used or CveLookupAgent not available. Proceeding without CVE tool integration for ResearchAgent.")

        # Now create the SequentialAgent with the (potentially updated) ResearchAgent.agent
        self.root_agent = SequentialAgent(
            name="security_orchestrator",
            sub_agents=[
                self.planner_agent.agent,    # PlannerAgent's LlmAgent
                self.research_agent.agent,   # ResearchAgent's LlmAgent (now potentially with CVE tool)
                self.analysis_agent.agent,   # AnalysisAgent's LlmAgent
            ],
            description="Executes a sequence of planning, research, and analysis for zero-day vulnerabilities"
        )
        logger.info("Orchestrator: SequentialAgent (root_agent) created/updated with current sub-agent configurations.")
            
    async def cleanup_resources(self):
        """Clean up all resources used by the agents.
        
        This should be called when processing is complete to ensure proper resource cleanup.
        """
        logger.info("Cleaning up Orchestrator resources")
        
        # Clean up resources for research, CVE, and analysis agents
        # Note: self.cve_agent is the CveLookupAgent class instance, not an LlmAgent
        # Its cleanup is called directly.
        agent_instances_to_cleanup = [
            ("research", self.research_agent), 
            ("analysis", self.analysis_agent)
        ]
        if self.cve_agent: # Add CveLookupAgent itself if it exists
             agent_instances_to_cleanup.append(("cve_lookup_service", self.cve_agent))

        for agent_name, agent_obj in agent_instances_to_cleanup:
            if hasattr(agent_obj, 'cleanup') and callable(agent_obj.cleanup):
                try:
                    # Check if cleanup is an async method
                    if asyncio.iscoroutinefunction(agent_obj.cleanup):
                        await agent_obj.cleanup()
                    else:
                        agent_obj.cleanup() # Call synchronously if not async
                    logger.info(f"{agent_name.capitalize()} agent resources cleaned up")
                except Exception as e:
                    logger.warning(f"Error cleaning up {agent_name} agent resources: {e}")
                    import traceback
                    logger.warning(f"Cleanup error traceback: {traceback.format_exc()}")
        
        logger.info("Orchestrator resource cleanup complete")
    
    async def process_query(self, query: str, timeout: float = 300.0) -> dict:
        """
        Process a user query through the complete agent workflow.
        
        Args:
            query: The security query from the user
            timeout: Maximum time in seconds to wait for a response (default: 5 minutes)
            
        Returns:
            Dictionary containing the final response and intermediate outputs
        """
        logger.info(f"Orchestrator: Processing query: {query}")

        # Ensure agents are initialized and sequence is created
        if not self.root_agent:
            await self._initialize_sub_agents_and_create_sequence()
        
        if not self.root_agent: # Still not there after attempt
            logger.error("Orchestrator: Root sequential agent could not be initialized. Aborting.")
            return {
                "final_response": "Critical error: Orchestrator failed to initialize. Please check logs.", 
                "agent_outputs": {}
            }
        
        # Check if the query contains CVE-related terms to log a hint
        if "CVE-" in query or "cve-" in query or "Log4Shell" in query or "log4shell" in query:
            logger.info("Query contains CVE-related terms. Planner should instruct researcher to use CVE specialist tool.")
        
        # Create a session for processing the query
        # session_service = InMemorySessionService() # Not needed if runner creates its own
        # user_id = "user_1"
        # session_id = "session_1"
        # session = session_service.create_session(
        #     app_name="scout_agent", 
        #     user_id=user_id, 
        #     session_id=session_id
        # )

        # Create a runner to execute the sequential agent
        runner = InMemoryRunner(
            agent=self.root_agent # Use the fully constructed SequentialAgent
        )

        # Session for the runner
        session = runner.session_service.create_session(
            app_name=runner.app_name, user_id="test_user" # Consider making user_id dynamic
        )
        
        logger.info(f"Setting timeout of {timeout} seconds for query processing")

        content = UserContent(parts=[Part(text=query)])

        logger.info(f"Processing query with sequential agent: {query}")
        
        final_response = ""
        agent_outputs = {
            "security_planner": {"output": "", "role": "planner"},
            "security_researcher": {"output": "", "role": "researcher"}, # This will be security_researcher_with_cve if tool added
            "security_analyst": {"output": "", "role": "analyst"},
            "security_orchestrator": {"output": "", "role": "orchestrator"}
        }
        
        try:
            import queue
            import threading
            response_queue = queue.Queue()
            
            def agent_thread_worker():
                try:
                    thread_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(thread_loop)
                    
                    thread_final_response = ""
                    thread_agent_outputs = {k: dict(v) for k, v in agent_outputs.items()}
                    
                    try:
                        for event in runner.run(
                            user_id=session.user_id, session_id=session.id, new_message=content
                        ):
                            if not hasattr(event, 'content') or not event.content or not event.content.parts:
                                continue
                            
                            # Ensure we only collect actual strings, filtering out None values from part.text
                            text_parts = []
                            for part in event.content.parts:
                                if hasattr(part, 'text') and part.text is not None:
                                    text_parts.append(part.text)
                                # Optional: Log non-text parts or None text parts if needed for debugging
                                # elif isinstance(part, types.FunctionCall):
                                #     logger.info(f"Thread received function call: {part.function_call.name} from {getattr(event, 'author', 'unknown')}")
                                # elif hasattr(part, 'text') and part.text is None:
                                #     logger.info(f"Thread received a part with None text from {getattr(event, 'author', 'unknown')}")

                            text = "\\n".join(text_parts) if text_parts else ""
                            
                            author = getattr(event, 'author', None)
                            if author:
                                # Adjust for potentially renamed research agent
                                current_researcher_name = self.research_agent.agent.name 
                                if author == current_researcher_name and "security_researcher" in thread_agent_outputs:
                                     author_key = "security_researcher" # Log under consistent key
                                elif author in thread_agent_outputs:
                                     author_key = author
                                else:
                                     author_key = "security_orchestrator" # Default if author not in predefined keys

                                logger.info(f"Thread received output from agent: {author} (logging as {author_key})")
                                thread_agent_outputs[author_key]["output"] = text
                                response_queue.put(("agent_output", (author_key, text)))
                            
                            thread_final_response = text # Last message is considered final for now
                    
                    except Exception as run_error:
                        logger.error(f"Error during agent.run() in thread: {run_error}", exc_info=True)
                        response_queue.put(("error", str(run_error)))
                        return
                    
                    logger.info("Thread completed successfully with final response")
                    response_queue.put(("final", (thread_final_response, thread_agent_outputs)))
                    
                except Exception as thread_error:
                    logger.error(f"Thread exception: {thread_error}", exc_info=True)
                    response_queue.put(("error", str(thread_error)))
                finally:
                    if 'thread_loop' in locals() and thread_loop.is_running():
                        thread_loop.call_soon_threadsafe(thread_loop.stop)
                    # thread_loop.close() # Closing can sometimes cause issues if not fully stopped

            logger.info("Starting agent processing thread")
            worker_thread = threading.Thread(target=agent_thread_worker)
            worker_thread.daemon = True
            worker_thread.start()
            
            import time
            start_time = time.time()
            
            processing_complete = False
            while time.time() - start_time < timeout:
                if not worker_thread.is_alive() and response_queue.empty():
                    logger.info("Worker thread has completed and queue is empty.")
                    processing_complete = True
                    break
                    
                try:
                    msg_type, msg_data = response_queue.get(timeout=0.5) # Add timeout to get
                    
                    if msg_type == "agent_output":
                        agent_name, text = msg_data
                        agent_outputs[agent_name]["output"] = text
                        logger.info(f"Received agent output from thread: {agent_name}")
                    elif msg_type == "error":
                        logger.error(f"Thread reported error: {msg_data}")
                        raise Exception(msg_data)
                    elif msg_type == "final":
                        final_response, final_agent_outputs = msg_data
                        agent_outputs.update(final_agent_outputs) # Ensure all outputs are captured
                        logger.info("Received final response and outputs from thread")
                        processing_complete = True
                        break 
                except queue.Empty:
                    continue # Loop and check thread status or timeout
            
            if not processing_complete and worker_thread.is_alive():
                 logger.warning(f"Thread processing timed out after {timeout} seconds")
                 final_response = "I apologize, but the query processing timed out."
                 # Attempt to join the thread briefly, but don't hang indefinitely
                 worker_thread.join(timeout=1.0)


            # If thread finished but we missed the 'final' message due to timing
            if not final_response and not worker_thread.is_alive():
                logger.info("Thread finished, attempting to retrieve any last messages from queue.")
                while not response_queue.empty():
                    try:
                        msg_type, msg_data = response_queue.get(block=False)
                        if msg_type == "agent_output":
                            agent_name, text = msg_data
                            agent_outputs[agent_name]["output"] = text
                        elif msg_type == "final":
                            final_response, final_agent_outputs = msg_data
                            agent_outputs.update(final_agent_outputs)
                            break 
                    except queue.Empty:
                        break
                if not final_response: # If still no final response, construct from parts
                    logger.warning("No explicit final response after thread completion; constructing from outputs.")
                    # Construct from agent_outputs if necessary, or use last known output
                    # This part might need refinement based on how you want to handle partial results
                    if agent_outputs["security_analyst"]['output']:
                        final_response = agent_outputs["security_analyst"]['output']
                    elif agent_outputs["security_researcher"]['output']:
                         final_response = agent_outputs["security_researcher"]['output']
                    else:
                         final_response = "Processing completed, but no definitive final response was captured."

        except Exception as e:
            logger.error(f"Error during query processing: {e}", exc_info=True)
            final_response = f"I apologize, but there was an error during query processing: {str(e)}"
            
        logger.info("Query processing completed")
            
        try:
            await self.cleanup_resources()
        except Exception as cleanup_error:
            logger.warning(f"Error during final cleanup: {cleanup_error}", exc_info=True)
        
        return {
            "final_response": final_response,
            "agent_outputs": agent_outputs
        }


class PlannerAgent:
    """
    Planner Agent - Creates structured plans for security research and analysis.

    This agent breaks down security queries into specific research tasks and analysis requirements.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash-preview-04-17"):
        """
        Initialize the Planner Agent.

        Args:
            model_name: The Vertex AI model to use
        """
        self.agent = LlmAgent(
            name="security_planner",
            description="Creates detailed research plans for security queries",
            model=model_name,
            instruction=PLANNER_SYSTEM_PROMPT, 
            output_key="research_plan",
        )

class ResearchAgent:
    """
    Research Agent - Specialized for information retrieval.
    
    Uses tools to query RAG, web, and CVE information.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash-preview-04-17"):
        self.rag_tool = RagQueryTool()
        self.web_search_tool = WebSearchTool()
        self.model_name = model_name
        self.cve_tool_instance_ref = None # To store the cve tool if added

        self.base_tools = [self.rag_tool, self.web_search_tool]
        
        # Initial LlmAgent with base tools
        self.agent = LlmAgent(
            name="security_researcher", 
            description="Security researcher specialized in finding vulnerability information",
            model=self.model_name,
            instruction=RESEARCH_TASK_PROMPT, # This prompt needs to be updated
            tools=list(self.base_tools), # Ensure a new list is passed
            output_key="research_findings",
        )
        logger.info(f"ResearchAgent initialized with {len(self.base_tools)} basic tools. Name: {self.agent.name}")

    def add_cve_tool(self, cve_tool_instance: FunctionTool): # Assuming AgentTool is a type of FunctionTool or compatible
        """Recreates the internal LlmAgent to include the CVE tool."""
        if not cve_tool_instance:
            logger.warning("ResearchAgent: add_cve_tool called with no tool instance.")
            return False

        self.cve_tool_instance_ref = cve_tool_instance
        # Create a new list for tools to avoid modifying the original base_tools list
        updated_tools = list(self.base_tools) + [self.cve_tool_instance_ref]

        logger.info("--- Tools for Recreated ResearchAgent ---")
        for tool_obj in updated_tools:
            # Ensure tool_obj has a name, provide default if not for logging
            tool_name = getattr(tool_obj, 'name', "UnknownTool")
            tool_desc = getattr(tool_obj, 'description', "No description")
            logger.info(f"Tool Name: {tool_name}, Description: {tool_desc}")
        logger.info("---------------------------------------")
        
        # Recreate the LlmAgent
        self.agent = LlmAgent(
            name="security_researcher_with_cve", 
            description="Security researcher with CVE lookup capabilities",
            model=self.model_name,
            instruction=RESEARCH_TASK_PROMPT, # This prompt needs to be updated
            tools=updated_tools,
            output_key="research_findings",
        )
        logger.info(f"ResearchAgent's LlmAgent recreated as '{self.agent.name}' with {len(updated_tools)} tools.")
        return True

    async def cleanup(self):
        logger.info("Cleaning up Research Agent resources")
        if hasattr(self.rag_tool, '_pipeline') and self.rag_tool._pipeline is not None:
            if hasattr(self.rag_tool._pipeline, 'cleanup') and callable(self.rag_tool._pipeline.cleanup):
                try:
                    # RAG pipeline cleanup might be synchronous or asynchronous
                    if asyncio.iscoroutinefunction(self.rag_tool._pipeline.cleanup):
                        await self.rag_tool._pipeline.cleanup()
                    else:
                        self.rag_tool._pipeline.cleanup()
                    logger.info("RAG pipeline resources cleaned up")
                except Exception as e:
                    logger.warning(f"Error cleaning up RAG pipeline: {e}", exc_info=True)
        logger.info("Research Agent resources cleaned up successfully")


class AnalysisAgent:
    """
    Analysis Agent - Evaluates retrieved information for security insights.
    """
    def __init__(self, model_name: str = "gemini-2.5-flash-preview-04-17"):
        self.vulnerability_tool = VulnerabilityAnalysisTool()
        self.web_search_tool = WebSearchTool()
        
        self.agent = LlmAgent(
            name="security_analyst",
            description="Security analyst specialized in vulnerability assessment",
            model=model_name,
            instruction=ANALYSIS_TASK_PROMPT,
            tools=[self.vulnerability_tool, self.web_search_tool],
        )

# Initialize the default root agent for ADK web runner
try:
    default_orchestrator = OrchestratorAgent()
    # To make root_agent usable by ADK web, it needs to be fully initialized if it relies on async setup.
    # However, ADK web runner typically expects a synchronous instantiation.
    # For now, we set it, but for ADK web, a synchronous setup or a wrapper might be needed.
    # This default_orchestrator.root_agent will be None until process_query is called.
    # A better approach for ADK web might be to have a factory function or ensure sync init.
    async def _get_default_root_agent():
        await default_orchestrator._initialize_sub_agents_and_create_sequence()
        return default_orchestrator.root_agent

    # If running in a context where an event loop is present (e.g. Jupyter notebook with !pip install nest_asyncio)
    # import nest_asyncio
    # nest_asyncio.apply()
    # root_agent = asyncio.run(_get_default_root_agent())
    # For simple script execution, this direct assignment of a coroutine won't work for ADK web.
    # ADK web expects `root_agent` to be an `Agent` instance directly.
    # For now, this will leave `root_agent` as None if `_initialize_sub_agents_and_create_sequence` is not run.
    # A common pattern for ADK web is to have a simple, synchronously initialized agent as root_agent.
    # The complex async setup might need to be triggered differently for ADK web.
    if os.getenv("ADK_WEB_RUNNER") == "true":
         logger.warning("ADK Web Runner detected. Default root_agent might not be fully async initialized here.")
         # Fallback to a synchronously initialized part if possible, or a placeholder.
         # For now, OrchestratorAgent itself doesn't have a direct .agent, its root_agent is the SequentialAgent.
         # This part needs careful consideration for ADK Web compatibility with async init.
         pass # root_agent remains None or needs a synchronous alternative for ADK web.
    else:
        # For non-ADK web (e.g. script runs), it will be initialized in process_query.
        pass

    logger.info(f"Default root_agent for ADK web runner is initially: {root_agent}")

except Exception as e:
    logger.error(f"Failed to initialize default root_agent: {e}", exc_info=True)

