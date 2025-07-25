# Zero-Day Scout CLI

An agentic RAG system for security vulnerability research with a powerful command-line interface.

![Zero-Day Scout Logo](https://img.shields.io/badge/Zero--Day-Scout-red)
![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-green)

## Overview

Zero-Day Scout is an advanced security research assistant that combines Large Language Models with Retrieval-Augmented Generation (RAG) to help you investigate security vulnerabilities, zero-day exploits, and threat intelligence. The system uses a sequential agent workflow to deliver comprehensive security insights with documented sources.

## Features

- **Three-Stage Agent Workflow**:
  - 🧠 **Planning** - Analyzes your query and develops a structured research plan
  - 🔍 **Research** - Retrieves relevant information from security knowledge base
  - 📊 **Analysis** - Evaluates findings to provide actionable security insights

- **Advanced RAG Integration**:
  - Integration with Google Vertex AI RAG for document retrieval
  - Transparent source documentation with relevance scores
  - Support for reranking to improve result quality

- **User-Friendly Interface**:
  - Interactive command-line with rich formatting
  - Query enhancement for better results
  - Execution plan preview before processing
  - Keyboard shortcuts for efficient workflow

## Installation

### Prerequisites

- Python 3.11+
- Google Cloud account with Vertex AI access
- Permission to use Vertex AI Generative AI models

### Environment Setup

1. Clone the repository:
   ```bash
   git clone [repository-url]
   cd zero-day-scout
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables - copy the template and add your credentials:
   ```bash
   cp .env.template .env
   # Edit .env file with your Google Cloud settings
   ```

## Usage

### Basic Command

```bash
python src/apps/scout_cli.py
```

This will start the interactive CLI mode with a user-friendly interface.

### Command-line Arguments

```bash
# Run with a specific query
python src/apps/scout_cli.py --query "What are the latest zero-day vulnerabilities in Apache Struts?"

# Specify a different model
python src/apps/scout_cli.py --model "gemini-2.5-flash-pro-preview-04-17"

# Automatically enhance the query
python src/apps/scout_cli.py --enhance

# Skip query enhancement
python src/apps/scout_cli.py --no-enhancement

# Hide RAG source information
python src/apps/scout_cli.py --no-rag

# Hide execution plan
python src/apps/scout_cli.py --no-plan

# Enable verbose output
python src/apps/scout_cli.py --verbose

# Enable debug logging
python src/apps/scout_cli.py --debug
```

### Interactive Commands

In interactive mode, the following commands are available:

| Command | Description |
|---------|-------------|
| /help | Show available commands |
| /examples | Show example security queries |
| /exit, /quit | Exit the application |
| Ctrl+C | Interrupt current operation or exit |
| /suggest | Get query improvement suggestions |
| /enhance | Enhance your last query for better results |
| /debug | Toggle debug logging |
| /verbose | Toggle verbose logging |
| /agents | Show agent structure and workflow |
| /rag | Toggle RAG information display |
| /plan | Toggle execution plan display |
| /clear | Clear the screen |

## Workflow

1. **Query Input** - Enter your security research question
2. **Query Enhancement** - Optionally improve your query for better results
3. **Execution Plan** - Preview how your query will be processed
4. **Agent Processing**:
   - Planning stage
   - Research stage (with document retrieval)
   - Analysis stage
5. **Results Display**:
   - Research Plan
   - Research Findings (with source references)
   - Security Analysis
   - Final Analysis

## Examples

Here are some example queries to get you started:

- "What are the latest zero-day vulnerabilities in Apache Struts?"
- "How can organizations protect against Log4Shell vulnerabilities?"
- "What are the common exploit techniques for SQL injection?"
- "How can I detect if my system has been compromised by a zero-day exploit?"
- "What security vulnerabilities affect Docker containers?"

## Advanced Configuration

### Google Cloud Setup

This tool requires proper Google Cloud configuration. Ensure you have:

- Enabled Vertex AI API in your project
- Created a service account with Vertex AI access
- Downloaded service account credentials
- Set `GOOGLE_APPLICATION_CREDENTIALS` to the credential file path

### Environment Variables

Key environment variables include:

- `GOOGLE_CLOUD_PROJECT` - Your Google Cloud project ID
- `GOOGLE_CLOUD_LOCATION` - Cloud region (e.g., us-central1)
- `GOOGLE_APPLICATION_CREDENTIALS` - Path to service account key file
- `RAG_CORPUS_NAME` - Name of your RAG corpus
- `RAG_GENERATIVE_MODEL` - Model to use (e.g., gemini-2.5-flash)

## Troubleshooting

### Common Issues

- **Authentication Errors**: Check your Google Cloud credentials
- **RAG Retrieval Failures**: Ensure your corpus is properly set up
- **Slow Response Times**: Try using a different model or reducing the query complexity

### Debug Mode

Run with the `--debug` flag to see detailed diagnostic information:

```bash
python src/apps/scout_cli.py --debug
```

## License

This project is licensed under the [insert license] - see the LICENSE file for details.

## Acknowledgments

- Google Agent Development Kit (ADK) for agent framework
- Vertex AI for generative models and RAG capabilities
- Rich library for terminal formatting