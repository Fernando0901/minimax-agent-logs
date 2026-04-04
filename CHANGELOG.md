# Changelog — MiniMax Agent

## 2026-04-04 — Bug fixes + infrastructure (session 2)

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
