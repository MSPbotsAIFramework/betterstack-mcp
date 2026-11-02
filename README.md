# betterstack-mcp

MCP server for [BetterStack](https://betterstack.com) Uptime monitoring and
Incident management, built for the MSPbots Agent platform. It lets an Agent
list and manage uptime monitors, list and triage incidents (acknowledge /
resolve), and see on-call schedules -- who is on call, and when.

Transport: MCP Streamable HTTP (`POST /mcp`), stateless, one container
instance serving many tenants concurrently. Stack: Python 3.12, FastMCP,
httpx. License: Apache-2.0.

---

<div align="center">

## MSPbots Connector

**The MCP Gateway built for MSPs: visible, controlled, and your data stays where it belongs.**

[**Get started at connect.mspbots.ai →**](https://connect.mspbots.ai)

</div>

---

MSPbots Connector gives your AI clients one MCP URL to reach your entire MSP stack (RMM, PSA, documentation, security, finance), and gives you control over who can call which tool and a record of everything that was called.

**Hosted service: [connect.mspbots.ai](https://connect.mspbots.ai)** · Free to use.

### Why Connector

![MSPbots Connector](https://stgoss.mspbots.ai/files/mcp/mspbots-mcp.png)

| | |
|---|---|
| **Visible** | Every tool call is logged: who, which vendor, when. Usage dashboard, CSV export, SIEM streaming. |
| **Controlled** | Role-based, per-tool allowlist. Deny by default. |
| **Protected** | Credentials encrypted per record. AI clients never see your vendor passwords or tokens. |
| **MSP-native** | Built for the MSP stack only: RMM, PSA, documentation, security, finance. |

### Quick start

1. **Sign up** at [connect.mspbots.ai](https://connect.mspbots.ai).
2. **Connect your vendors.** Pick from 150+ connectors and authorize each one on the vendor's own page, or bring your own API keys. No extra vendor accounts needed.
3. **Set access.** Create roles and decide which tools each role may call. Nothing is allowed until you allow it.
4. **Add your MCP URL to your AI client.** Copy the URL from your Connector dashboard into Claude, ChatGPT, Cursor, VS Code, Gemini, Codex, or any MCP-capable client.
5. **Ask your AI to do real work**, and watch every call appear in the audit log.

### Features

**Unified gateway**
- One MCP URL for all your AI clients
- 150+ connectors across the MSP stack
- Custom MCP servers supported, free
- Authorization happens on each vendor's own page; the AI never sees passwords or tokens
- Bring your own credentials: use the vendor API keys you already have
- Multiple accounts per app; connect once, reuse across AI clients
- Tool search: finds the right action for the task
- One sign-in; vendor credentials are injected behind the scenes and OAuth tokens refresh automatically

**Visibility**
- Audit log for every tool call (who, which vendor, when)
- Usage dashboard: call volume, top vendors, error rate, per-user activity
- Export audit logs to CSV, or stream to Loki, Graylog, or LogScale (SIEM)
- Optional recording of tool arguments and result summaries (off by default, enabled per organization)

**Control**
- Per-role, per-tool allowlist, deny by default
- owner / admin / member roles
- SCIM provisioning with Entra ID, Okta, JumpCloud, and Google Workspace

**Security**
- Credentials encrypted one record at a time (AES-256-GCM, per-record key)
- AI clients authenticate with OAuth 2.1 + PKCE
- Vendor responses are scanned for prompt-injection patterns and returned as structured data. This is one layer of defense, not a guarantee against every attack.
- Static egress IP for customer firewall and API allowlisting

### Pricing

**Free.**

Links: [connect.mspbots.ai](https://connect.mspbots.ai) · [mspbots.ai](https://mspbots.ai)

---

## Authentication headers

Every `/mcp` request must carry the tenant's BetterStack credential in an HTTP header -- never an environment variable, never a config file.

| Header | Required | Meaning | Where to get it |
|---|---|---|---|
| `X-Betterstack-Api-Token` | Yes | BetterStack API token (Global API token, or a team-scoped Incidents/Uptime API token), forwarded as `Authorization: Bearer <token>` | BetterStack dashboard -> Settings -> API tokens |
| `X-Betterstack-Base-Url` | No | Override the Uptime/Incidents API base URL. Default: `https://uptime.betterstack.com/api/v2` | -- (forward-compatible headroom; BetterStack is single-region SaaS today) |

A request with no `X-Betterstack-Api-Token` header gets `HTTP 401` listing the required header name; no tool runs.

## Tools

11 tools across 3 resource groups. `list_*` tools default to `limit=50`, hard-capped at `200`; all read tools are annotated read-only, `betterstack_delete_monitor` is destructive, `betterstack_acknowledge_incident`/`betterstack_resolve_incident` are idempotent.

| Tool | What it does |
|---|---|
| `betterstack_list_monitors` | List uptime monitors, optionally filtered by URL or name. |
| `betterstack_get_monitor` | Get one monitor's detail by id. |
| `betterstack_create_monitor` | Create a new uptime monitor for a URL. |
| `betterstack_update_monitor` | Update a monitor's settings, including pause/resume via `paused`. |
| `betterstack_delete_monitor` | Delete a monitor by its id. Irreversible; no bulk/filter delete. |
| `betterstack_list_incidents` | List incidents, optionally filtered by monitor, status, or date range. |
| `betterstack_get_incident` | Get one incident's detail by id. |
| `betterstack_acknowledge_incident` | Acknowledge an incident to claim it for triage. |
| `betterstack_resolve_incident` | Resolve an incident, closing out the triage loop. |
| `betterstack_list_oncall_schedules` | List on-call schedules (id and name). |
| `betterstack_list_oncall_events` | List who is on call for a schedule, in a given time window. |

**Scope (v1)**: BetterStack Logs/Telemetry capabilities are not built in this version -- only the Uptime/Incidents-API surface (monitors, incidents, on-call) that the connecting ticket named. On-call is read-only; editing rotations stays in BetterStack's own UI for now. See `docs/tickets/PRD-21258.md` ("Decisions made by DEV01") for the full reasoning.

## Local development

```bash
uv sync
uv run pytest

# Run the server
uv run python -m betterstack_mcp   # listens on 0.0.0.0:8080 by default

# Exercise it with a real BetterStack token
curl -X POST http://localhost:8080/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -H 'X-Betterstack-Api-Token: <your token>' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

```bash
docker build --platform linux/amd64 -t betterstack-mcp:dev .
```
