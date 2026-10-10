# VerifyWise MCP client example

A runnable Python 3.10+ repository with no third-party dependencies. Connects to
VerifyWise's documented MCP gateway at `/v1/mcp`, lists available tools and calls
a tool using its discovered name and input schema. No OpenAI API key is needed.

## What this connects to

The client calls the VerifyWise gateway; the gateway forwards approved calls to
registered backend MCP servers. A gateway connection does not itself expose
VerifyWise projects, risks, or evidence. Those require backend tools that call
your running VerifyWise instance's API.

The included `demo_server.py` is a separate backend with fictional sample data.
It does not connect to your VerifyWise database or API.

## 1. Try it locally

Unzip the archive, open a terminal in `verifywise-mcp-client`, and run:

```bash
python demo_server.py
```

In a second terminal in the same directory:

```bash
python client.py --demo list
python client.py --demo call demo_list_projects --args '{}'
```

The call returns a text content block containing a sample project with ID
`demo-1`. Stop the server with Ctrl+C. On Windows, `py` may be used instead of
`python`; on some Linux/macOS systems use `python3`.

## 2. Configure your VerifyWise gateway

In a VerifyWise version/deployment with MCP Gateway enabled:

1. Open **AI Gateway > Agent Control > MCP Servers** and register a backend MCP
   endpoint reachable from the gateway. Configure backend credentials there.
2. Discover the backend tools and review their risk/approval settings.
3. Open **Agent keys** and create a scoped key permitting the tools you need.
4. Copy the key when created and set the environment variables below.

To route the sample backend through your gateway, register its reachable
`/mcp` endpoint. The demo binds only to loopback: the gateway must run on the
same host/network context, or you must use an authenticated deployment of a
backend. `127.0.0.1` inside a container refers to that container, not your laptop.
The demo is intentionally local and is not suitable for public deployment.

Linux/macOS:

```bash
export VERIFYWISE_MCP_URL='https://your-verifywise-host/v1/mcp'
read -r -s -p 'VerifyWise agent key: ' VERIFYWISE_AGENT_KEY
echo
export VERIFYWISE_AGENT_KEY
python client.py list
```

PowerShell:

```powershell
$env:VERIFYWISE_MCP_URL = 'https://your-verifywise-host/v1/mcp'
$secret = Read-Host 'VerifyWise agent key' -AsSecureString
$env:VERIFYWISE_AGENT_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
python client.py list
```

`.env.example` documents the settings. The client reads process environment
variables; it does not automatically load a `.env` file. Never commit real keys.

## 3. Call a discovered tool

Inspect `list` output for the exact tool name and `inputSchema`. Gateway tool
names may differ from direct backend names. If the demo tool appears under its
original name, call it with:

```bash
python client.py call demo_list_projects --args '{}'
```

For any other tool, replace the name and JSON arguments with values from its
schema. The CLI prints the complete MCP result, including content blocks and
`isError`. A tool error exits with status 2; a connection failure exits with 1.

## 4. Expose real VerifyWise application data

Build or register a backend MCP server with a tool such as `list_projects`.
Inside that tool, use an authenticated VerifyWise API client to call the
documented project-list endpoint for **your deployed version**, then return a
bounded, sanitized result as MCP tool content. Verify the endpoint, request
schema, authentication method, and organization permissions using your
instance's API reference. This repository does not invent an endpoint or assume
your application token is the same as the gateway agent key.

Store the VerifyWise application API credential on the backend. Register the
backend with the gateway, discover its tool, then call its discovered name using
this client. Backend tools are also the place to implement pagination and data
filters for the application's API. Prefer starting with read-only tools.

## Approval and troubleshooting

- **No tools:** Check backend registration/discovery and the agent key ACL.
- **401/403:** Check whether the key is active, scoped correctly, and unexpired.
- **404:** Confirm your gateway base URL and that the deployed version has MCP
  Gateway enabled. An expired MCP session requires a fresh client invocation.
- **Approval required:** The client prints the JSON-RPC error, including gateway
  approval details when provided. Review the request in VerifyWise Approvals.
  Follow your deployed gateway's status/resume contract; do not assume replaying
  a tool call resumes it. This example does not poll approvals or replay calls.
- **Network/TLS:** Use a valid HTTPS certificate and a host reachable from the
  client. Redirects are rejected so credentials are not forwarded to another URL.

No automatic retries are performed: a timeout can occur after a tool has run.
Check gateway activity before rerunning a call that changes data.

## Implementation scope and validation

Supports protocol version `2025-03-26`, initialization, initialized notification,
JSON and POST SSE responses, session headers, paginated tool discovery, calls,
and best-effort session cleanup. This intentionally small synchronous example
does not support legacy SSE transport, OAuth, stream resumption, sampling,
server-initiated requests, or automatic session recovery. Use the official MCP
SDK for a broader production implementation.

Run the included local integration and transport checks:

```bash
python -m unittest discover -s tests -v
```

Verified against the included demo server, not a live VerifyWise instance.
No live host or credentials were supplied.

## Sources

- https://verifywise.ai/user-guide/ai-gateway/mcp-overview
- https://verifywise.ai/user-guide/ai-gateway/mcp-agent-keys
- https://verifywise.ai/api-docs
- https://modelcontextprotocol.io/specification/2025-03-26/basic/transports
- https://modelcontextprotocol.io/specification/2025-03-26/basic/lifecycle
- https://github.com/modelcontextprotocol/python-sdk

Documentation reviewed 2026-10-10. Verify deployment-specific behavior before
connecting to real data.
