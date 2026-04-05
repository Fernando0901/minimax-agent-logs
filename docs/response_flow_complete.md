# MiniMax-Agent Response Flow — Complete Architecture

**Document:** Complete response flow from Telegram trigger to Claude Code CLI execution
**Date:** 2026-04-05
**Author:** Claude Code CLI (autonomous audit)
**Repo:** fernando0901/minimax-agent-logs

---

## Overview

When Fernando sends a message to the MiniMax Telegram bot, a complex chain of systems is triggered. This document describes the complete flow, including the self-fix mechanism that allows the bot to improve itself autonomously.

---

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         STEP 1: Telegram Message                             │
│                             │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 2: main.py Telegram Handler                          │
│  agent/main.py — python-telegram-bot v21 async handlers                      │
│  ├── handle_text()     → simple_chat() via brain.py                          │
│  ├── handle_photo()   → vision_chat() via brain.py                          │
│  └── classify_intent() → determines if 'improve' keyword present             │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 3: brain.py — Intent Classification                  │
│  agent/brain.py — classify_intent()                                          │
│                                                                              │
│  IMPROVEMENT_KEYWORDS = [                                                     │
│    "corrígelo", "corrige", "mejora el bot", "mejora esto",                    │
│    "fix it", "fix the bot", "improve the bot",                              │
│    "bug", "broken", "fail"                                                   │
│  ]                                                                           │
│                                                                              │
│  • If keyword detected → intent = "improve"                                   │
│  • Otherwise           → intent = "chat"                                     │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
              ▼                                 ▼
┌──────────────────────────┐      ┌─────────────────────────────────────────────┐
│    INTENT = "chat"        │      │       INTENT = "improve"                     │
│                           │      │                                             │
│  → chat() in brain.py     │      │  → execute_self_fix() in self_improve.py    │
│  → MiniMax M2.5 API       │      │  → Writes task to /root/agent-tasks/         │
│  → Tool call execution    │      │    pending/fix_{timestamp}.md              │
│  → Response to Telegram   │      │  → Returns "📋 Tarea enviada..."            │
└──────────────────────────┘      └──────────────────────────────┬──────────────┘
                                                                  │
                                                                  ▼
                                                  ┌─────────────────────────────────────┐
                                                  │   STEP 4: task_watcher.py            │
                                                  │   /root/scripts/task_watcher.py      │
                                                  │   Runs as SYSTEMD service            │
                                                  │   (outside Docker container)         │
                                                  │   Polls every 5 seconds             │
                                                  │   cwd=/root                          │
                                                  └──────────────────────┬──────────────┘
                                                                     │
                                                                     ▼
                                                  ┌─────────────────────────────────────┐
                                                  │   STEP 5: Claude Code CLI            │
                                                  │   $ claude --print [task_content]   │
                                                  │   cwd=/root                         │
                                                  │   timeout=600s                       │
                                                  └──────────────────────┬──────────────┘
                                                                     │
                                                                     ▼
                                                  ┌─────────────────────────────────────┐
                                                  │   STEP 6: Claude Code Executes       │
                                                  │   Reads /root/minimax-agent/        │
                                                  │   Direct file edits                 │
                                                  │   docker-compose up --build -d      │
                                                  │   if container needs rebuild        │
                                                  │   Appends to CHANGELOG.md           │
                                                  └──────────────────────┬──────────────┘
                                                                     │
                                                                     ▼
                                                  ┌─────────────────────────────────────┐
                                                  │   STEP 7: task_watcher notifies     │
                                                  │   Telegram message to   │
                                                  │   "✅ Tarea completada" or           │
                                                  │   "❌ Tarea fallida"                 │
                                                  └─────────────────────────────────────┘
```

---

## Step-by-Step Description

### STEP 1: Telegram Message Received

Fernando sends a message via Telegram to the bot token `@`. The message arrives at `main.py` handlers.

**Key files:**
- `agent/main.py` — Telegram handlers
- `agent/brain.py` — Intent classification + chat logic

---

### STEP 2: Telegram Handler Dispatch

`main.py` uses `python-telegram-bot v21 async` with two primary handlers:

```python
# Text messages
async def handle_text(update, context):
    text = update.message.text
    intent = classify_intent(text)
    if intent == "improve":
        from agent.self_improve import execute_self_fix
        history = load_conversation(user_id)
        await execute_self_fix(user_id, text, history)
    else:
        await simple_chat(user_id, text, ...)

# Photo messages
async def handle_photo(update, context):
    photo = update.message.photo[-1]
    image_base64 = await photo.download()
    await vision_chat(user_id, caption, image_base64, ...)
```

---

### STEP 3: Intent Classification

`classify_intent()` in `brain.py` checks for improvement keywords:

```python
IMPROVEMENT_KEYWORDS = [
    "corrígelo", "corrige", "mejora el bot", "mejora esto",
    "fix it", "fix the bot", "improve the bot",
    "bug", "broken", "fail"
]

def classify_intent(message: str) -> str:
    msg_lower = message.lower()
    if any(kw in msg_lower for kw in IMPROVEMENT_KEYWORDS):
        return "improve"
    return "chat"
```

**Critical note:** Only EXPLICIT fix/improve requests trigger self-fix. "there's a bug" does NOT trigger it — only "corrígelo" or "mejora" does.

---

### STEP 4A: Chat Flow (intent = "chat")

When intent is "chat", the flow is:

```
chat() in brain.py
    ├── load_conversation(user_id)    → sliding window of 20 messages
    ├── build_system_prompt()        → includes memory context, skills, MCP tools
    ├── call_minimax(messages, tools) → MiniMax M2.5 API with tool definitions
    ├── If tool_calls detected:
    │   ├── execute_tool_call()       → routes to MCP or built-in handlers
    │   │   ├── Odoo Bridge (odoo_agent)
    │   │   ├── n8n tools (list/trigger/get/update_workflow)
    │   │   ├── MiniMax tools (web_search, understand_image)
    │   │   └── MCP tools via mcp_manager
    │   └── call_minimax again with results
    └── Return response to Telegram
```

**Tools available to MiniMax in chat mode:**

| Tool | Source | Purpose |
|------|--------|---------|
| `web_search` | Built-in (direct API) | Web search via MiniMax coding plan |
| `understand_image` | Built-in (direct API) | Image analysis via MiniMax VLM |
| `odoo_agent` | Odoo Bridge | Unified Odoo CRM queries |
| `n8n_list_workflows` | Direct REST API | List n8n workflows |
| `n8n_trigger_workflow` | Direct REST API | Trigger workflow by ID |
| `n8n_get_workflow` | Direct REST API | Download workflow JSON |
| `n8n_update_workflow` | Direct REST API | Push workflow JSON to n8n |
| `manage_notification` | Built-in | Create/list/delete notifications |
| MCP tools | mcp_manager | Dynamic — n8n, github, hostinger, etc. |

---

### STEP 4B: Self-Fix Flow (intent = "improve")

When intent is "improve", `execute_self_fix()` is called:

```python
async def execute_self_fix(user_id, problem_description, conversation_history):
    # Builds context from last 14 conversation messages
    # Gathers today's audit data (errors, slow tool calls)
    # Writes task file to /root/agent-tasks/pending/fix_{timestamp}.md
    # Returns immediately with confirmation message
```

**Task file structure:**
```markdown
# Fix Task — {timestamp}
**Source:** minimax-agent Telegram bot
**User:** {user_id}
**Problem:** {problem_description}

## Recent conversation context
[👤 USER] ...
[🤖 BOT] ...

## Today's Audit Data
**Event summary:** {...}
**⚠️ Errors detected (N):** ...
**🐌 Slow tool calls (N, >5000ms):** ...

## What you must do
1. Read relevant files in /root/minimax-agent/agent/
2. Identify root cause
3. Apply fix by DIRECTLY EDITING files
4. If container needs rebuild: docker-compose -f ... up --build -d
5. Append summary to CHANGELOG.md
```

---

### STEP 5: task_watcher.py — The Orchestrator Bridge

`/root/scripts/task_watcher.py` runs as a **systemd service** outside the Docker container:

```python
# Runs independently — not inside minimax-agent container
# Polls /root/agent-tasks/pending/ every 5 seconds
# Uses asyncio.create_subprocess_shell with stdin pipe:
proc = await asyncio.create_subprocess_shell(
    "claude --print",
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    cwd="/root"  # Critical: runs from /root, not inside container
)
# Passes task content via stdin
# timeout=600s
```

**Why stdin pipe?** See the fix on 2026-04-04: `create_subprocess_exec` with positional args caused issues. Using `create_subprocess_shell` with stdin pipe is the correct approach.

---

### STEP 6: Claude Code CLI Execution

When `claude --print` runs from `/root` with task content on stdin:

1. **Claude Code reads** the task prompt from stdin
2. **Claude Code changes directory** to `/root`
3. **Claude Code reads** the relevant source files in `/root/minimax-agent/agent/`
4. **Claude Code applies fixes** by directly editing Python files
5. **If container needs rebuild:**
   ```bash
   docker-compose -f /root/minimax-agent/docker-compose.yml up --build -d
   ```
6. **Claude Code appends** summary to `/root/minimax-agent/CHANGELOG.md`
7. **Claude Code outputs** a brief summary to stdout

---

### STEP 7: Notification to Fernando

`task_watcher.py` sends Telegram notification on completion:

```python
if success:
    await send_telegram(
        f"✅ <b>Tarea completada:</b> {first_line}\n\n"
        f"<pre>{preview}</pre>"
    )
else:
    await send_telegram(
        f"❌ <b>Tarea fallida:</b> {first_line}\n\n"
        f"<pre>{preview}</pre>"
    )
```

The task file is **moved** from `pending/` to `completed/` or `failed/` with execution results appended.

---

## Key Architecture Decisions

### Why systemd service outside Docker?

`task_watcher.py` runs as a systemd service **outside** the minimax-agent Docker container because:
- If the container needs to be rebuilt (`docker-compose up --build -d`), the service that triggers the rebuild cannot be inside that container
- The service must survive container restarts/rebuilds
- It polls `/root/agent-tasks/pending/` — a volume mounted from host

### Why stdin pipe for Claude Code?

```python
# CORRECT (2026-04-04 fix)
proc = await asyncio.create_subprocess_shell(
    "claude --print",
    stdin=asyncio.subprocess.PIPE,
    ...
)

# INCORRECT (before fix)
proc = await asyncio.create_subprocess_exec(
    "claude", "--print", task_prompt,  # positional args caused issues
    ...
)
```

### Why sliding window of 20 messages?

From `brain.py`:
```python
SLIDING_WINDOW = 20  # messages per user
```
Only the last 20 messages are kept in conversation history to:
- Stay within MiniMax API token limits
- Keep context relevant (not stale old messages)
- Reduce API costs

---

## Memory and Context Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    agent_memory.md (persistent)                  │
│  /root/minimax-agent/memory/agent_memory.md                    │
│  Session learnings appended after each session                  │
│  Loaded into system prompt (last 100 lines)                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  conversation_store.json (per session)          │
│  /root/minimax-agent/memory/conversation_store.json            │
│  Sliding window of 20 messages per user_id                      │
│  Loaded for each chat turn, not persisted long-term             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Docker Container Relationship

```
┌─────────────────────────────────────────────────────────────────┐
│                    Host System (VPS 31.97.211.181)              │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  minimax-agent Docker container                           │   │
│  │  /root/minimax-agent/                                    │   │
│  │  - agent/brain.py                                        │   │
│  │  - agent/main.py                                         │   │
│  │  - agent/self_improve.py                                 │   │
│  │  - agent/mcp_manager.py                                  │   │
│  │  - memory/                                               │   │
│  │  - skills/                                                │   │
│  │  - .env                                                   │   │
│  └────────────────────────────┬─────────────────────────────┘   │
│                                │ volumes mounted                  │
│                                ▼                                 │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Host paths (not inside container):                        │   │
│  │  - /root/agent-tasks/pending/  ← task_watcher writes here │   │
│  │  - /root/agent-tasks/completed/                           │   │
│  │  - /root/agent-tasks/failed/                              │   │
│  │  - /root/minimax-agent/docker-compose.yml                 │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  task_watcher.py (systemd service)                          │   │
│  │  Runs from /root/, outside Docker                           │   │
│  │  Executes: claude --print with task content on stdin        │   │
│  └────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## GitHub Integration

The bot pushes logs to `fernando0901/minimax-agent-logs`:

| Path | Content |
|------|---------|
| `/conversations/` | conversation_store.json snapshots |
| `/memory/` | agent_memory.md snapshots |
| `/improvements/` | Daily improvement plans |
| `/audit/` | System audit reports |
| `/fix_report_*.md` | Self-fix execution reports |
| `/CHANGELOG.md` | All changes made via self-fix |

**Push mechanism:** `self_improve.py` has `push_snapshot_to_github()` using GitHub REST API.

---

## MCP Manager Architecture

```python
# agent/mcp_manager.py — Dynamic MCP registry
class MCPSessionManager:
    sessions: dict[str, MCPSession]  # mcp_name → session
    tools_cache: list[dict]          # all available tools

    def get_all_tools() → list[dict]  # aggregated from all connected MCPs
    async call_tool(mcp_name, tool_name, args) → result
```

**Connected MCPs (from agent_memory.md):**

| MCP | Transport | Target |
|-----|-----------|--------|
| n8n | HTTP | n8n.vag131999.cloud/mcp-server/http |
| minimax_coding | stdio | minimax-coding-plan-mcp |
| minimax_media | stdio | minimax-mcp |
| minimax_search | stdio | minimax-search |
| hostinger | stdio | hostinger-api-mcp@latest |
| context7 | stdio | @upstash/context7-mcp |
| playwright | stdio | @playwright/mcp@latest |
| github | HTTP | api.githubcopilot.com/mcp/ |

---

## Error Handling and Recovery

### queue_fix_task() — Silent Background Fix

When an internal error occurs in minimax-agent, `queue_fix_task()` silently queues a fix task:
- Writes to `/root/agent-tasks/pending/fix_{timestamp}.md`
- Does NOT notify Fernando (background recovery)
- task_watcher picks it up within 5 seconds

### audit_system() — Daily Health Check

```python
async def audit_system() → dict:
    # Checks MCP manager sessions
    # Checks Odoo microservice health (http://localhost:8000/health)
    # Returns: mcp_status, api_calls, failed_count, issues
```

---

## Summary

| Component | Role |
|-----------|------|
| **Telegram** | User interface — Fernando sends messages here |
| **main.py** | Entry point — dispatches to brain.py handlers |
| **brain.py** | Conversation engine — MiniMax M2.5 API + tool orchestration |
| **self_improve.py** | Self-fix engine — writes tasks to agent-tasks/ |
| **task_watcher.py** | Background orchestrator — systemd service, polls pending/, runs Claude Code CLI |
| **Claude Code CLI** | Self-improvement executor — edits files in /root/minimax-agent/ |
| **GitHub** | Persistent log storage — fernando0901/minimax-agent-logs |
| **Docker** | Container isolation — minimax-agent container |
| **systemd** | Process manager — keeps task_watcher running outside Docker |

---

**Document generated:** 2026-04-05
**Last updated by:** Claude Code CLI audit
