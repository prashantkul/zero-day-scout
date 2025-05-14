# Zero-Day Scout CLI Tool

A visually enhanced command-line interface for interacting with the Zero-Day Scout RAG pipeline, featuring progress tracking, performance metrics, query suggestions, and document management functionality.

## Features

- **Interactive UI**: Beautiful terminal-based interface with color-coded elements
- **Step-by-step progress tracking**: Visual feedback for each stage of the RAG process
- **Query suggestions**: AI-powered suggestions to improve your search queries
- **Real-time progress indicators**: Live updates during query processing
- **Animated splash screen**: Professional application launch experience
- **Command history**: Track and revisit previous queries
- **Markdown formatting**: Responses rendered with proper markdown formatting
- **Context visualization**: View retrieved documents when answers are limited
- **Debug and verbose modes**: Detailed information about internal processing 
- **Smart response handling**: Special handling for cases with limited information
- **Document management**: View and track research papers and ingested documents
- **Ingestion tracking**: Identify which documents have been ingested and which are pending

## Installation

Before using this tool, ensure you have the required dependencies:

```bash
pip install rich
```

The tool uses the existing Zero-Day Scout configuration system, so make sure your environment is properly set up as described in the main README.

## Usage

### Interactive Mode

For an interactive session with a splash screen:

```bash
python -m src.apps.rag_cli
```

With reranking enabled:

```bash
python -m src.apps.rag_cli --reranking
```

Skip the splash screen:

```bash
python -m src.apps.rag_cli --no-splash
```

### Single Query Mode

To run a single query:

```bash
python -m src.apps.rag_cli --query "What are the latest zero-day vulnerabilities in cloud systems?"
```

With reranking and query suggestions:

```bash
python -m src.apps.rag_cli --query "What are the latest zero-day vulnerabilities?" --reranking --suggest
```

### Document Management Commands

#### Listing Documents

List all research papers in GCS:

```bash
python -m src.apps.rag_cli --papers
```

List research papers with detailed information:

```bash
python -m src.apps.rag_cli --papers-detailed
```

List research papers from a specific prefix:

```bash
python -m src.apps.rag_cli --papers-prefix "uploaded_papers/"
```

List ingested documents:

```bash
python -m src.apps.rag_cli --ingested
```

#### Ingesting Documents

Ingest documents from all configured prefixes:

```bash
python -m src.apps.rag_cli --ingest-all
```

Ingest documents from a specific prefix:

```bash
python -m src.apps.rag_cli --ingest-prefix "uploaded_papers/"
```

Ingest specific documents:

```bash
python -m src.apps.rag_cli --ingest-paths "gs://rag-research-papers/paper1.pdf" "gs://rag-research-papers/paper2.pdf"
```

### Advanced Usage Options

```bash
# Debug mode (shows detailed information)
python -m src.apps.rag_cli --debug

# Verbose mode (shows detailed context information)
python -m src.apps.rag_cli --verbose

# Combine options
python -m src.apps.rag_cli --query "What are zero-day vulnerabilities?" --reranking --debug --verbose
```

### Available Commands in Interactive Mode

- Type your query and press Enter to run it
- Type `help` to see all available commands
- Type `suggestions` to see improvements for your last query
- Type `history` to view previous queries
- Type `papers` to list research papers in GCS
- Type `papers detailed` to view detailed information about available papers
- Type `papers <prefix>` to list papers from a specific prefix (e.g., `papers uploaded_papers/`)
- Type `ingested` to list all ingested documents
- Type `ingest all` to ingest documents from all configured prefixes
- Type `ingest prefix <prefix>` to ingest documents from a specific prefix
- Type `ingest gs://<path>` to ingest specific document(s)
- Type `reranking` to toggle reranking on/off
- Type `debug` to toggle debug mode on/off
- Type `verbose` to toggle verbose mode on/off
- Type `clear` to clear the screen
- Type `exit` or `quit` to exit the program

### Splash Screen Controls

- When the splash screen appears, you can:
  - Press Enter to continue to the application
  - Press Ctrl+C to exit immediately
  
### Context Visualization

When the RAG engine can't find enough information to answer a query:

1. The tool automatically displays the retrieved contexts
2. Response is shown with a yellow border instead of green
3. The tool explains what was found and why it might not be sufficient
4. Query suggestions are offered to help refine the search

## Visual Features

### Step Tracking
The CLI shows a real-time progress table with the following steps:
1. **Initializing RAG pipeline** - Connecting to Vertex AI
2. **Embedding query** - Converting your query to vector embeddings
3. **Retrieving relevant documents** - Finding matching content
4. **Ranking/Reranking results** - Prioritizing the most relevant information
5. **Generating response** - Creating the final answer


### Splash Screen and Branding
The CLI features distinctive visual branding:
- Persistent ASCII art logo for Zero-Day Scout remains visible throughout your session
- Animated splash screen with loading progress indicators
- Interactive initialization sequence that waits for user input
- Consistent branding across all modes (interactive and single query)

### Reranking Information
The CLI explains reranking benefits and offers to enable it when:
- The tool is launched without the `--reranking` flag
- A query is entered in single query mode without reranking

Reranking benefits explained:
1. **Improving relevance** - Reordering results based on semantic meaning
2. **Reducing false positives** - Filtering out less relevant matches
3. **Handling nuanced queries** - Better understanding of complex questions
4. **Contextual understanding** - Considering the full context of your query

## How It Works

The CLI tool integrates with the existing `VertexRagPipeline` and adds:

1. Rich text UI using the `rich` library for beautiful console output
2. Real-time progress tracking for each step of the RAG process
3. Query improvement suggestions using the same Generative AI model
4. Interactive workflow with multiple command options
5. Visual performance analysis to understand query processing

Each query result is presented with detailed performance metrics and formatted response content, and the tool offers query suggestions after each search to help refine your exploration.