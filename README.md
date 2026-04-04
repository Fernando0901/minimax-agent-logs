# MiniMax Telegram Agent — Project Documentation

> **Language rule:** English internally (code, comments, logs, docs). Spanish for Fernando's conversation.

---

## 1. Project Overview

**Name:** MiniMax Telegram Agent
**Owner:** Fernando Guadarrama — Vidrios y Aluminio Guadarrama
**VPS:** 31.97.211.181 (vag131999.cloud)
**Primary Model:** MiniMax-M2.7 via MiniMax API
**Secondary Model:** Claude Code CLI (for self-improvement tasks)
**GitHub:** `fernando0901/minimax-agent-logs`
**Last Updated:** 2026-04-04

Autonomous Telegram bot that handles Fernando's business operations using AI. The agent can hold conversations, query Odoo CRM, generate images, execute n8n workflows, and continuously self-improve.

---

## 2. Architecture Overview

```
Fernando (Telegram)
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  minimax-agent (Docker Container)                           │
│  python-telegram-bot v21+ async event loop                  │
│                                                             │
│  main.py ──► brain.py ──► MiniMax M2.7 API                 │
│     │           │                                           │
│     │           ├──► mcp_manager.py ──► MCP clients         │
│     │           ├──► odoo_bridge.py ──► Odoo FastAPI       │
│     │           └──► image_handler.py                      │
│     │                                                   │
│     ├──► self_improve.py ──► writes task ──► returns       │
│     │                                          │           │
│     └──► backup.py ──► GitHub push            │           │
│                                                   │           │
└──────────────────────────────────────────────────────────────┘
                                                   │
                    ┌────────────────────────────┘
                    ▼
        /root/agent-tasks/pending/
                    │
                    ▼
┌──────────────────────────────────────────────────────────────┐
│  task_watcher.py (systemd service — OUTSIDE Docker)         │
│  Polls every 5s. Executes Claude Code CLI with cwd=/root   │
│  Sends Telegram notifications on completion                 │
└──────────────────────────────────────────────────────────────┘
```

### Key Design Principle

**The Docker container NEVER calls Claude Code directly for self-fix tasks.** It writes a task file and returns immediately. The external `task_watcher` service handles execution. This prevents the container from being killed while modifying itself.

---

## 3. Directory Tree

```
/root/
├── agent-tasks/                    # Orchestrator task queue (EXTERNAL, not in Docker)
│   ├── pending/    *.md           # Tasks waiting to be executed
│   ├── completed/   *.md           # Successfully completed tasks
│   ├── failed/      *.md           # Failed tasks
│   └── learning/    *.json         # Error context for future corrections
│
├── scripts/                        # External scripts (outside Docker)
│   ├── task_watcher.py             # NEW: systemd file watcher service
│   ├── orchestrator.py             # Daily cron orchestrator (MiniMax brain)
│   ├── minimax-telegram-bot.py
│   ├── minimax_tools.py
│   ├── start-minimax-bot.sh
│   ├── start-orchestrator.sh
│   └── daily-update*.sh
│
├── logs/                          # Shared log directory (bind-mounted)
│   ├── agent.log                  # minimax-agent container logs
│   ├── task-watcher.log
│   └── orchestrator-*.log
│
├── .env                           # Environment variables (read by Docker)
│
└── minimax-agent/                  # Docker project root (/root/minimax-agent in container)
    ├── agent/
    │   ├── __init__.py
    │   ├── main.py                # Telegram bot entry + all handlers
    │   ├── brain.py               # MiniMax API + tool calling + intent classification
    │   ├── mcp_manager.py         # Dynamic MCP registry and tool routing
    │   ├── odoo_bridge.py        # FastAPI client for Odoo microservice
    │   ├── image_handler.py      # Vision + image generation via MiniMax media MCP
    │   ├── skill_loader.py       # YAML skill hot-loader
    │   ├── self_improve.py       # Claude Code CLI orchestration
    │   └── backup.py            # GitHub backup (daily + session learnings)
    │
    ├── skills/                    # YAML skill definitions (hot-reloadable)
    │   ├── greeting.yaml
    │   ├── odoo_search.yaml
    │   └── price_consultant.yaml
    │
    ├── mcps.json                  # Dynamic MCP registry (8 MCPs)
    │
    ├── memory/
    │   ├── conversation_store.json # Per-user conversation history
    │   ├── api_usage.json         # Rate limit tracking
    │   └── agent_memory.md        # Persistent learnings (last 100 lines injected into system prompt)
    │
    ├── tasks/                     # Claude Code improvement task files
    ├── improvements/               # Improvement plan + fix reports
    ├── outputs/                   # Generated images
    ├── logs/                      # Container-internal logs
    ├── audit_reports/             # Full audit reports
    │
    ├── Dockerfile
    ├── docker-compose.yml
    ├── requirements.txt
    ├── CHANGELOG.md
    └── CLAUDE.md                  # Self-improvement contract (for Claude Code runs)
```

---

## 4. Docker Configuration

### docker-compose.yml

```yaml
services:
  minimax-agent:
    build: .
    container_name: minimax-agent
    restart: always
    env_file: .env
    volumes:
      - /root:/root                    # Full ecosystem + task_watcher access
      - /usr/bin/claude:/usr/bin/claude  # Claude Code CLI binary
    network_mode: host                 # Access to localhost:8000 (Odoo microservice)
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      retries: 3
      start_period: 10s
```

### Key Bind Mounts

| Host Path | Container Path | Purpose |
|-----------|---------------|---------|
| `/root` | `/root` | Shares agent-tasks/, scripts/, logs/, .env with host |
| `/usr/bin/claude` | `/usr/bin/claude` | Claude Code CLI binary inside container |

### Environment Variables (`.env`)

```
MINIMAX_API_KEY=sk-cp-...         # MiniMax API key
MINIMAX_API_HOST=https://api.minimax.io
MINIMAX_MODEL=MiniMax-M2.7
MINIMAX_RATE_LIMIT=4500           # Calls per rate window
MINIMAX_RATE_WINDOW_HOURS=5

TELEGRAM_BOT_TOKEN=8604821173:AAH...  # Telegram bot token
TELEGRAM_AUTHORIZED_USER_ID=8288612046  # Fernando's Telegram ID

ODOO_MICROSERVICE_URL=http://localhost:8000  # Odoo FastAPI (host network)

GITHUB_TOKEN=ghp_ypt7...          # GitHub personal access token
GITHUB_USERNAME=fernando0901
GITHUB_LOGS_REPO=minimax-agent-logs

MINIMAX_MCP_BASE_PATH=/root/minimax-agent/outputs
```

---

## 5. MCP Registry (mcps.json)

8 MCP connections configured:

| Name | Transport | Purpose | Enabled |
|------|-----------|---------|---------|
| `n8n` | HTTP | n8n workflow management | ✅ |
| `minimax_coding` | stdio (uvx) | MiniMax coding plan MCP | ✅ |
| `minimax_media` | stdio (uvx) | Image generation + vision | ✅ |
| `minimax_search` | stdio (uvx) | Web search | ✅ |
| `hostinger` | stdio (npx) | VPS management (Hostinger API) | ✅ |
| `context7` | stdio (npx) | Upstash Context7 documentation | ✅ |
| `playwright` | stdio (npx) | Browser automation | ✅ |
| `github` | HTTP | GitHub REST API | ✅ |

### MCP Addition Rules
- **NEVER** hardcode MCPs in Python
- Add new MCPs to `mcps.json`
- Container auto-reconnects via lazy initialization
- Auth tokens redacted before GitHub backup (GitHub secret scanning blocks real tokens)

---

## 6. Skills (YAML-based, hot-reloadable)

Skills are defined in `/root/minimax-agent/skills/*.yaml` and injected into the system prompt when relevant keywords are detected in user messages.

### Skill File Format

```yaml
name: skill_name
description: What this skill does (shown in /skills list)
trigger_keywords:
  - keyword1
  - keyword2
system_injection: |
  Instructions injected into system prompt when triggered.
```

### Current Skills

| File | Trigger Keywords | System Injection |
|------|-----------------|-----------------|
| `greeting.yaml` | hola, hello, buenos días, bye | Friendly greeting, no tools needed |
| `odoo_search.yaml` | cliente, client, buscar, oportunidad | Use `search_client` or `get_opportunities` |
| `price_consultant.yaml` | precio, price, cotización, cuánto cuesta | Always call `get_price` first |

### Adding a New Skill
1. Create `/root/minimax-agent/skills/new_skill.yaml`
2. Add trigger keywords and system_injection
3. Done — `skill_loader.py` hot-reloads automatically (no restart needed)

---

## 7. Telegram Bot — Commands & Handlers

### Command List

| Command | Handler | Description |
|---------|---------|-------------|
| `/start` | `cmd_start` | Welcome message + capabilities |
| `/help` | `cmd_help` | List all commands |
| `/skills` | `cmd_skills` | List loaded YAML skills |
| `/odoo <query>` | `cmd_odoo` | Direct Odoo query (prices, clients, opportunities) |
| `/imagine <prompt>` | `cmd_imagine` | Generate image via MiniMax media MCP |
| `/improve <task>` | `cmd_improve` | Trigger on-demand self-improvement |
| `/add_mcp <name> <url>` | `cmd_add_mcp` | Dynamically add a new MCP |
| `/status` | `cmd_status` | System health (MCPs, API usage, rate limit) |
| `/approve <items>` | `cmd_approve` | Approve improvement plan items + push to GitHub |
| `/reject <items>` | `cmd_reject` | Reject improvement plan items + push to GitHub |

### Message Handlers

| Handler | Trigger | Behavior |
|---------|---------|----------|
| `handle_text` | Any text message | Intent classification → route to MiniMax or self-fix |
| `handle_photo` | Any photo | Vision analysis via MiniMax media MCP |

### Intent Classification (`classify_intent`)

Messages containing these keywords route to the self-improvement flow (NOT to MiniMax chat):

```
corrígelo, corrige, fix, bug, error, mejora, mejorar,
problema, no funciona, no marchan, no responde,
improve, broken, wrong, issue, fail, failing
```

### Idle Detection

After 20 minutes of inactivity per user, before processing the next message:
1. `save_session_learnings()` is called (background, non-blocking)
2. MiniMax summarizes the conversation into a learning paragraph
3. Appended to `memory/agent_memory.md`
4. Pushed to GitHub `memory/agent_memory.md`

---

## 8. Brain — MiniMax API Integration

### Core Flow (`chat()`)

```
User message
    │
    ▼
load_conversation(user_id)  ← sliding window (20 msgs)
    │
    ▼
build_system_prompt(skills_ctx, mcp_tools_ctx, odoo_ctx)
    │
    ▼
MiniMax M2.7 API (with tools)
    │
    ├─► No tool_calls → return text
    │
    └─► Has tool_calls → execute via MCP manager or Odoo bridge
            ↓ (up to 5 iterations)
        final text → save to history → return
```

### Tool Calling Bug (FIXED 2026-04-04)

MiniMax returns tool calls in nested format:
```json
{"tool_calls": [{"id": "call_xxx", "type": "function",
  "function": {"name": "get_price", "arguments": "{\"product_name\":\"vidrio 6mm\"}"}}]}
```

**Wrong parsing:** `tc.get("name")` → `None`
**Correct parsing:** `tc.get("function",{}).get("name")` → `"get_price"`

### Workaround: Text-Embedded Tool Calls

MiniMax-M2.5 sometimes outputs tool calls as plain text instead of using the `tool_calls` field. Brain.py parses this with regex:
```python
# Matches: {"tool_call": {"name": "...", "arguments": {...}}}
re.search(r'\{[\s]*"tool_call"[\s]*:[\s]*\{', response_text)
```

### System Prompt Injection

The system prompt includes (in order):
1. Base persona (Fernando's AI assistant)
2. **Memory section** — last 100 lines of `memory/agent_memory.md`
3. **Skills section** — loaded from YAML skills
4. **Odoo tools** — from `odoo_bridge`
5. **MCP tools** — from connected MCP clients

---

## 9. Odoo Bridge

Connects to the FastAPI microservice running at `http://localhost:8000` (inside the Docker network, not exposed externally).

### Available Tools

| Function | Parameters | Description |
|----------|------------|-------------|
| `get_price` | `product_name: str` | Get price from Odoo product catalog |
| `search_client` | `query: str` | Search contacts by name/email/phone |
| `get_opportunities` | none | List all CRM opportunities |
| `create_opportunity` | dict | Create new sales opportunity |

### Microservice Endpoints (Odoo side)

```
POST /create_contact
POST /schedule_activity
POST /search         (Rich search: contacts + opportunities + activities)
POST /update_contact
GET  /docs
```

Auth: All require `X-Agent-Secret` header.

---

## 10. Self-Improvement Architecture

### Dual-System Design

| Component | Location | Model | Trigger |
|-----------|----------|-------|---------|
| MiniMax chat | Docker container | MiniMax M2.7 | Normal messages |
| Claude Code fixes | task_watcher (systemd) | Claude (via CLI) | Keywords in messages |
| Daily improvement | Docker JobQueue (03:00 UTC) | Claude Code CLI | Cron schedule |
| Orchestrator | Host cron (06:00 UTC) | MiniMax M2.7 | Daily cron |

### Self-Fix Flow (Addendum 2 — current)

```
1. Fernando sends: "corrígelo: [problem]"
2. brain.py classify_intent() → "improve"
3. execute_self_fix() writes /root/agent-tasks/pending/fix_TIMESTAMP.md
4. Returns "📋 Tarea enviada al orquestador..." (< 2 seconds)
5. task_watcher (systemd) detects file within 5 seconds
6. task_watcher runs: claude --print [task_content] cwd=/root
7. Claude Code executes the fix, edits files, updates CHANGELOG.md
8. task_watcher moves file to completed/
9. task_watcher sends Telegram: "✅ Tarea completada: [summary]"
```

### Daily Self-Improvement Cycle (03:00 UTC — JobQueue)

```
daily_self_improve_cycle():
    1. audit_system() → MCP status, API usage, issues
    2. generate_improvement_plan() → writes improvements/YYYY-MM-DD_plan.md
    3. push_plan_to_github()
    4. apply_approved_improvements(yesterday's plan)
    5. Returns summary for Telegram notification
```

### Orchestrator Flow (06:00 UTC — separate cron)

The legacy Python orchestrator at `/root/scripts/orchestrator.py` runs via cron. Reads JSON task files from `agent-tasks/pending/*.json`. Uses MiniMax M2.7 API for error analysis. **This is separate from the task_watcher and uses different task file formats.**

---

## 11. Backup System

### Daily Backup (23:50 UTC — JobQueue)

Three components backed up daily to GitHub `minimax-agent-logs`:

| Component | Path in Repo | Notes |
|-----------|-------------|-------|
| Conversation log | `logs/YYYY-MM-DD.md` | Markdown formatted, grouped by date+user |
| mcps.json (redacted) | `snapshots/YYYY-MM-DD_mcps.json` | Auth tokens replaced with `[REDACTED]` |
| skills/ (tar.gz) | `snapshots/YYYY-MM-DD_skills.tar.gz` | All YAML skill files |

### Session Learnings (20 min idle trigger)

```
save_session_learnings(user_id, conversation_history):
    1. Ask MiniMax to summarize conversation → learning paragraph
    2. Append to memory/agent_memory.md
    3. Push to GitHub memory/agent_memory.md
```

### GitHub Secret Scanning Workaround

When pushing `mcps.json` to GitHub, real API tokens trigger secret scanning → 409 error → GitHub blocks the push.

**Solution:** Before pushing, redact all sensitive values:
```python
REDACTED = "[REDACTED]"
for header_key in ["authorization", "token", "key", "api"]:
    if header_key in k.lower():
        mcp["headers"][k] = REDACTED
for env_key in ["api_key", "token", "password", "secret", "key"]:
    if env_key in k.lower():
        mcp["env"][k] = REDACTED
```

---

## 12. task_watcher — External Fix Execution Service

### Overview

`/root/scripts/task_watcher.py` — lightweight async Python file watcher running as a systemd service outside Docker.

### Why External?

If the Docker container calls `claude --print` directly:
- Long-running Claude Code process keeps container alive
- If it modifies the same files the bot is using → race condition
- Container gets killed mid-rebuild → bot crashes

**Solution:** Container writes a task file and returns immediately (< 2s). External watcher executes Claude Code. Container never modifies itself.

### Service Configuration

```ini
[Unit]
Description=MiniMax Agent Task Watcher
After=network.target

[Service]
Type=simple
User=root
EnvironmentFile=/root/minimax-agent/.env
ExecStart=/usr/bin/python3 /root/scripts/task_watcher.py
Restart=always
RestartSec=10
StandardOutput=append:/root/logs/task-watcher.log
StandardError=append:/root/logs/task-watcher.log

[Install]
WantedBy=multi-user.target
```

### Commands to Manage

```bash
systemctl daemon-reload
systemctl enable task-watcher
systemctl start task-watcher
systemctl stop task-watcher
systemctl status task-watcher
journalctl -u task-watcher -f
```

---

## 13. Key Files Reference

### agent/brain.py

| Function | Purpose |
|----------|---------|
| `classify_intent(message)` | Route to "improve" or "chat" based on keywords |
| `get_memory_context(max_lines=100)` | Read last N lines of agent_memory.md |
| `build_system_prompt()` | Assemble system prompt with memory + skills + tools |
| `chat()` | Core MiniMax API call with tool execution loop |
| `simple_chat()` | Entry point — routes improve intent |
| `execute_tool_call()` | Route tool call to MCP manager or Odoo bridge |
| `build_tools_list()` | Build MiniMax tools schema from Odoo + MCP |
| `load_conversation()` / `save_conversation()` | Sliding window per user |
| `get_api_usage()` / `increment_api_call()` | Rate limit tracking |

### agent/main.py

| Item | Purpose |
|------|---------|
| `last_message_time = {}` | Per-user idle tracking |
| `handle_text()` | Idle check → classify → route |
| `handle_photo()` | Vision analysis via image_handler |
| `cmd_*` | 10 Telegram command handlers |
| `run()` | Bot setup + JobQueue scheduling |

### agent/self_improve.py

| Function | Purpose |
|----------|---------|
| `execute_self_fix()` | Write task file → return immediately |
| `run_claude_improvement()` | Execute Claude Code CLI (for daily cycle) |
| `generate_improvement_plan()` | Audit + create plan doc |
| `apply_approved_improvements()` | Execute approved items via Claude Code |
| `push_plan_to_github()` | Push plan markdown to repo |
| `audit_system()` | Check MCP health, API usage, Odoo connectivity |

### agent/backup.py

| Function | Purpose |
|----------|---------|
| `run_daily_backup()` | Backup conversations + mcps.json + skills |
| `save_session_learnings()` | Summarize idle conversation → memory + GitHub |
| `format_conversation_for_markdown()` | Convert JSON conversation to readable Markdown |
| `push_daily_log()` | Push conversation log to GitHub |
| `push_snapshot_file()` / `push_binary_snapshot()` | Generic GitHub file push |
| `push_memory_snapshot_to_github()` | Push agent_memory.md updates |

### agent/mcp_manager.py

| Function | Purpose |
|----------|---------|
| `get_manager()` | Lazy singleton MCP manager |
| `add_mcp()` | Dynamically register new MCP |
| `ensure_connected()` | Connect on first tool use |
| `call_tool()` | Route tool call to correct MCP |
| `get_all_tools()` | Collect all tools from all MCPs |
| `get_tools_for_system_prompt()` | Human-readable tool descriptions |

### agent/skill_loader.py

| Function | Purpose |
|----------|---------|
| `load_all_skills()` | Load all `skills/*.yaml` files |
| `list_skills()` | Return list of {name, description} |
| `get_skills_for_system_prompt()` | Build skills context for system prompt |

---

## 14. Known Issues & Fixes Log

| Date | Issue | Root Cause | Fix |
|------|-------|------------|-----|
| 2026-04-04 | Tool calls returned raw JSON | brain.py read `tc.get("name")` instead of `tc.get("function",{}).get("name")` | Fixed nested parsing |
| 2026-04-04 | APScheduler event loop error | `scheduler.start()` from daemon thread without event loop | Replaced with `application.job_queue.run_daily()` (python-telegram-bot JobQueue) |
| 2026-04-04 | GitHub 409 on mcps.json push | Secret scanning detected real API tokens | Redact all auth-related values before push |
| 2026-04-04 | Container killed during self-fix | Container called Claude Code directly, kept process alive | Decoupled: container writes task file → external task_watcher executes |
| 2026-04-04 | `error: unknown option '--cwd'` | `--cwd` is not a `claude` CLI flag, it's a `create_subprocess_exec` parameter | Pass `cwd=` as subprocess_exec kwarg, not as CLI argument |

---

## 15. External Dependencies & Connections

### Internal Services (localhost)

| Service | URL | Port | Purpose |
|---------|-----|------|---------|
| Odoo FastAPI microservice | `http://localhost:8000` | 8000 | Odoo CRM operations |

### External Services

| Service | URL | Auth | Purpose |
|---------|-----|------|---------|
| MiniMax API | `https://api.minimax.io` | API Key | Chat completions, image generation |
| Telegram Bot API | `https://api.telegram.org` | Bot Token | All bot communication |
| GitHub API | `https://api.github.com` | PAT | Backup, changelog, fix reports |
| n8n (primary) | `https://n8n.vag131999.cloud` | Bearer Token | Workflow execution |
| n8n (secondary) | `https://n8n2.vag131999.cloud` | Bearer Token | Backup n8n instance |

### n8n Workflows (Production)

| Workflow | ID | Purpose |
|----------|-----|---------|
| Asistente_Odoo | `cbFMGb2tm9jRGg9r` | Main CRM assistant (6 nodes) |
| Confirm Write Operation | `NRVQLPN9D8UaB9Qo` | Odoo write confirmations |
| Confirmation Handler | `sHJRfadX3b2nt4I0` | User confirmation routing |

---

## 16. GitHub Repository Structure (minimax-agent-logs)

```
minimax-agent-logs/
├── README.md                # This file
├── CHANGELOG.md             # Project changelog
├── memory/
│   └── agent_memory.md      # Persistent agent learnings
├── improvements/
│   └── YYYY-MM-DD_plan.md   # Daily improvement plans
├── snapshots/
│   ├── YYYY-MM-DD_mcps.json       # Redacted MCP config snapshot
│   └── YYYY-MM-DD_skills.tar.gz  # Skills backup
├── logs/
│   └── YYYY-MM-DD.md        # Daily conversation logs
└── fix_report_*.md         # Fix execution reports
```

---

## 17. Security Rules

1. **Port 8000 is NEVER exposed externally** — FastAPI microservice is internal-only
2. **Never push directly to main/production branches** — always use feature branches or direct file push via API
3. **NEVER log, print, or write credentials to files** — only to designated secrets locations
4. **Credentials never in GitHub** — mcps.json tokens are always redacted before push
5. **`--dangerously-skip-permissions` NOT used** — normal permission flow maintained
6. **Claude Code workspace** — `/root/minimax-agent` for improvement tasks, `/root` for global context

---

## 18. Coding Rules

- **Language:** Python 3.11+ with full async/await
- **HTTP Client:** `httpx` (async throughout)
- **Telegram Bot:** `python-telegram-bot >= 21.0` (async API)
- **MCP Client:** `mcp >= 1.0.0`
- **Type hints:** Required on all public functions
- **Internal language:** English (code, comments, logs, docs)
- **Response language:** Spanish (Fernando's Telegram messages only)
- **File format:** YAML for skills, JSON for configs, Markdown for docs

---

## 19. Rate Limits

| Limit | Value | Window |
|-------|-------|--------|
| MiniMax API calls | 4500 | 5 hours |
| Telegram polling | Long polling | Continuous |
| task_watcher poll | 5 seconds | Continuous |
| Self-improvement cycle | 1x daily | 03:00 UTC |
| Orchestrator | 1x daily | 06:00 UTC |
| Backup | 1x daily | 23:50 UTC |
| Idle threshold | 20 minutes | Per user |

---

*Document generated 2026-04-04*
*Project: MiniMax Telegram Agent — Fernando Guadarrama — Vidrios y Aluminio Guadarrama*
