# MiniMax-Agent — Complete "corrígelo" Flow Audit
**Date:** 2026-04-05
**Author:** Claude Code CLI (MiniMax-Agent self-audit)
**Source data:** `/root/minimax-agent/logs/audit/2026-04-05.jsonl`, `/root/agent-tasks/{completed,failed}/*.md`, `/root/scripts/task_watcher.py`, `agent/*.py`

---

## Section 1 — Complete Message Flow: Telegram → Response (ASCII Diagram)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: Telegram Polling (main.py — app.run_polling)                      │
│  User sends message → telegramelegram Bot API                              │
│  python-telegram-bot receives Update object                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: Auth Middleware (auth_middleware)                                  │
│  Checks update.effective_user.id == TELEGRAM_AUTHORIZED_USER_ID             │
│  If unauthorized → silently ignores (no error shown)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: Handler Routing (main.py)                                         │
│  /start        → cmd_start()                                                │
│  /help         → cmd_help()                                                 │
│  /skills       → cmd_skills()                                               │
│  /improve      → cmd_improve() → trigger_improvement()                     │
│  PHOTO         → handle_photo() → understand_image (direct API)            │
│  TEXT          → handle_text() → simple_chat() [ALL other messages]        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: handle_text() — pre-processing (main.py:394)                      │
│  log_incoming() → audit JSONL                                              │
│  Idle check: if user_id in last_message_time > 20 min →                    │
│              save_session_learnings() in background task                    │
│  last_message_time[user_id] = now                                           │
│  await update.message.reply_chat_action("typing")                            │
│  Loads: skills_ctx, mcp_ctx, odoo_ctx                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 5: simple_chat() — Intent Classification (brain.py:831)               │
│  classify_intent(message) → checks IMPROVEMENT_KEYWORDS:                     │
│    ["corrígelo", "corrige", "mejora el bot", "mejora esto",                 │
│     "fix it", "fix the bot", "improve the bot", "bug", "broken", "fail"]  │
│  If match → intent="improve" → execute_self_fix()                           │
│  Else     → intent="chat"   → chat()                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
┌──────────────────────────┐        ┌──────────────────────────────────────────┐
│   INTENT = "improve"     │        │         INTENT = "chat"                  │
│   execute_self_fix()     │        │         chat()                          │
│   (see Section 2)        │        │         brain.py:681                     │
└──────────────────────────┘        └──────────────────────────────────────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 6: chat() — Build Messages (brain.py:681)                             │
│  1. check_rate_limit() → if > 4300 calls/5h → "rate limit exceeded"         │
│  2. load_conversation(user_id) → last 20 messages from conversation_store    │
│  3. build_system_prompt() → skills_context + mcp_tools + odoo_tools +       │
│                             memory_context (last 100 lines of agent_memory) │
│  4. messages = [system] + history + [user_message]                         │
│     (user_message: string, OR [{"type":"image",...}, {"type":"text",...}])  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 7: MiniMax API Call (brain.py:723)                                    │
│  call_minimax(messages, tools=build_tools_list())                           │
│  Endpoint: POST {MINIMAX_API_HOST}/v1/text/chatcompletion_v2               │
│  Tools available: web_search, understand_image, odoo_agent,                 │
│                   n8n_list_workflows, n8n_trigger_workflow, n8n_get_workflow│
│                   n8n_update_workflow + MCP tools from connected MCPs       │
│  increment_api_call() → updates api_usage.json                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 8: Tool Call Handling (brain.py:726-828)                              │
│  Up to 5 iterations for chained tool calls                                  │
│                                                                             │
│  a) Extract tool_calls from MiniMax response (native format)                 │
│  b) WORKAROUND: If no tool_calls but response_text contains                 │
│     {"tool_call": {...}} → regex extraction + execute                       │
│  c) For each tool_call:                                                    │
│       execute_tool_call(tool_name, arguments, user_id)                      │
│       log_tool_call() → audit JSONL                                         │
│  d) Append assistant msg + tool result msgs to messages                     │
│  e) Call MiniMax again with tool results                                    │
│  f) If no more tool_calls → final response → save to history → return      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 9: Post-Processing (brain.py:780-786)                                  │
│  history.append({"role": "user", "content": message})                       │
│  history.append({"role": "assistant", "content": response_text})           │
│  Trim to SLIDING_WINDOW (20 messages)                                       │
│  save_conversation(user_id, history) → conversation_store.json              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 10: handle_text() response (main.py:436)                             │
│  log_outgoing() → audit JSONL                                              │
│  await update.message.reply_text(response)                                  │
│  asyncio.create_task(push_audit_log_to_github()) → async GitHub push        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Section 2 — Special Flow: "corrígelo" Activated (Self-Fix Sub-Flow)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TRIGGER DETECTED — classify_intent() returns "improve"                     │
│  Keyword found: "corrígelo" OR "corrige" OR "mejora" OR "fix"              │
│  Location: brain.py:26-45 (IMPROVEMENT_KEYWORDS list + classify_intent())   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  SUB-FLOW A: simple_chat() → execute_self_fix() (brain.py:837-841)         │
│  From agent.self_improve import execute_self_fix                            │
│  history = load_conversation(user_id)                                       │
│  return await execute_self_fix(user_id, problem_description, history)       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  SUB-FLOW B: execute_self_fix() — self_improve.py                          │
│                                                                             │
│  1. Load last 14 messages from conversation_history (7 pairs)               │
│     Format: [👤 USER] for role==user (max 200 chars)                        │
│             [🤖 BOT] for role==assistant (max 500 chars)                    │
│     (Changed from 10 items with no role labels on 2026-04-05)              │
│                                                                             │
│  2. Build task_file path:                                                   │
│     /root/agent-tasks/pending/fix_{timestamp}.md                            │
│     e.g. fix_20260405_171010.md                                            │
│                                                                             │
│  3. Write task file with STRUCTURE:                                        │
│     # Fix Task — {timestamp}                                                │
│     **Source:** minimax-agent Telegram bot                                   │
│     **User:** {user_id}                                                     │
│     **Problem:** {problem_description}                                       │
│                                                                             │
│     ## Recent conversation context                                          │
│     (last 14 messages in [👤 USER] / [🤖 BOT] format)                      │
│                                                                             │
│     ## Today's Audit Data                                                   │
│     {today_summary()} → event counts from JSONL                             │
│                                                                             │
│     ## What you must do                                                     │
│     (problem description + instructions)                                     │
│                                                                             │
│     ## Constraints                                                          │
│     (Never expose port 8000, Never delete memory/, etc.)                   │
│                                                                             │
│  4. Send Telegram notification to user:                                     │
│     "📋 Tarea enviada al orquestador.\nTe notificaré cuando esté lista."  │
│     log_claude_task() → audit JSONL (status: "dispatched")                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  SUB-FLOW C: Task File Written to Disk                                      │
│  Path: /root/agent-tasks/pending/fix_{timestamp}.md                        │
│  The orchestrator (Python script) polls this directory.                    │
│  HOWEVER: task_watcher.py is a SEPARATE systemd service that:              │
│  - Polls /root/agent-tasks/pending/ every 2 seconds                       │
│  - Detects new fix_*.md files                                              │
│  - Reads the task content                                                  │
│  - Executes: claude --model minimax --print /path/to/task.md              │
│  - OR: claude-code CLI with cwd=/root                                     │
│  - NOTIFIES user via Telegram on completion/failure                        │
│                                                                             │
│  ⚠️ IMPORTANT: task_watcher.py is a SEPARATE PROCESS from the bot.        │
│  It runs as a systemd service: task-watcher.service                        │
│  It is NOT part of the minimax-agent Docker container.                     │
│  It runs: subprocess.Popen(['claude', '--model', 'minimax', '--print',    │
│                             task_path])                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  SUB-FLOW D: task_watcher.py Detection (systemd service)                  │
│  Service: task-watcher.service                                             │
│  Config: /etc/systemd/system/task-watcher.service                          │
│  WorkingDirectory: /root                                                   │
│  Command: /root/scripts/task_watcher.py                                    │
│                                                                             │
│  Detection loop (every 2 seconds):                                         │
│  - scandir /root/agent-tasks/pending/                                      │
│  - Filter: fix_*.md files                                                  │
│  - For each: read content → execute with Claude Code CLI                    │
│  - Move to /root/agent-tasks/completed/ on SUCCESS                         │
│  - Move to /root/agent-tasks/failed/ on ERROR/timeout (600s max)          │
│                                                                             │
│  Claude Code execution:                                                     │
│  - cwd=/root (per CLAUDE.md Section 10)                                   │
│  - Model: MiniMax-M2 (hardcoded in task_watcher.py)                        │
│  - Reads task.md content as prompt                                         │
│  - Claude Code writes output to stdout → captures in task result            │
│  - Bot user (8288612046) notified via Telegram when done                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  SUB-FLOW E: Claude Code CLI Execution                                      │
│  Claude Code is invoked with:                                              │
│    claude --model minimax --print /root/agent-tasks/pending/fix_*.md       │
│                                                                             │
│  Claude Code:                                                               │
│  1. Reads task.md (the problem description)                                 │
│  2. Reads CLAUDE.md from /root/.claude/CLAUDE.md for context               │
│  3. Applies the fix (edits Python files, runs docker commands, etc.)       │
│  4. If docker changes → rebuilds container                                  │
│  5. Appends summary to CHANGELOG.md                                        │
│  6. Writes result to task file in completed/ or failed/                    │
│  7. Returns "✅ SUCCESS" or "❌ FAILED" + output                          │
│                                                                             │
│  IMPORTANT: Claude Code runs OUTSIDE the minimax-agent container.          │
│  It has access to the host filesystem (/root, /opt, /root/minimax-agent)   │
│  It can run docker commands, git, curl, etc.                              │
│  Bot notification: task_watcher sends Telegram message to user (8288612046)│
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  SUB-FLOW F: Error Handling (if task fails)                                │
│  On Exception in handle_text():                                            │
│    log_error() → audit JSONL                                               │
│    queue_fix_task(e, context=...) → writes to /root/agent-tasks/pending/   │
│    "⚠️ Ocurrió un error interno. Ya lo estoy arreglando automáticamente."  │
│                                                                             │
│  On timeout (600s in task_watcher.py):                                      │
│    Task moved to /root/agent-tasks/failed/                                 │
│    Status: "❌ FAILED — Timeout after 600s"                               │
│    User notified via Telegram with failure message                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Section 3 — Last 5 Executions Log

### Execution 1: `fix_20260405_171010.md` — ❌ FAILED (TIMEOUT)

| Field | Value |
|-------|-------|
| **Timestamp (pending)** | 2026-04-05 17:10:10 |
| **Source** | minimax-agent Telegram bot |
| **User** | 8288612046 |
| **Trigger message** | "Corrígelo: ejecuta el plan con las correcciones" |
| **Problem description** | Execute the webhook trigger plan for workflow `ocgpEc41Ez7WLlVQ` (tech+China news workflow). The workflow lacked a manual trigger node. |
| **Conversation context** | Image analysis of a remote control (MEGALUZ brand) → Web search → Question about tech news notification summary → Attempt to execute n8n workflow → Failed because workflow had no webhook trigger node → Plan drafted to add webhook → "Corrígelo: ejecuta el plan" |
| **Claude Code output** | `Status: ❌ FAILED — Timestamp: 2026-04-05T17:20:15.192681 — Output: Timeout after 600s` |
| **Files touched** | None (timeout before any file modification) |
| **Root cause** | The task was to execute an n8n workflow modification plan (add webhook node). Claude Code took >600s and timed out. Likely the n8n API call or workflow modification took too long. |
| **User notification** | FAILED message sent to Telegram (timing suggests user was notified of timeout) |
| **Total duration** | >600s (timeout) |

---

### Execution 2: `fix_20260405_181912.md` — ✅ SUCCESS (No files changed — just info)

| Field | Value |
|-------|-------|
| **Timestamp (pending)** | 2026-04-05 18:19:12 |
| **Source** | minimax-agent Telegram bot |
| **User** | 8288612046 |
| **Trigger message** | "Corrige: audita la creación de un nuevo workflow para evitar contaminar el morning digest actual. Crea el plan de implementación con la hoja de ruta y guardalo dentro de '/root/minimax-agent/tasks/new_workflow_tech&china_news_report'" |
| **Problem description** | Fernando asked to audit workflow creation to AVOID contaminating the existing Morning Digest. Create implementation plan and save to specific path. |
| **Claude Code output** | `Status: ✅ SUCCESS — Timestamp: 2026-04-05T18:19:26.777818 — Output: Here is the link of the news workflow: https://n8n.vag131999.cloud/workflow/ocgpEc41Ez7WLlVQ. Also note that the correction was that the workflow couldn't be executed manually (lacked manual trigger node). Already should be fixed with 'When clicking Test workflow' node added.` |
| **Files touched** | None — Claude Code only provided information, did not create any files |
| **What happened** | Claude Code determined the original issue was already addressed (webhook node added in previous session). Provided the workflow link. Did NOT create the requested plan file at `/root/minimax-agent/tasks/new_workflow_tech&china_news_report`. |
| **Gap identified** | Claude Code did NOT create the implementation plan file as requested. Only provided the workflow link. The `tasks/new_workflow_tech&china_news_news_report` directory was never populated. |
| **User notification** | Sent workflow link to Telegram |

---

### Execution 3: `fix_20260405_190310.md` — ✅ SUCCESS (brain.py modified)

| Field | Value |
|-------|-------|
| **Timestamp (pending)** | 2026-04-05 19:03:10 |
| **Source** | minimax-agent Telegram bot |
| **User** | 8288612046 |
| **Trigger message** | "No necesito que actualices mi workflow, solo que redactes un plan para crear un nuevo workflow en lugar de ocupar el morning digest, para evitar contaminarlo y en su lugar cuando te pida una automatización crees un nuevo workflow en n8n (tú no, claude code CLI a través del comando "corrige") pero que esto se quede en tus conocimientos y en las futuras propuestas de automatización" |
| **Problem description** | Fernando was frustrated: the bot should NEVER modify existing workflows (especially Morning Digest). When Fernando asks for automation, the bot should PROPOSE creating a NEW workflow and use "corrige" to have Claude Code CLI create it. This policy should be permanent knowledge. |
| **Claude Code output** | `Status: ✅ SUCCESS — Timestamp: 2026-04-05T19:05:12.105339` <br><br>**Changes made:**<br>1. `agent/brain.py` — Added `## WORKFLOW AUTOMATION (CRITICAL RULE)` section in `build_system_prompt()`<br>2. `memory/agent_memory.md` — Documented this learning permanently |
| **Files touched** | `agent/brain.py` (build_system_prompt function), `memory/agent_memory.md` |
| **Specific code change** | Added permanent system prompt section:<br>"When Fernando asks for an automation: NEVER modify existing workflows. PROPOSE creating a NEW workflow. Draft the full plan (name, trigger, nodes). Tell Fernando to use 'corrige' so Claude Code CLI creates it in n8n." |
| **Container rebuild** | ✅ Yes — `docker-compose -f /root/minimax-agent/docker-compose.yml up --build -d` |
| **User notification** | ✅ Notified of successful fix |
| **Total duration** | ~122s (from 19:03:10 to 19:05:12) |

---

### Execution 4: `fix_20260405_192045.md` — ✅ SUCCESS (Plan created, pushed to GitHub)

| Field | Value |
|-------|-------|
| **Timestamp (pending)** | 2026-04-05 19:20:45 |
| **Source** | minimax-agent Telegram bot |
| **User** | 8288612046 |
| **Trigger message** | "Corrígelo: cuando envíes un error a reparar a Claude code CLI haz que se envíen los últimos 7 mensajes del chat de telegram, incluyendo tanto mensajes del bot como mensajes de los logs, y del usuario, para que Claude tenga más contexto sobre las ejecuciones y lo que falló. Antes, Crea un plan de implementación y súbelo a mi reporte de git minimax-agent-logs a través de MCP o API directa, después enviame el link o la dirección cd del archivo" |
| **Problem description** | Improve execute_self_fix() context: send last 7 message pairs (user+bot) instead of 10 items, with clear [👤 USER] / [🤖 BOT] labels. First create implementation plan and push to GitHub minimax-agent-logs repo, then send Fernando the link. |
| **Claude Code output** | `Status: ✅ SUCCESS — Timestamp: 2026-04-05T19:23:12.845508`<br><br>**Plan pushed:** `https://github.com/Fernando0901/minimax-agent-logs/blob/main/improvements/20260405_fix_context_plan.md`<br><br>**Plan summary:**<br>- Change `[-10:]` to `[-14:]` for 7 user+bot pairs<br>- Format: `[👤 USER]` for role==user (max 200 chars), `[🤖 BOT]` for role==assistant (max 500 chars)<br>- File to modify: `agent/self_improve.py` only<br>- Risk: Low — only changes string formatting in task file generation |
| **Files touched** | Plan file created and pushed to GitHub. No local files modified yet (plan only). |
| **Gap identified** | This execution only created and pushed the PLAN. It did NOT implement the fix. The actual implementation was done in Execution 5. |
| **User notification** | Sent GitHub link to Fernando |
| **Total duration** | ~147s (from 19:20:45 to 19:23:12) |

---

### Execution 5: `fix_20260405_194319.md` — ✅ SUCCESS (self_improve.py modified)

| Field | Value |
|-------|-------|
| **Timestamp (pending)** | 2026-04-05 19:43:19 |
| **Source** | minimax-agent Telegram bot |
| **User** | 8288612046 |
| **Trigger message** | "Corrígelo: Implementa el plan de mejora que subiste a GitHub..." (with 8-step implementation instructions referencing the GitHub plan) |
| **Problem description** | Implement the exact plan from Execution 4: change conversation_history[-10:] to [-14:], add [👤 USER]/[🤖 BOT] labels, max 200 chars for user, 500 for bot. Then rebuild container, verify healthy, update CHANGELOG, push to GitHub. |
| **Claude Code output** | `Status: ✅ SUCCESS — Timestamp: 2026-04-05T19:46:27.944232`<br><br>**Lines modified:**<br>OLD:<br>`recent_msgs = conversation_history[-10:]`<br>`context = "\n".join([f"{m['role']}: {str(m.get('content',''))[:200]}" for m in recent_msgs])`<br><br>NEW:<br>`recent_msgs = conversation_history[-14:] if len(conversation_history) >= 14 else conversation_history`<br>`context = "\n".join([f"[👤 USER] {str(m.get('content',''))[:200]}" if m['role'] == 'user' else f"[🤖 BOT] {str(m.get('content',''))[:500]}" for m in recent_msgs])` |
| **Files touched** | `agent/self_improve.py` (execute_self_fix function), `CHANGELOG.md` |
| **Container rebuild** | ✅ Yes — `docker compose -f /root/minimax-agent/docker-compose.yml up --build -d` |
| **CHANGELOG update** | ✅ Pushed to GitHub minimax-agent-logs repo |
| **User notification** | "✅ Listo, líneas modificadas: [shown above]" |
| **Total duration** | ~189s (from 19:43:19 to 19:46:27) |

---

## Section 4 — Gaps: Current Flow vs. Ideal M2.7 Auto-Evolution Cycle

The M2.7 auto-evolution ideal cycle is:

```
analizar trayectorias de fallo
  → planificar cambios
    → modificar código
      → ejecutar evaluaciones
        → comparar resultados
          → decidir mantener o revertir
```

### Current State Assessment

| Stage | Exists? | Quality | Notes |
|-------|---------|---------|-------|
| **1. Analizar trayectorias de fallo** | ⚠️ Partial | Medium | `today_summary()` in audit_logger gives event counts but NO trajectory analysis. `queue_fix_task()` captures errors but doesn't classify them. No structured failure categorization (P0/P1/P2). |
| **2. Planificar cambios** | ✅ Yes | Good | Execution 4 shows plan can be created, pushed to GitHub for Fernando's review before implementation. But this is NOT automatic — Fernando must trigger with "corrígelo". |
| **3. Modificar código** | ✅ Yes | Good | Claude Code CLI successfully edits Python files, rebuilds containers, updates CHANGELOG. |
| **4. Ejecutar evaluaciones** | ❌ Missing | — | No automated test/evaluation step exists. The system has no way to verify a fix actually works before declaring success. |
| **5. Comparar resultados** | ❌ Missing | — | No before/after comparison. Claude Code declares SUCCESS purely based on completing the task file write, NOT on actual behavioral verification. |
| **6. Decidir mantener o revertir** | ❌ Missing | — | No rollback mechanism. If a fix breaks something, there's no automatic revert. Fernando must manually trigger another "corrígelo". |

### Specific Gaps

**Gap 1: No evaluation step after fix deployment**
- The Claude Code execution in task_watcher.py ends when Claude writes its output to the task file.
- There is NO step that: runs the bot, sends a test message, verifies the fix works.
- In Execution 1, the timeout might have been a real error OR a hanging process — there's no way to distinguish.

**Gap 2: No structured failure classification**
- `queue_fix_task()` writes all errors to pending tasks with no priority, category, or root cause tag.
- Some errors are P0 (bot crashes), others are P3 (formatting issues) — all treated equally.
- This means the orchestrator can't prioritize critical fixes over minor ones.

**Gap 3: Conversation history context quality is limited**
- Even after Execution 5, only the last 7 pairs are sent (14 messages).
- Images are not included in context (only `photo_sent` placeholder text).
- The bot can't see what error message actually appeared in Telegram — only what the bot's error handler logged.

**Gap 4: task_watcher has no retry logic**
- If Claude Code CLI fails to start (binary missing, permissions), the task stays in pending forever.
- The service has no circuit breaker — if the Claude process hangs, the next tasks queue up.

**Gap 5: No visibility into Claude Code's reasoning**
- The task_watcher executes Claude Code and captures stdout, but:
  - It does NOT capture the intermediate steps Claude Code took
  - It does NOT log which files Claude Code read before making changes
  - The "SUCCESS" status is based on the task file being written, not on actual verification

**Gap 6: No GitHub PR/branch flow**
- Currently: Claude Code commits directly to `main` (or whatever the default branch is).
- Should be: Feature branch → PR → review → merge.
- This means bugs introduced by Claude Code go directly to production.

---

## Section 5 — Implementation Recommendations (Ordered by Impact)

### REC-1: Add Automated Evaluation Step After Each Fix (HIGH IMPACT)

**What:** After Claude Code completes a fix, the task_watcher should:
1. Run a smoke test (e.g., `docker exec minimax-agent python -c "import agent; print('OK')"`)
2. If the fix was to brain.py/self_improve.py: send a test message via Telegram Bot API and verify response
3. Mark task as `VERIFIED` or `FAILED_EVALUATION`

**Why:** Currently a task marked "SUCCESS" may not have fixed anything. We need to close the loop.

**Files to modify:** `/root/scripts/task_watcher.py`

**Implementation:**
```python
# After Claude Code completes successfully:
test_ok = run_smoke_test()  # docker exec + python import check
if test_ok:
    # Optional: send test message to Telegram bot and verify response
    mark_task_verified(task_path)
else:
    mark_task_failed_evaluation(task_path, reason="smoke test failed")
    queue_revert_task(original_task_path)
```

---

### REC-2: Add Structured Failure Classification (MEDIUM-HIGH IMPACT)

**What:** Enhance `queue_fix_task()` and `execute_self_fix()` to classify failures by:
- **Priority:** P0 (bot crash/unresponsive), P1 (tool broken), P2 (wrong behavior), P3 (cosmetic)
- **Category:** `api_error`, `mcp_error`, `docker_error`, `logic_error`, `timeout`
- **Root cause tag:** The specific module/function that failed

**Why:** The orchestrator (Python, 6 AM daily) can't prioritize if all tasks look the same. Priority classification lets Fernando review P0 items first.

**Files to modify:** `agent/self_improve.py` (queue_fix_task, execute_self_fix), `agent/audit_logger.py` (add failure classification fields)

---

### REC-3: Add Rollback Mechanism (MEDIUM IMPACT)

**What:** Before applying any fix, Claude Code should:
1. Copy the original file to `/root/agent-tasks/backups/{filename}_{timestamp}.bak`
2. Write the revert command to the task file as a final step
3. If evaluation fails, execute the revert: `cp backup path → original path`

**Why:** Currently if a fix breaks something, there's no automatic undo. Fernando must notice and trigger another "corrígelo" manually.

**Implementation:** Add to task_watcher.py:
```python
if task.status == "VERIFIED":
    pass  # keep changes
elif task.status == "FAILED_EVALUATION":
    run_revert(task)  # cp backup → original
    notify_user(f"❌ Fix reverted: {task.reason}")
```

---

### REC-4: Improve Context Quality for Claude Code (MEDIUM IMPACT)

**What:** Enhance `execute_self_fix()` to include:
1. **Actual error message** from Telegram: the `log_error()` entry from the audit JSONL, not just the exception string
2. **Docker container health status**: `docker ps --format "{{.Names}} {{.Status}}"`
3. **Recent journalctl entries** for the bot: `journalctl -u minimax-agent --no-pager -n 20`
4. **Git diff** if there were recent changes to the relevant files

**Why:** In Execution 1, Claude Code had to figure out from scratch that the workflow couldn't be triggered. If it had the actual error message from the n8n API response, it could have diagnosed faster (avoiding the 600s timeout).

**Files to modify:** `agent/self_improve.py` (execute_self_fix function)

---

### REC-5: Implement GitHub Branch Workflow for Claude Code (MEDIUM IMPACT)

**What:** Modify task_watcher.py to:
1. Create a feature branch: `fix/{timestamp}`
2. Commit changes to that branch
3. Open a PR against `main` (or push to `main` as current behavior but add PR creation as optional step)
4. Add `CI` check that runs smoke test before merge

**Why:** Direct commits to main mean bugs go straight to production. A PR review gate would catch issues before they affect Fernando's bot.

**Files to modify:** `/root/scripts/task_watcher.py`

---

### REC-6: Add Conversation Image Context (LOW-MEDIUM IMPACT)

**What:** In `execute_self_fix()`, when the error context includes an image, download the image and attach it to the task file as a local path, so Claude Code can analyze it.

**Why:** Currently `photo_sent` placeholder tells Claude Code an image was sent but not WHAT was in the image. If the error is related to image handling, Claude Code needs to see the actual image.

**Files to modify:** `agent/self_improve.py`

---

## Appendix A — Complete Audit Log Extract (2026-04-05.jsonl — fix/improve events)

```
=== INCOMING/OUTGOING EVENTS (corrígelo triggers) ===

[17:44:26] INCOMING: "Corrígelo: ejecuta el plan con las correcciones"
[17:44:27] OUTGOING: "📋 Tarea enviada al orquestador..." (4.5ms)
[18:06:20] INCOMING: "Corrige: audita la creación de un nuevo workflow..."
[18:06:21] OUTGOING: "📋 Tarea enviada al orquestador..." (8.8ms)
[18:19:12] INCOMING: "Qué entendiste con este mensaje: Corrige: audita..."
[18:19:12] OUTGOING: "📋 Tarea enviada al orquestador..." (10.4ms)
[18:19:12] INCOMING: "Corrige: audita la creación de un nuevo workflow..." (duplicate trigger)
[18:19:12] OUTGOING: "📋 Tarea enviada al orquestador..." (10.4ms)
[19:03:10] INCOMING: "No necesito que actualices mi workflow..."
[19:03:10] OUTGOING: "📋 Tarea enviada al orquestador..." (8.8ms)
[19:20:45] INCOMING: "Corrígelo: cuando envíes un error a reparar a Claude code CLI..."
[19:20:45] OUTGOING: "📋 Tarea enviada al orquestador..." (9.1ms)
[19:43:19] INCOMING: "Corrígelo: Implementa el plan de mejora que subiste a GitHub..."
[19:43:19] OUTGOING: "📋 Tarea enviada al orquestador..." (7.7ms)

=== SYSTEM EVENTS ===

[03:00:00] SYSTEM: Self-improvement cycle — 1 issue found, 0 MCPs healthy, 0 applied
[23:50:00] SYSTEM: (Daily backup scheduled but log cut off before execution)

=== NOTIFICATION EVENTS ===

[09:00:00] NOTIFICATION: Topic "tecnología y china" — likely sent (log entry truncated)
```

---

## Appendix B — task_watcher.py Execution Details

**Service configuration:**
```
[Unit]
Description=MiniMax Agent Task Watcher
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root
ExecStart=/root/scripts/task_watcher.py
Restart=on-failure
RestartSec=10
```

**Key execution parameters:**
- Poll interval: 2 seconds
- Task timeout: 600 seconds (10 minutes)
- Claude Code model: `minimax` (hardcoded in task_watcher.py)
- Notification: Telegram direct message to user 8288612046 on completion/failure
- Task file naming: `fix_{YYYYMMDD}_{HHMMSS}.md`
- Completed path: `/root/agent-tasks/completed/`
- Failed path: `/root/agent-tasks/failed/`

**Recent journalctl entries for task-watcher:**
```
2026-04-04T17:26:26+00:00 — Stopped (service restart for config change)
2026-04-04T17:26:26+00:00 — CPU: 45.6s, Memory peak: 528.4M
2026-04-05T02:30:35+00:00 — Stopped (service restart)
2026-04-05T02:30:35+00:00 — CPU: 2min 11s, Memory peak: 1.2G (large task ran here)
```

---

## Appendix C — File Locations Reference

| File | Purpose |
|------|---------|
| `/root/minimax-agent/agent/main.py` | Telegram handlers, routing, job scheduler |
| `/root/minimax-agent/agent/brain.py` | MiniMax API, intent classification, tool execution |
| `/root/minimax-agent/agent/self_improve.py` | Self-fix orchestration, task file generation |
| `/root/scripts/task_watcher.py` | Systemd service that runs Claude Code CLI on task files |
| `/root/minimax-agent/logs/audit/2026-04-05.jsonl` | Daily JSONL audit log |
| `/root/agent-tasks/pending/` | Pending task files (picked up by task_watcher) |
| `/root/agent-tasks/completed/` | Successfully completed task results |
| `/root/agent-tasks/failed/` | Failed/timeout task results |
| `/root/minimax-agent/CHANGELOG.md` | Change log (updated after each fix) |
| `/root/minimax-agent/memory/agent_memory.md` | Persistent agent learnings |
| `/root/minimax-agent/docker-compose.yml` | Container definition |
| `/etc/systemd/system/task-watcher.service` | Systemd unit file |

---

*Document generated: 2026-04-05 by Claude Code CLI (MiniMax-Agent self-audit)*
*Total executions audited: 5 (1 failed/timeout, 4 successful)*
