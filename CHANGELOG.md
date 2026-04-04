## 2026-04-04 — Enable web_search, understand_image, image generation via direct API

### PROBLEM
The minimax-coding-plan-mcp package crashes when run as MCP stdio subprocess (BrokenResourceError in anyio streams during session.initialize). MCP server works standalone but client cannot connect.

### FIX 1 — web_search via direct API
- direct_web_search() in brain.py → POST /v1/coding_plan/search
- Added to build_tools_list() and execute_tool_call()
- Status: WORKING

### FIX 2 — understand_image via direct VLM API
- direct_understand_image() in brain.py → POST /v1/coding_plan/vlm
- Local files converted to base64 data URI for VLM API
- Status: WORKING

### FIX 3 — Image generation with correct endpoint + rate limiting
- generate_image() now uses POST /v1/image_generation (was /v1/media/generate)
- Fixed response: data.image_urls[0] (was data[0].url)
- Daily limit: 50 images tracked in api_usage.json
- Status: WORKING

### FIX 4 — handle_photo uses understand_image tool
- handle_photo() saves Telegram photo to temp file, calls execute_tool_call("understand_image", ...)
- Removed base64 vision_chat path

Files: brain.py, image_handler.py, main.py. Container rebuilt and restarted.

---

# Changelog — MiniMax Agent

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
- `run_daily_backup()` now backs up: conversation_store.json + mcps.json (redacted) + skills/ as tar.gz
- Files pushed to minimax-agent-logs repo as snapshots/YYYY-MM-DD_mcps.json and snapshots/YYYY-MM-DD_skills.tar.gz
- mcps.json tokens redacted before push (GitHub blocks files with detected secrets)
- Backup wired to JobQueue (23:50 UTC daily)

### FIX 3 — /approve and /reject now push to GitHub
- After updating local plan file, both commands push the updated plan to GitHub
- Fernando receives Telegram confirmation with GitHub URL after successful push
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
