# CVE MCP Client CLI

A beautiful command-line interface for interacting with the CVE MCP Server to search and retrieve vulnerability information.
The MCP server uses https://www.circl.lu/services/cve-search/ as the backend API.

## Features

- 🎨 Beautiful terminal UI with colored output
- 🔍 Search CVEs by ID (e.g., CVE-2021-44228)
- 📋 Get latest CVEs from the database
- 🏢 Search vulnerabilities by vendor and product
- 📊 View database update status
- 🌐 Test server connectivity
- 💻 Both interactive and single-command modes

## Usage

### Interactive Mode

Simply run the CLI without arguments to enter interactive mode:

```bash
python src/cve_mcp/cve_cli.py
```

Or if you're in the `src/cve_mcp` directory:

```bash
./cve_cli.py
```

### Single Command Mode

Execute specific commands directly:

```bash
# Search for a specific CVE
python src/cve_mcp/cve_cli.py --cve CVE-2021-44228

# Get latest CVEs
python src/cve_mcp/cve_cli.py --latest

# Search by vendor and product
python src/cve_mcp/cve_cli.py --vendor microsoft --product windows_10

# List all vendors
python src/cve_mcp/cve_cli.py --vendors

# List products for a vendor
python src/cve_mcp/cve_cli.py --vendor apache

# Check database status
python src/cve_mcp/cve_cli.py --status

# Test server connection
python src/cve_mcp/cve_cli.py --ping
```

### Connection Options

By default, the CLI connects to `localhost:8080`. You can specify a different server:

```bash
python src/cve_mcp/cve_cli.py --host 192.168.1.100 --port 8000
```

## Interactive Mode Commands

When running in interactive mode, you'll see a menu with these options:

1. **Search CVE by ID** - Look up a specific CVE (e.g., CVE-2021-44228)
2. **Get latest CVEs** - Display the most recent vulnerabilities
3. **Search by vendor/product** - Find CVEs for specific software
4. **List all vendors** - Show all vendors in the database
5. **List products for a vendor** - Show products for a specific vendor
6. **Database update status** - Check when the CVE database was last updated
7. **Test server connection** - Verify connectivity to the MCP server
8. **Quit** - Exit the application

## Display Features

### CVE Details
- Color-coded CVSS severity scores:
  - 🔴 Critical (9.0-10.0) - Red
  - 🟠 High (7.0-8.9) - Orange
  - 🟡 Medium (4.0-6.9) - Yellow
  - 🟢 Low (0.0-3.9) - Green

### CVE Lists
- Tabular format with CVE ID, CVSS score, publication date, and summary
- Automatic truncation of long summaries
- Shows first 20 results with total count

### Vendor Lists
- Multi-column display for efficient space usage
- Alphabetically sorted
- Shows total count

## Prerequisites

1. The CVE MCP Server must be running:
   ```bash
   ./start_cve_mcp_server.sh start
   ```

2. Required Python packages:
   ```bash
   pip install rich
   ```

## Error Handling

The CLI provides clear error messages for common issues:
- Server connection failures
- Invalid CVE IDs
- Network timeouts
- Malformed responses

## Tips

1. Use partial CVE IDs - the CLI will search for matches
2. Vendor and product names are case-insensitive
3. Use Ctrl+C to cancel any operation in interactive mode
4. The CLI automatically formats and highlights important information

## Examples

### Finding Log4Shell Information
```bash
# Direct search
python src/cve_mcp/cve_cli.py --cve CVE-2021-44228

# Or in interactive mode:
# Select option 1, then enter: CVE-2021-44228
```

### Finding Apache Vulnerabilities
```bash
# List all Apache products
python src/cve_mcp/cve_cli.py --vendor apache

# Search for Apache Struts vulnerabilities
python src/cve_mcp/cve_cli.py --vendor apache --product struts
```

### Checking Latest Threats
```bash
# Get the 30 most recent CVEs
python src/cve_mcp/cve_cli.py --latest
```

## Integration with Zero-Day Scout

This CLI can be used standalone or as part of the Zero-Day Scout system for quick CVE lookups during security research.