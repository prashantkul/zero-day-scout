# Zero-Day Scout

A RAG-based security analysis system using Google Cloud Vertex AI RAG Engine.

## Project Overview

Zero-Day Scout is an AI-powered security intelligence system that combines multi-agent orchestration with advanced document analysis to identify and analyze security vulnerabilities. 
Built on Google's Agent Development Kit (ADK), it features a sequential three-agent workflow (Plan → Research → Analyze) that processes security documents through Vertex AI RAG Engine for deep insights.

The system provides two modes of interaction - 
1. RAG System - Direct document retrieval & question answering
2. Agentic RAG - Deep security research with multi-agent workflow

The system integrates with CVE databases via Message Communication Protocol (MCP) to provide real-time vulnerability data, and offers both a Scout CLI for security analysis and an interactive CVE CLI for vulnerability
searches. It generates comprehensive security reports in markdown format, making it an essential tool for security researchers and professionals seeking to understand emerging threats and vulnerabilities in their
technology stack.

## Console Screenshots

### Zero-day HQ
Run `python zero_day_hq.py `
![ZTS-HQ](https://github.com/prashantkul/zero-day-scout/blob/add-screen-shots/zts-1.png)

### Option # 1 - Interact with RAG system
![RAG](https://github.com/prashantkul/zero-day-scout/blob/add-screen-shots/zts-2.png)

### Option # 2 - Interact with Agentic RAG system
![Agentic-RAG](https://github.com/prashantkul/zero-day-scout/blob/add-screen-shots/zts-3.png)

## Architecture
![Architecture](https://github.com/prashantkul/zero-day-scout/blob/add-screen-shots/Zero-Day%20Scout.png)


## Environment Setup

```bash
# Create a conda environment
conda create --name scout python=3.11

# Activate the environment
conda activate scout

# Install dependencies
pip install -r requirements.txt
# or with uv (which is listed as a dependency)
uv pip install -r requirements.txt

# Set up environment variables (copy template first)
cp .env.template .env
# Edit .env with your actual values
```

## Project Structure

- `config/`: Configuration files for the application
  - `constants.py`: Default configuration values
  - `config_manager.py`: Manages loading config from environment variables
- `src/`: Source code for the application
  - `rag/`: RAG pipeline implementation
    - `pipeline.py`: Main RAG pipeline using Vertex AI
    - `gcs_utils.py`: Utilities for working with Google Cloud Storage
  - `examples/`: Example usage scripts
- `tests/`: Test files for the application

## Configuration

Configuration is managed through environment variables and default values:

1. Copy `.env.template` to `.env` and edit with your values
2. Key environment variables:
   - `GOOGLE_CLOUD_PROJECT`: Your GCP project ID
   - `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account key
   - `GCS_BUCKET`: GCS bucket for document storage
   - `RAG_CORPUS_NAME`: Name for the RAG corpus
   - `DOCUMENT_PREFIXES`: Comma-separated list of GCS prefixes to scan for documents (e.g., "research/,papers/,publications/")

## Document Ingestion

### Document Prefixes

The system can be configured to ingest documents from specific prefixes in your GCS bucket:

1. Configure document prefixes in your `constants.py` file:
   ```
   DOCUMENT_PREFIXES=research/,papers/,publications/
   ```

2. Default prefixes are set in `config/constants.py` if not specified:
   ```python
   DEFAULT_DOCUMENT_PREFIXES = [
    "arxiv_security_papers/",
    "uploaded_papers/",
    "cves/",] 
   ```

3. To ingest documents from these prefixes, call the `ingest_documents` method with an empty list:
   ```python
   pipeline.ingest_documents([])  # Uses configured prefixes
   ```

## Testing MCP with MCP Inspector
MCP server can be tested with MCP Inspector
1. Start MCP server using `start_cve_mcp_server.sh`, this will launch MCP server in background mode.
   ```Starting CVE MCP Server in the foreground...
      2025-05-24 08:11:18,721 - cve-search-mcp - INFO - Starting MCP server at http://0.0.0.0:8080
      2025-05-24 08:11:18,721 - cve-search-mcp - INFO -   - StreamableHTTP MCP: http://0.0.0.0:8080/mcp/
      2025-05-24 08:11:18,721 - cve-search-mcp - INFO -   - SSE MCP (Legacy): http://0.0.0.0:8080/mcp/sse
      2025-05-24 08:11:18,721 - cve-search-mcp - INFO -   - HTTP Ping: http://0.0.0.0:8080/ping
      2025-05-24 08:11:18,721 - cve-search-mcp - INFO -   - JSON response mode for StreamableHTTP: disabled
      INFO:     Started server process [53353]
      INFO:     Waiting for application startup.
      2025-05-24 08:11:18,760 - mcp.server.streamable_http_manager - INFO - StreamableHTTP session manager started
      2025-05-24 08:11:18,760 - cve-search-mcp - INFO - MCP server started with StreamableHTTPSessionManager and SSE transport
      INFO:     Application startup complete.```

![MCP-Inspector](https://github.com/prashantkul/zero-day-scout/blob/add-screen-shots/mcp.png)


### Duplicate Prevention

The system now tracks ingested documents to prevent duplicates:

1. Previously ingested documents are stored in a JSON file (`.ingested_docs.json` by default)
2. When ingesting documents, only new documents not previously ingested are processed
3. The tracking file path can be customized when initializing the pipeline:
   ```python
   pipeline = VertexRagPipeline(tracking_file="/custom/path/to/tracking.json")
   ```

## RAG Reranking support
The system uses Vertex AI Reranking to improve quality of content. 

See `README_RERANKING.md` for more information on setting up and using the reranking feature.

## Agentic RAG System

Zero-Day Scout includes an agentic RAG system that uses Google ADK (Agent Development Kit) to orchestrate multiple specialized agents for comprehensive security analysis.

### Agent Architecture

The system uses a `SequentialAgent` that coordinates three specialized agents:

1. **PlannerAgent**: Creates a structured research plan from the user query
   - Output stored in: `state["research_plan"]`
   
2. **ResearchAgent**: Executes the plan using multiple tools (RAG, CVE lookup, web search)
   - Reads from: `state["research_plan"]`
   - Output stored in: `state["research_findings"]`
   
3. **AnalysisAgent**: Analyzes findings and generates security insights
   - Reads from: `state["research_plan"]` and `state["research_findings"]`
   - Produces the final response

### How Agent State Passing Works

The Google ADK `SequentialAgent` automatically manages data flow between agents:

1. Each agent defines an `output_key` when initialized
2. The agent's output is automatically stored in the shared state using this key
3. Subsequent agents can access previous outputs from the state
4. The state is passed automatically - no manual intervention required

Example flow:
```
User Query → PlannerAgent → state["research_plan"] → ResearchAgent → state["research_findings"] → AnalysisAgent → Final Response
```

### Troubleshooting

#### RAG Query Tool Not Being Used

**Issue**: The Research Agent may not use the RAG query tool even when it should.

**Cause**: Tool naming mismatch between prompts and actual tool definitions.

**Solution**: Ensure tool names in prompts match the function names:
- RAG tool: `rag_query` (not `rag_query_tool`)
- Web search tool: `web_search` (not `web_search_tool`)
- CVE tool: `cve_lookup_specialist`

The prompts should reference these exact tool names. Additionally, the Research Agent prompt should enforce RAG-first approach:
- Make RAG query mandatory as the first step
- Use other tools only to supplement RAG results
- Explicitly state that `rag_query` is the PRIMARY source

#### Agent State Access

**Issue**: Agents may not properly access data from previous agents.

**Solution**: Ensure prompts explicitly specify the state keys:
```python
# In Research Agent prompt:
"The research plan from the planner agent will be available in the agent state with the key 'research_plan'."

# In Analysis Agent prompt:
"The research plan will be available in the agent state with the key 'research_plan'."
"The research findings will be available in the agent state with the key 'research_findings'."
```

### Running the Agentic System

```bash
# Run the Scout Agent with CVE MCP integration
python -m src.scout_agent.run --query "Tell me about Log4Shell vulnerability"

# Start the CVE MCP server (required for CVE lookups)
./start_cve_mcp_server.sh start
```

## Development Guidelines

When working with this codebase:

1. Always ensure proper authentication with Google Cloud
2. Update environment variables in .env for your specific setup
3. Follow the existing module structure for new features
4. Add tests for new functionality when implementing
5. When modifying agent prompts, ensure tool names match actual function definitions
6. Test the full agent pipeline after any prompt changes
