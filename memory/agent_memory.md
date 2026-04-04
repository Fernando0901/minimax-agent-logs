# Agent Memory — MiniMax Agent

## Session Learnings

_Learnings from interactions are appended below by the agent._

---

## System Knowledge

- Fernando's business: Vidrios y Aluminio Guadarrama (Vidrio y Aluminio)
- Odoo CRM accessible via FastAPI microservice at `http://odoo_python_agent:8000`
- n8n orchestrator at `https://n8n.vag131999.cloud` + `https://n8n2.vag131999.cloud`
- Primary n8n workflow: Asistente_Odoo (ID: `cbFMGb2tm9jRGg9r`)
- Agent runs in Docker container `minimax-agent` on VPS 31.97.211.181
- GitHub repo for logs/backups: `fernando0901/minimax-agent-logs`

## Repeated Fixes Applied

| Date | Issue | Root Cause | Fix |
|------|-------|------------|-----|
| 2026-04-04 | Tool calling returned raw JSON | brain.py read `tc.get("name")` instead of `tc.get("function",{}).get("name")` | Fixed parsing in brain.py |
| 2026-04-04 | APScheduler event loop error | scheduler.start() from thread without event loop | Replaced with python-telegram-bot JobQueue |
| 2026-04-04 | GitHub 409 on mcps.json push | Secret scanning detected API tokens | Redact all auth-related values before push |

## Preferencias de Fernando

- Prefers Spanish responses from the agent
- Uses "corrígelo", "mejora", "bug" as improvement trigger keywords
- Likes direct, efficient answers — no lengthy preambles
- Receives improvement notifications via Telegram
