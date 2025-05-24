# Zero-Day Scout: Software Architecture Design

## 1. Executive Summary

Zero-Day Scout is an advanced security research system that leverages Retrieval-Augmented Generation (RAG), multi-agent orchestration, and real-time vulnerability intelligence to provide comprehensive security research capabilities. The system combines Google Cloud Vertex AI RAG Engine, Google Agent Development Kit (ADK), Message Communication Protocol (MCP), and specialized security APIs to create a sophisticated security analysis platform.

## 2. System Overview

### 2.1 Purpose
Zero-Day Scout enables security researchers and analysts to:
- Conduct comprehensive security document analysis using RAG
- Search and analyze CVE vulnerability databases in real-time  
- Orchestrate complex security research workflows through intelligent agents
- Generate detailed security reports with citations and evidence
- Access distributed security intelligence through MCP integration

### 2.2 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            Zero-Day Scout Architecture                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐              │
│  │  User Interface │    │   CLI Interface │    │ Streamlit App   │              │
│  │     Layer       │    │                 │    │                 │              │
│  └─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘              │
│            │                      │                      │                      │
│            └──────────────────────┼──────────────────────┘                      │
│                                   │                                             │
│  ┌─────────────────────────────────┼─────────────────────────────────────────┐   │
│  │              Agent Orchestration Layer                                    │   │
│  │                                 │                                         │   │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐       │   │
│  │  │  Orchestrator   │    │   Planner       │    │   Research      │       │   │
│  │  │     Agent       │    │    Agent        │    │    Agent        │       │   │
│  │  └─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘       │   │
│  │            │                      │                      │               │   │
│  │            └──────────────────────┼──────────────────────┘               │   │
│  │                                   │                                      │   │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐       │   │
│  │  │    Analysis     │    │   CVE Lookup    │    │  Web Search     │       │   │
│  │  │     Agent       │    │     Agent       │    │     Tool        │       │   │
│  │  └─────────────────┘    └─────────────────┘    └─────────────────┘       │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                   │                                             │
│  ┌─────────────────────────────────┼─────────────────────────────────────────┐   │
│  │                    Tools & Services Layer                                │   │
│  │                                 │                                         │   │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐       │   │
│  │  │   RAG Query     │    │  Vulnerability  │    │    CVE MCP      │       │   │
│  │  │     Tool        │    │ Analysis Tool   │    │    Server       │       │   │
│  │  └─────────┬───────┘    └─────────────────┘    └─────────┬───────┘       │   │
│  │            │                                             │               │   │
│  │            └─────────────────┬───────────────────────────┘               │   │  
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                │                                               │
│  ┌─────────────────────────────┼─────────────────────────────────────────────┐ │
│  │                    Data & Infrastructure Layer                           │ │
│  │                             │                                             │ │
│  │  ┌─────────────────┐  ┌─────────────┐  ┌─────────────────┐ ┌─────────────┐ │ │
│  │  │   Vertex AI     │  │    GCS      │  │  CVE Database   │ │   Tavily    │ │ │
│  │  │  RAG Engine     │  │   Bucket    │  │   (External)    │ │ Web Search  │ │ │
│  │  └─────────────────┘  └─────────────┘  └─────────────────┘ └─────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 3. Core Components

### 3.1 Agent Orchestration Layer

#### 3.1.1 Orchestrator Agent (`src/scout_agent/agent.py`)
**Purpose**: Main coordinator that manages the entire security analysis workflow

**Responsibilities**:
- Orchestrate sequential agent execution (Plan → Research → Analyze)
- Manage MCP server connections for CVE lookups
- Handle query processing with timeout and error recovery
- Coordinate resource cleanup and session management
- Implement LLM transfer patterns for specialized tasks

**Key Features**:
- Sequential workflow with Planner → Research → Analysis agents
- Asynchronous MCP connection management
- Thread-safe query processing with timeout handling (default 300s)
- Automatic fallback mechanisms for robustness
- Dynamic CVE tool integration into Research Agent when MCP is available

**Implementation Details**:
- Uses Google ADK's `SequentialAgent` to chain sub-agents
- Implements async initialization pattern for MCP connections
- Thread-based execution with queue-based communication for timeout handling
- Automatic resource cleanup after query processing

#### 3.1.2 Planner Agent
**Purpose**: Creates structured research plans for security queries

**Responsibilities**:
- Break down complex security queries into actionable research tasks
- Generate structured research plans with clear objectives
- Identify required tools and information sources
- Set priorities and research scope

**Implementation Details**:
- Uses `LlmAgent` with specialized planning instruction prompt
- Output key: "research_plan" for structured plan generation
- Works with configurable models (default: gemini-2.5-flash-preview-04-17)

#### 3.1.3 Research Agent  
**Purpose**: Execute information retrieval using multiple tools and sources

**Responsibilities**:
- Query RAG corpus for relevant security documents
- Perform web searches for current threat intelligence
- Delegate CVE lookups to specialized CVE agent
- Integrate multiple information sources
- Format and contextualize retrieved information

**Tools Integration**:
- RAG Query Tool for document corpus access
- Web Search Tool for real-time information
- CVE Lookup Agent for vulnerability intelligence (dynamically added when MCP available)

**Implementation Details**:
- Base tools: RAG Query and Web Search always available
- CVE tool added dynamically via `add_cve_tool()` method
- Agent name changes from "security_researcher" to "security_researcher_with_cve" when CVE tool added
- Implements cleanup method for RAG pipeline resources

#### 3.1.4 Analysis Agent
**Purpose**: Evaluate retrieved information and generate security insights

**Responsibilities**:
- Analyze security information for vulnerabilities and threats
- Assess risk levels and impact scenarios  
- Generate actionable security recommendations
- Synthesize findings from multiple sources
- Create comprehensive security reports

#### 3.1.5 CVE Lookup Agent (`src/scout_agent/cve_agent.py`)
**Purpose**: Specialized agent for CVE vulnerability lookups via MCP

**Responsibilities**:
- Connect to CVE MCP server for real-time vulnerability data
- Handle MCP protocol communication and error recovery
- Format CVE information for consumption by other agents
- Manage connection lifecycle and health monitoring

**Implementation Details**:
- Uses `MCPStreamableHTTPClient` for MCP protocol communication
- Creates ADK-compatible `FunctionTool` wrappers for MCP tools
- Implements intelligent query parsing to determine appropriate CVE tool:
  - `vul_cve_search` for specific CVE IDs (e.g., CVE-2021-44228)
  - `vul_last_cves` for latest vulnerabilities
  - `vul_vendor_product_cve` for vendor/product queries
- Formats CVE JSON 5.1 responses into readable markdown
- Provides `AgentTool` wrapper for integration with Research Agent

### 3.2 Tools & Services Layer

#### 3.2.1 RAG Query Tool (`src/scout_agent/tools.py`)
**Purpose**: Interface to Vertex AI RAG Engine for document retrieval

**Features**:
- Direct RAG integration with chunking and reranking
- Time-based filtering for temporal queries
- Context tracking for result transparency
- Quota limit handling with graceful degradation
- Metadata extraction and source attribution

#### 3.2.2 Vulnerability Analysis Tool
**Purpose**: Analyze text content for security vulnerabilities

**Capabilities**:
- Security pattern recognition
- Severity assessment and classification
- CVE correlation and mapping
- Risk scoring and prioritization

#### 3.2.3 Web Search Tool (`src/scout_agent/web_search_tool.py`)
**Purpose**: Real-time web intelligence gathering using Tavily API

**Features**:
- Security-focused search queries
- Result filtering and relevance scoring
- Source credibility assessment
- Integration with other intelligence sources

#### 3.2.4 CVE MCP Server (`src/cve_mcp/streamable_server.py`)
**Purpose**: MCP-compliant server providing CVE database access

**API Endpoints**:
- `vul_vendors`: List vulnerability vendors
- `vul_vendor_products`: Get products by vendor
- `vul_vendor_product_cve`: Get CVEs by vendor/product
- `vul_cve_search`: Search specific CVE by ID
- `vul_last_cves`: Get latest CVEs (30 most recent)
- `vul_db_update_status`: Database status information
- `ping`: Health monitoring and latency measurement

**Transport**:
- Primary: StreamableHTTP transport with MCP protocol
- Legacy support: SSE endpoint redirects to StreamableHTTP
- Built with Starlette/FastAPI for HTTP handling
- Configurable JSON response mode

**Implementation Details**:
- Base URL: https://cve.circl.lu/api/
- Retry logic with exponential backoff
- PID file management for daemon mode
- Configurable timeout and retry counts
- Health monitoring via `/ping` HTTP endpoint

### 3.3 Data & Infrastructure Layer

#### 3.3.1 Vertex AI RAG Engine (`src/rag/pipeline.py`)
**Purpose**: Core RAG implementation using Google Cloud Vertex AI

**Features**:
- Document ingestion from GCS with metadata extraction
- Configurable chunking with size and overlap parameters
- Vector embeddings using default Vertex AI embedding model
- Reranking capability with Discovery Engine
- Time-based filtering and metadata queries
- Duplicate prevention and tracking

**Configuration**:
- Chunk size: 512 tokens (configurable)
- Chunk overlap: 100 tokens (configurable)  
- Distance threshold: 0.6 (configurable)
- Top-K results: 5 (configurable)
- Reranking: Optional with Discovery Engine integration

**Implementation Details**:
- `VertexRagPipeline` class manages entire RAG lifecycle
- Cloud-based tracking of ingested documents (with local fallback)
- Metadata extraction from filenames (dates, document types)
- Batch ingestion support (25 documents per batch limit)
- Direct RAG response method combining retrieval and generation
- Context storage in `last_contexts` for display purposes

#### 3.3.2 Google Cloud Storage Integration (`src/rag/gcs_utils.py`)
**Purpose**: Document storage and management

**Capabilities**:
- Document upload and organization
- Metadata tracking and versioning
- Prefix-based document organization
- Cloud-based ingestion tracking

#### 3.3.3 External APIs
- **CVE Database**: Real-time vulnerability intelligence via cve.circl.lu
- **Tavily Search API**: Web intelligence gathering
- **Google Cloud Services**: Vertex AI, RAG Engine, GCS

## 4. Data Flow Architecture

### 4.1 Query Processing Flow

```
User Query
    │
    ▼
Orchestrator Agent
    │
    ▼
Planner Agent ──► Research Plan
    │
    ▼
Research Agent
    │
    ├──► RAG Query Tool ──► Vertex AI RAG Engine ──► Document Corpus
    │
    ├──► Web Search Tool ──► Tavily API ──► Web Intelligence  
    │
    └──► CVE Lookup Agent ──► MCP Server ──► CVE Database
    │
    ▼
Research Findings
    │
    ▼
Analysis Agent ──► Vulnerability Analysis Tool
    │
    ▼
Final Security Report
```

### 4.2 MCP Communication Flow

```
CVE Lookup Agent
    │
    ▼
MCP Client ──► SSE Transport ──► MCP Server ──► CVE API
    │                              │
    ▼                              ▼
Response Processing           Health Monitoring
    │                              │
    ▼                              ▼
Formatted Results             Connection Management
```

### 4.3 RAG Document Pipeline

```
Document Sources (GCS)
    │
    ▼
Document Ingestion ──► Metadata Extraction
    │                      │
    ▼                      ▼
Chunking Process ──► Vector Embeddings ──► RAG Corpus
    │                                          │
    ▼                                          ▼
Tracking & Deduplication              Query & Retrieval
```

## 5. Security Architecture

### 5.1 Authentication & Authorization
- Google Cloud IAM for service authentication
- Service account key management
- API key security for external services
- Environment variable protection

### 5.2 Data Security
- Encrypted communication via HTTPS/WSS
- Secure credential storage
- Document access control via GCS IAM
- Audit logging for security events

### 5.3 Network Security
- CORS configuration for web interfaces
- Rate limiting on API endpoints
- Request validation and sanitization
- Health monitoring and alerting

## 6. Scalability & Performance

### 6.1 Horizontal Scaling
- Stateless agent design enables multiple instances
- MCP server clustering for high availability
- Load balancing for concurrent queries
- Auto-scaling based on workload

### 6.2 Performance Optimization
- Lazy loading of pipeline resources
- Connection pooling for external APIs
- Caching of frequently accessed data
- Timeout management and circuit breakers

### 6.3 Resource Management
- Configurable timeouts and retry logic
- Memory-efficient document processing
- Graceful degradation under load
- Resource cleanup and garbage collection

## 7. Deployment Architecture

### 7.1 Cloud Deployment
- Google Cloud Platform as primary infrastructure
- Container-based deployment with Docker
- Cloud Build for CI/CD pipeline
- Scheduled ingestion via Cloud Scheduler

### 7.2 Local Development
- Docker Compose for local environment
- Environment variable configuration
- Local MCP server for development
- CLI interface for testing

### 7.3 Monitoring & Observability
- Structured logging with configurable levels
- Health check endpoints for monitoring
- Performance metrics collection
- Error tracking and alerting

## 8. Integration Points

### 8.1 External Systems
- **Vertex AI RAG Engine**: Core document intelligence
- **CVE Databases**: Real-time vulnerability data via cve.circl.lu
- **Web Search APIs**: Current threat intelligence via Tavily
- **Google Cloud Services**: Storage, compute, and AI

### 8.2 User Interfaces

#### 8.2.1 Command Center (`zero_day_hq.py`)
- Main entry point offering choice between RAG and Agent systems
- Rich terminal UI with colored output and menus
- Direct launch options via --rag or --agent flags
- Signal handling for graceful shutdown

#### 8.2.2 Scout CLI (`src/apps/scout_cli.py`)
- Agentic RAG interface with sequential workflow
- Query enhancement and suggestion features
- Execution plan preview before processing
- Real-time agent status updates
- Markdown export (automatic or manual)
- Commands: /help, /examples, /suggest, /enhance, /export, /agents, /rag, /plan

#### 8.2.3 RAG CLI (`src/apps/rag_cli.py`)
- Direct RAG interface for simple retrieval
- Corpus management commands
- Document ingestion and tracking
- Interactive and single-query modes

### 8.3 Data Formats
- **Input**: PDF, text, markdown documents from GCS
- **Processing**: JSON metadata, vector embeddings
- **Output**: Markdown reports with structured sections
- **Configuration**: Environment variables, config files
- **Tracking**: JSON files for ingested documents and metadata

## 9. Quality Attributes

### 9.1 Reliability
- Fault tolerance with automatic retry logic
- Graceful error handling and recovery
- Health monitoring and self-healing
- Data consistency and integrity

### 9.2 Maintainability
- Modular architecture with clear separation of concerns
- Comprehensive logging and debugging capabilities
- Configuration management and environment abstraction
- Automated testing and validation

### 9.3 Usability
- Intuitive CLI and web interfaces
- Comprehensive documentation and examples
- Error messages with actionable guidance
- Export capabilities for analysis results

## 10. Implementation Technologies

### 10.1 Core Technologies
- **Language**: Python 3.x
- **AI/ML Framework**: Google Vertex AI, Google ADK
- **Web Framework**: Starlette/FastAPI for MCP server
- **CLI Framework**: Rich for terminal UI
- **Async Support**: asyncio for concurrent operations

### 10.2 Key Libraries
- **google-cloud-aiplatform**: Vertex AI integration
- **vertexai**: RAG and generative model APIs
- **mcp**: Message Communication Protocol implementation
- **requests**: HTTP client for external APIs
- **uvicorn**: ASGI server for MCP endpoints

### 10.3 Configuration Management
- **Environment Variables**: Primary configuration method
- **Config Manager**: Centralized configuration loading
- **Constants Module**: Default values and settings
- **CLAUDE.md**: Project-specific instructions and documentation

## 11. Future Architecture Considerations

### 11.1 Extensibility
- Plugin architecture for new tools and agents
- Custom model integration capabilities
- Additional data source connectors
- Enhanced export and visualization options

### 11.2 Advanced Features
- Multi-tenant support for enterprise deployment
- Advanced caching and indexing strategies
- Real-time collaboration capabilities
- Enhanced security analysis algorithms

### 11.3 Potential Improvements
- Implement caching layer for frequently accessed CVE data
- Add support for additional vulnerability databases
- Enhance time-based filtering with full metadata support
- Implement agent memory for context retention across queries
- Add support for batch processing of multiple queries
- Create web API endpoints for programmatic access

This architecture provides a robust foundation for security intelligence gathering while maintaining flexibility for future enhancements and scalability requirements. The modular design allows for easy extension and modification of individual components without affecting the overall system stability.