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
- GitHub repo for logs/backups: `fernando0901/minax-agent-logs`

## Repeated Fixes Applied

| Date | Issue | Root Cause | Fix |
|------|-------|------------|-----|
| 2026-04-04 | Bot didn't respond to images | handle_photo called analyze_image directly, no tool support | Now uses vision_chat() with full MCP/Odoo tools |
| 2026-04-04 | task_watcher --cwd error | create_subprocess_exec with positional arg to claude --print | Changed to create_subprocess_shell with stdin pipe |
| 2026-04-04 | Tool calling returned raw JSON | brain.py read `tc.get("name")` instead of `tc.get("function",{}).get("name")` | Fixed parsing in brain.py |
| 2026-04-04 | APScheduler event loop error | scheduler.start() from thread without event loop | Replaced with python-telegram-bot JobQueue |
| 2026-04-04 | GitHub 409 on mcps.json push | Secret scanning detected API tokens | Redact all auth-related values before push |

##的习惯 (Fernando's Preferences)

- Prefers Spanish responses from the agent
- Uses "corrígelo", "mejora", "bug" as improvement trigger keywords
- Likes direct, efficient answers — no lengthy preambles
- Receives improvement notifications via Telegram

## Test Entry — e2e passed


## Session — 2026-04-05 05:31 (User 8288612046)
**Aprendizajes para agente persistente:**

**Empresa del usuario:** Vidrios y Aluminio Guadarrama maneja SOLO vidrio flotado y vidrio templado (no laminado ni otros tipos). **Preferencias:** Quiere notificaciones diarias a las 9am hora México sobre tecnología y China (configurar en n8n workflow `ocgpEc41Ez7WLlVQ`), y recibir logs de su repo `fernando0901/minax-agent-logs` por Telegram después de cada tarea completada. **Limitaciones técnicas:** El agente no puede hacer push directo a GitHub ni ejecutar comandos en sistema de archivos — necesita integración via n8n o funciones externas. **Errores evitados:** No incluir tokens de autenticación en archivos push (causa error 409 Conflict por GitHub Secret Scanning).

## Session — 2026-04-05 06:20 (User 8288612046)
**Aprendizajes para agente AI persistente:**

**Preferencias del negocio del usuario:** El usuario maneja el negocio "Vidrios y Aluminio Guadarrama" que trabaja **exclusivamente** con vidrio flotado y vidrio templado (NO laminado ni otros tipos). **CRÍTICO:** Toda información sobre este negocio debe ceñirse a estos dos productos sin asumir otros.

**Limitaciones técnicas detectadas:** El agente no tiene capacidad de escribir archivos permanentes ni hacer push a GitHub directamente (sin embargo tiene `git_ops.py` con funciones existentes que no se invocan automáticamente). No hay MCP tools configuradas actualmente.

**Solicitudes pendientes del usuario:** Quiere que se envíe un log a su repositorio GitHub (`fernando0901/minax-agent-logs`) cada vez que se complete una tarea. No tiene implementado este comportamiento aún.

**Integraciones en su ecosistema:** n8n (workflow "Morning Digest - Phase F" ID `ocgpEc41Ez7WLlVQ`), Odoo CRM, Telegram para notificaciones, GitHub para logs.

**Problema de seguridad resuelto:** GitHub rechazaba pushes con error 409 Conflict porque Secret Scanning detectaba tokens de autenticación en los archivos.