# Siyin Cloud Print MCP Server

An MCP (Model Context Protocol) server that brings the **Siyin Cloud Print System** (司印云打印) into the LLM ecosystem — upload documents to a print queue with a single natural-language instruction.

> **Note:** This MCP is designed for **on-premises / intranet environments**. The Siyin print API is not reachable from the public internet, so this server runs locally (stdio) or on the customer's own intranet (streamable-http / SSE).

## Features

- Standard MCP server, callable from CodeBuddy, Claude Desktop, Cursor, WorkBuddy, and any MCP client
- Default **stdio** transport — runs on the user's machine, so it can reach the intranet print server
- Also supports **streamable-http / SSE** for centralized intranet deployment
- All connection parameters via environment variables or tool arguments; **no hard-coded intranet addresses**
- Automatic MIME detection: Word / Excel / PowerPoint / PDF / images
- **Passwordless printing** (requires "Skip password check" enabled in Siyin admin)

## Tools

### `upload_document`

| Argument | Description |
|----------|-------------|
| `file_path` | Absolute path to the local file (required) |
| `doc_name` | Display name; defaults to the file name |
| `color` | `Color` / `Mono` |
| `copy` | Number of copies (string) |
| `duplex` | `1` one-sided / `2` short-edge / `3` long-edge |
| `paper_size` | A3 / A4 / A5 (applies to images and PDF) |
| `collate` | `0` / `1` |

Connection arguments (`protocol`, `host`, `port`, `uri`, `login_account`, `login_domain`, `printer_queue`, `solutionkey`) fall back to `SIYIN_*` environment variables.

### `check_server`

Probes server connectivity without uploading anything.

## Installation

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Configuration

```bash
cp .env.example .env
```

Then edit `.env`:

| Variable | Description |
|----------|-------------|
| `SIYIN_HOST` | Siyin server IP |
| `SIYIN_PORT` | Port (default 8110) |
| `SIYIN_SOLUTIONKEY` | Solution key issued by Siyin |
| `SIYIN_PRINTER_QUEUE` | Printer queue ID |
| `SIYIN_LOGIN_ACCOUNT` | Login account |

## Usage

### stdio (recommended for intranet)

```bash
python server.py
```

MCP client configuration:

```json
{
  "mcpServers": {
    "siyin-cloud-print": {
      "command": "python",
      "args": ["/absolute/path/to/siyin-cloud-print/server.py"]
    }
  }
}
```

### streamable-http / SSE

```bash
python server.py --transport streamable-http --host 0.0.0.0 --port 9000
python server.py --transport sse --host 0.0.0.0 --port 9000
```

Endpoints: `/mcp` (streamable-http) and `/sse` (SSE).

Then just ask your AI assistant:

> "Upload `D:/docs/report.docx` to Siyin, color, A4, 3 copies, double-sided."

## License

MIT — see [LICENSE](./LICENSE).
