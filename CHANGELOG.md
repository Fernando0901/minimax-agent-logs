# Changelog — MiniMax Agent

## 2026-04-04 — Full self-audit: MCP library broken, direct API confirmed working

### AUDIT FINDING
The Python mcp library (all versions 1.7.0-1.27.0) has a fundamental bug where its asyncio stdio_client
cannot communicate with MCP servers. Error: "ExceptionGroup: unhandled errors in a TaskGroup" affecting ALL
MCP transports (stdio and HTTP). Tested downgrade to 1.10, 1.7, 1.8, 1.9 — all fail same way.
The MCP servers themselves work fine with direct JSON-RPC over stdin/stdout.

### STATUS (confirmed working)
- MCP manager: 0 connections (broken library, not env vars)
- web_search: ✅ WORKING (direct /v1/coding_plan/search API)
- understand_image: ✅ WORKING (direct /v1/coding_plan/vlm API with base64 conversion)
- image_generation: ✅ WORKING (direct /v1/image_generation with URL return)
- Image usage tracking: ✅ WORKING (api_usage.json, 50/day limit)

### CHANGE — cmd_imagine sends URL directly (no disk roundtrip)
- `generate_image()` now returns `{"url": image_url, "local_path": filepath}`
  instead of `(filepath, None)`
- `cmd_imagine()` sends `bot.send_photo(photo=image_url)` directly
- Local file still saved for usage tracking
- **Files:** image_handler.py (generate_image), main.py (cmd_imagine)

Container rebuilt. All tools verified.

---

## 2026-04-04 — Enable web_search, understand_image, image generation via direct API

### PROBLEM
The minimax-coding-plan-mcp package (uvx entry point) crashes immediately when run as an MCP stdio subprocess. Root cause: BrokenResourceError in anyio streams during session.initialize(). The MCP server itself works fine when run directly, but the MCP Python SDK 1.27.0 client cannot maintain a stable connection to it.

### FIX 1 — web_search via direct API
- Added `direct_web_search()` in brain.py calling MiniMax `/v1/coding_plan/search` API
- Added "web_search" tool to `build_tools_list()` with full OpenAI-format schema
- Routed through `execute_tool_call()` → `direct_web_search()`
- **Status: WORKING** — verified with "noticias hoy Mexico" query

### FIX 2 — understand_image via direct VLM API
- Added `direct_understand_image()` in brain.py calling MiniMax `/v1/coding_plan/vlm` API
- Added local file path → base64 data URI conversion (VLM API requires HTTP URL or base64)
- Added "understand_image" tool to `build_tools_list()`
- Routed through `execute_tool_call()` → `direct_understand_image()`
- **Status: WORKING** — verified with local PNG file (returns "A wide landscape view of a setting or rising sun...")

### FIX 3 — Image generation via /v1/image_generation with rate limiting
- Rewrote `generate_image()` in image_handler.py to use correct endpoint: `POST /v1/image_generation`
- Fixed response parsing: `data.image_urls[0]` (not `data[0].url`)
- Added daily limit tracking in api_usage.json: "images_today", max 50/day
- **Status: WORKING** — verified generating 184KB PNG image

### FIX 4 — handle_photo uses understand_image tool
- `handle_photo()` in main.py now: saves Telegram photo to temp file → calls `execute_tool_call("understand_image", {prompt, image_source})` → returns analysis
- Removed base64 vision_chat path (was inefficient)
- **Status: WORKING**

### FILES CHANGED
- `agent/brain.py` — direct_web_search(), direct_understand_image(), build_tools_list() (added 2 tools), execute_tool_call() (routing for new tools)
- `agent/image_handler.py` — complete rewrite: analyze_image() (base64→VLM), generate_image() (correct endpoint + rate limiting)
- `agent/main.py` — handle_photo() (uses understand_image tool), cmd_imagine() (handles new generate_image tuple return)

Container rebuilt and restarted. All tools verified.

---

## 2026-04-04 — Fix self-fix intent + task_watcher + image handling

### FIX 1 — Intent classification now only triggers on explicit fix requests
- **Problem:** Bot classified ANY message with "error", "problema", "no funciona" as "improve" intent, sending "Tarea enviada al orquestador" without actually doing anything
- **Fix:** IMPROVEMENT_KEYWORDS reduced to only explicit fix commands: "corrígelo", "corrige", "mejora el bot", "fix it", "bug", "broken", "fail"
- Casual mentions like "tienes un error?", "por qué no funciona" → chat (not self-fix)
- **File changed:** `agent/brain.py` (classify_intent function)

### FIX 2 — Images now use vision_chat (full conversation + tools)
- **Problem:** `handle_photo()` called `analyze_image()` directly, bypassing tool support
- **Fix:** `handle_photo()` now calls `vision_chat()` with MCP + Odoo tools
- **Files changed:** `main.py` (handle_photo), `brain.py` (vision_chat)

### FIX 3 — task_watcher subprocess now uses stdin
- **Problem:** `claude --print` was called with positional argument instead of stdin
- **Fix:** Changed from `create_subprocess_exec` to `create_subprocess_shell` with stdin pipe
- **File changed:** `/root/scripts/task_watcher.py` (execute_task function)
- task_watcher service restarted with fix

Container rebuilt and restarted. task_watcher restarted. Status: healthy.

---

## 2026-04-04 — Fix 404 errors on Odoo tool calls

### PROBLEM
The odoo_bridge.py was calling non-existent FastAPI endpoints:
- `GET /get_price` → should be `POST /get_product_price`
- `GET /search_client` → should be `POST /search`
- `GET /opportunities` → should be `POST /search` (opportunities are CRM leads)

This caused all Odoo tool calls from the Telegram bot to return 404 Not Found.

### FIX — odoo_bridge.py
Updated all functions to use the correct endpoint paths and HTTP methods:
- `get_price()`: Now calls `POST /get_product_price` with `{"search_term": product_name}`
- `search_client()`: Now calls `POST /search` with `{"search_term": query, "limit": 10}`
- `get_opportunities()`: Now calls `POST /search` (opportunities are leads searchable via /search)
- `create_opportunity()`: Now calls `POST /create_opportunity` (was using wrong endpoint)
- Added `_headers()` helper to avoid repeated header construction
- `raw_query()`: Fixed to use `POST` when specified, added Content-Type header

Container rebuilt and restarted. Status: healthy.

---

## 2026-04-04 — Fix Odoo DB connection + tool_call JSON display

### FIX 1 — Odoo microservice connection (network topology)
- **Problem:** minimax-agent used `network_mode: host` but odoo_python_agent runs on Docker internal network `deployment_package_app_network` with port 8000 only exposed internally (not bound to host)
- **Fix:** Changed minimax-agent to join `deployment_package_app_network` as an external network
- **Files changed:** docker-compose.yml (replaced `network_mode: host` with `networks: [deployment_package_app_network]`)
- **Also updated:** `.env` — `ODOO_MICROSERVICE_URL` changed from `http://localhost:8000` to `http://odoo_python_agent:8000` (Docker internal DNS resolves container name)

### FIX 2 — Tool call JSON shown to user instead of plain text
- **Problem:** MiniMax embeds tool calls as `{"tool_call": {"name":...}}` JSON text. The regex pattern `r'\{[\s]*"tool_call"[\s]*:[\s]*\{'` failed to match when MiniMax outputs the JSON with specific formatting (no space after `:` or nested structure variations)
- **Fix:** Replaced regex with more robust `re.compile(r'\{[\s]*"tool_call"[\s]*:[\s]*\{[\s\S]*?\}\s*\}', re.DOTALL)` — non-greedy match with DOTALL flag handles newlines and nested braces correctly
- **Additional safety:** Added `if tc_name:` guard before executing, and uses `response_text.replace(tc_text, "").strip()` to fully remove tool_call JSON from displayed text
- **File changed:** brain.py (lines 355-406)

---

## 2026-04-04 — Addendum 2: Intent routing + self-fix + persistent memory + idle detection

### CHANGE 1 — Intent classifier + router in brain.py
- Added `classify_intent()` with keyword-based detection ("corrígelo", "fix", "mejora", "bug", "error", etc.)
- `simple_chat()` now routes "improve" intent to `execute_self_fix()` instead of MiniMax
- Normal chat still goes to MiniMax M2.7 as before

### CHANGE 2 — `execute_self_fix()` in self_improve.py
- New async function: `execute_self_fix(user_id, problem_description, conversation_history)`
- Writes task file to `/root/agent-tasks/pending/fix_{timestamp}.md` and returns immediately
- The external `task_watcher.py` (systemd service, runs outside Docker) picks it up within 5 seconds
- task_watcher executes Claude Code CLI with `cwd=/root`, inherits global MCPs
- task_watcher sends Telegram notification on completion
- minimax-agent container is NEVER killed by its own fix tasks

### CHANGE 3a — `save_session_learnings()` in backup.py
- New async function called after 20 min idle per user
- Asks MiniMax to summarize conversation into a learning paragraph
- Appends learning to `memory/agent_memory.md`
- Pushes updated memory to GitHub `memory/agent_memory.md`

### CHANGE 3b — Memory injection in brain.py
- Added `get_memory_context()` — reads last 100 lines of `agent_memory.md`
- `build_system_prompt()` now injects memory section into system prompt
- Agent always has persistent context from previous sessions

### CHANGE 3c — `memory/agent_memory.md` created
- New file created at `/root/minimax-agent/memory/agent_memory.md`
- Contains system knowledge, repeated fixes log, and Fernando's preferences

### CHANGE 4 — Idle detection in main.py
- Added `last_message_time = {}` dict per user in main.py
- `handle_text()` now checks if user was idle >= 20 minutes
- If idle, triggers `save_session_learnings()` as background task before processing new message

### NEW — task_watcher.py (systemd service, outside Docker)
- Created `/root/scripts/task_watcher.py` — lightweight async file watcher
- Monitors `/root/agent-tasks/pending/` every 5 seconds for new .md task files
- Executes tasks via Claude Code CLI with `cwd=/root`
- Notifies Fernando via Telegram on success/failure
- Runs as systemd service: `task-watcher.service`
- Completely independent of minimax-agent Docker container — container never self-modifies

---

## 2026-04-04 — Bug fixes + infrastructure (第二次)

### FIX 1 — APScheduler removed, using python-telegram-bot JobQueue
- APScheduler thread removed from main.py (was causing "Event loop is running in a different thread" error)
- Replaced with application.job_queue.run_daily() for both daily self-improvement (03:00 UTC) and daily backup (23:50 UTC)
- APScheduler imports removed from self_improve.py
- `setup_scheduler()` function removed from self_improve.py

### FIX 2 — GitHub backup now includes mcps.json and skills snapshots
- `run_daily_backup()` now backs up: conversation_store.json + mcps.json + skills/ as tar.gz
- Files pushed to minimax-agent-logs repo as snapshots/YYYY-MM-DD_mcps.json and snapshots/YYYY-MM-DD_skills.tar.gz
- Added `push_snapshot_file()` and `push_binary_snapshot()` helper functions in backup.py
- Backup now wired to JobQueue (23:50 UTC daily)

### FIX 3 — /approve and /reject now push to GitHub
- After updating local plan file, both commands push the updated plan to GitHub
- Fernnand receives Telegram confirmation with GitHub URL after successful push
- Uses existing `push_plan_to_github()` from self_improve.py

### Tool Calling Bug — Fixed earlier this session
- brain.py was reading `tc.get("name")` instead of `tc.get("function",{}).get("name")`
- MiniMax returns tool_calls in nested format: `tool_calls[].function.name`
- Fixed and container rebuilt

---

## 2026-04-04 — Initial deployment
- Created full project structure at /root/minimax-agent/
- Implemented brain.py (MiniMax M2.5 conversation engine)
- Implemented mcp_manager.py (dynamic MCP registry)
- Implemented odoo_bridge.py (Odoo FastAPI client)
- Implemented image_handler.py (vision + generation)
- Implemented skill_loader.py (YAML-based skills)
- Implemented self_improve.py (Claude Code CLI orchestration)
- Implemented main.py (Telegram bot with all handlers)
- Configured mcps.json with n8n, minimax, hostinger, context7, playwright, github
- Docker setup with Dockerfile and docker-compose.yml
