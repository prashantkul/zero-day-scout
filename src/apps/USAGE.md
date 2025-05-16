# Zero-Day Scout CLI - Quick Reference

## Basic Usage

```bash
# Interactive mode
python src/apps/scout_cli.py

# Query mode
python src/apps/scout_cli.py --query "What are the latest zero-day vulnerabilities in Apache Struts?"
```

## Command-line Arguments

| Argument | Description |
|----------|-------------|
| --query, -q | Specify a query to process |
| --model, -m | Set the model to use (default: gemini-2.5-flash-preview-04-17) |
| --enhance, -e | Automatically enhance the query |
| --no-enhancement, -n | Skip query enhancement |
| --no-rag | Hide RAG source information |
| --no-plan | Hide execution plan preview |
| --export-pdf | Automatically export results to PDF |
| --no-sources | Exclude research sources from PDF export |
| --verbose, -v | Enable verbose output |
| --debug, -d | Enable debug logging |

## Interactive Commands

| Command | Description |
|---------|-------------|
| /help | Show available commands |
| /examples | Show example security queries |
| /exit, /quit | Exit the application |
| Ctrl+C | Interrupt operation or exit |
| /suggest | Get query improvement suggestions |
| /enhance | Enhance last query for better results |
| /debug | Toggle debug logging |
| /verbose | Toggle verbose logging |
| /agents | Show agent workflow structure |
| /rag | Toggle RAG information display |
| /plan | Toggle execution plan display |
| /export | Export current results to PDF |
| /export auto | Toggle automatic PDF export |
| /clear | Clear the screen |

## Agent Workflow

1. **Planning**: Analyzes your query and creates a structured research plan
2. **Research**: Retrieves relevant information from the security knowledge base
3. **Analysis**: Evaluates findings to provide actionable security insights

## Example Queries

- "What are the latest zero-day vulnerabilities in Apache Struts?"
- "How can organizations protect against Log4Shell vulnerabilities?"
- "What are common exploit techniques for SQL injection?"
- "How can I detect if my system has been compromised by a zero-day exploit?"
- "What security vulnerabilities affect Docker containers?"

## Tips

- Use query enhancement for more focused results
- Review the execution plan before proceeding
- Check research sources to evaluate information quality
- Use `/suggest` after a query to get improvement ideas
- Press Ctrl+C to cancel a long-running query
- Use `/export` to save important results as PDF reports