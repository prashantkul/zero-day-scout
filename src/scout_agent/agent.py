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

from google.adk.agents import Agent, LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool
from google.adk.runners import Runner, InMemoryRunner
from google.genai.types import Part, UserContent
from google.adk.sessions import InMemorySessionService
from google.genai import types
from vertexai.generative_models import GenerationConfig

from src.rag.pipeline import VertexRagPipeline
from src.scout_agent.tools import RagQueryTool, VulnerabilityAnalysisTool, CveLookupTool
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


class OrchestratorAgent:
    """
    Orchestrator Agent - Root sequential agent that coordinates the security analysis workflow.
    
    This sequential agent follows a three-step process:
    1. Plan: Create a structured research plan (Planner Agent)
    2. Research: Retrieve relevant security information (Research Agent)
    3. Analyze: Evaluate findings and generate insights (Analysis Agent)
    """

    def __init__(self, model_name: str = "gemini-2.5-flash-preview-04-17"):
        """
        Initialize the Orchestrator Agent with its component agents.
        
        Args:
            model_name: The Vertex AI model to use for all agents
        """
        # Initialize component agents
        self.planner_agent = PlannerAgent(model_name)
        self.research_agent = ResearchAgent(model_name)
        self.analysis_agent = AnalysisAgent(model_name)

        # Create the sequential orchestrator agent
        # This agent orchestrates the pipeline by running the sub-agents in order
        self.orchestrator = SequentialAgent(
            name="security_orchestrator",
            sub_agents=[
                self.planner_agent.agent,  # Step 1: Plan research
                self.research_agent.agent, # Step 2: Conduct research
                self.analysis_agent.agent  # Step 3: Analyze findings and provide final response
            ],
            description="Executes a sequence of planning, research, and analysis for zero-day vulnerabilities"
            # The agents will run in the order provided: Planner -> Researcher -> Analyst
        )

        # For ADK tools compatibility, define the root agent
        self.root_agent = self.orchestrator

    async def process_query(self, query: str) -> str:
        """
        Process a user query through the complete agent workflow.
        
        Args:
            query: The security query from the user
            
        Returns:
            The final synthesized response
        """
        # Create a session for processing the query
        session_service = InMemorySessionService()
        user_id = "user_1"
        session_id = "session_1"
        session = session_service.create_session(
            app_name="scout_agent", 
            user_id=user_id, 
            session_id=session_id
        )

        # Create a runner to execute the sequential agent
        runner = InMemoryRunner(
            agent=self.root_agent
        )

        session = runner.session_service.create_session(
            app_name=runner.app_name, user_id="test_user"
        )

        # Prepare the user's message
        content = UserContent(parts=[Part(text=query)])

        logger.info(f"Processing query with sequential agent: {query}")

        for event in runner.run(
            user_id=session.user_id, session_id=session.id, new_message=content
        ):
            for part in event.content.parts:
                print(part.text)


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
        # Create the planner agent
        self.agent = LlmAgent(
            name="security_planner",
            description="Creates detailed research plans for security queries",
            model=model_name,
            instruction=PLANNER_SYSTEM_PROMPT,
            output_key="research_plan",  # Store planner output in state
        )

class ResearchAgent:
    """
    Research Agent - Specialized for information retrieval from the RAG corpus.
    
    This agent uses tools to query the RAG system and retrieve relevant information
    about security vulnerabilities and zero-day exploits.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash-preview-04-17"):
        """
        Initialize the Research Agent with RAG query tools.
        
        Args:
            model_name: The Vertex AI model to use
        """
        # Create RAG query tool
        self.rag_tool = RagQueryTool()

        # Create the agent with the RAG tool
        self.agent = LlmAgent(
            name="security_researcher",
            description="Security researcher specialized in finding vulnerability information",
            model=model_name,
            instruction=RESEARCH_TASK_PROMPT,  # Using the task-specific prompt for research
            tools=[self.rag_tool],
            output_key="research_findings",  # Store research output in state
        )


class AnalysisAgent:
    """
    Analysis Agent - Evaluates retrieved information for security insights.
    
    This agent uses specialized tools to analyze security information,
    identify vulnerabilities, and provide security assessments.
    """

    def __init__(self, model_name: str = "gemini-2.5-flash-preview-04-17"):
        """
        Initialize the Analysis Agent with security analysis tools.
        
        Args:
            model_name: The Vertex AI model to use
        """
        # Create analysis tools
        self.vulnerability_tool = VulnerabilityAnalysisTool()
        self.cve_lookup_tool = CveLookupTool()

        # Create the agent with analysis tools
        self.agent = LlmAgent(
            name="security_analyst",
            description="Security analyst specialized in vulnerability assessment",
            model=model_name,
            instruction=ANALYSIS_TASK_PROMPT,  # Using the task-specific prompt for analysis
            tools=[self.vulnerability_tool, self.cve_lookup_tool],
        )
