# MiniMax-Agent — Conversación Completa + Diagnóstico + Fixes
**Fecha:** 2026-04-04
**Archivo generado por:** Claude Code (sesión actual)
**Propósito:** Dar a una IA externa para análisis y solución de problemas del bot de Telegram

---

## SECCIÓN 1 — CONVERSACIÓN TELEGRAM (2026-04-04)

### Mensaje 1 — Usuario
```
No me salen tus respuestas en texto plano me salen en formato Json y solamente me sale el cómo llamaste a la herramienta
```

### Mensaje 2 — Asistente
```
Ah, entiendo el problema. Eso suena a un error en la integración del agente.

Lo que deberías ver es:
1. Mi mensaje en texto plano (la explicación)
2. Los resultados de la herramienta (la lista de clientes)

Pero solo estás viendo el JSON de cómo invoqué la herramienta.

**Esto puede ser:**
1. La herramienta no está retornando datos — puede que no haya clientes registrados o hay un problema de conexión con Odoo
2. Un bug en la integración del agente con Telegram
3. Falta de permisos en la API de Odoo
```

### Mensaje 3 — Usuario
```
No únicamente puedo ver {"tool_call":{"name"}
Pero no tiene nada en arguments
Intenta buscar a todos los clientes que se llaman Fernando
```

### Mensaje 4 — Asistente (PROBLEMA: muestra tool_call JSON)
```
{"tool_call": {"name": "search_client", "arguments": {"query": "Fernando"}}}
```

### Mensaje 5 — Usuario
```
Pero no me envíes la llamada a la herramienta a mí
```

### Mensaje 6 — Asistente
```
Entiendo, pero ese es el formato que necesito usar para que el sistema ejecute la búsqueda. No te estoy enviando la llamada a ti como mensaje — es la forma en que el sistema funciona.

El problema es que tu integración no está mostrando los resultados, solo la llamada en sí.
```

### Mensaje 7 — Usuario
```
Hola 👋🏻
```

### Mensaje 8 — Asistente
```
¡Hola! 👋

Respecto al problema técnico que teníamos — donde no podías ver los resultados de las herramientas en texto plano — eso es un bug en la configuración del agente.
```

### Mensaje 9 — Usuario
```
Busca dentro de odoo el precio de la jadadera trompa de elefante
```

### Mensaje 10 — Asistente
```
Hay un problema de conexión con el CRM de Odoo. El error indica que no se puede establecer conexión:

"All connection attempts failed"

Posibles causas:
1. El servicio odoo_python_agent está caído o no está corriendo
2. Problemas de red entre contenedores (Docker)
3. El contenedor necesita reiniciarse
```

### Mensaje 11 — Usuario
```
Por qué no has ejecutado ninguna acción
```

### Mensaje 12 — Asistente
```
Ahí va el resultado — y ahora sí puedes ver la respuesta en texto plano. 🎉

El problema no es de conexión, sino del endpoint:

404 Not Found - /get_price?product=jadadera+trompa+de+elefante

La ruta /get_price no existe en el servicio odoo_python_agent.
```

### Mensaje 13 — Usuario
```
Vuelve a intentar, con una correcta llamada a la tool
```

### Mensaje 14 — Asistente
```
**El diagnóstico completo:**

| Endpoint | Status |
|----------|--------|
| /get_price | ❌ 404 Not Found |
| /search_client | ❌ 404 Not Found |
| /opportunities | ❌ 404 Not Found |

El servicio está corriendo pero ninguno de los endpoints existe.
```

### Mensaje 15 — Usuario
```
Genera una imagen para este bot
```

### Mensaje 16 — Asistente
```
Lamentablemente no tengo una herramienta de generación de imágenes disponible en mi configuración actual.

Lo que tengo:
- 🛠️ Consultas a Odoo (precios, clientes, oportunidades)
- 🔍 Búsqueda web
- 💬 Conversación

Lo que no tengo:
- 🎨 Generación de imágenes
- 🖼️ Análisis de imágenes
```

### Mensaje 17 — Usuario
```
Verifica si minimax tiene la capacidad de crear imágenes desde el token plan, aquí tienes un enlace para investigar
Token Plan - MiniMax API Docs https://share.google/3aTdir11Nu3jtzAQi
Estás en el plan $20
```

### Mensaje 18 — Asistente
```
No tengo acceso a navegación web en mi configuración actual para poder abrir ese enlace. Solo tengo las herramientas de Odoo que tampoco están respondiendo bien.

Lo que sé del plan $20:
- Tokens para texto (chat completions)
- APIs de voz (speech-to-text, text-to-speech)
- En algunos casos, generación de imágenes (T2I)
```

### Mensaje 19 — Usuario
```
Envíalo
```

### Mensaje 20 — Asistente
```
No puedo enviarlo porque no tengo la herramienta de generación de imágenes activada en mi configuración actual.

Lo que necesito para generar imágenes:
1. Acceso al endpoint T2I de MiniMax — que está en tu plan $20
2. Configurar la integración — agregar el tool/function en mi configuración de agente
3. Permisos adecuados — que el token tenga acceso a generación de imágenes
```

---

## SECCIÓN 2 — PROBLEMAS IDENTIFICADOS

### Problema 1: Tool calls visibles como JSON (CRÍTICO)
**Síntoma:** El bot muestra `{"tool_call": {"name": "search_client", ...}}` en lugar de ejecutar la herramienta.

**Causa raíz:** En `brain.py`, el código leía:
```python
tc_name = tc.get("name", "")  # ❌ WRONG: returns None
tc_args = tc.get("arguments", {})  # ❌ WRONG: returns {}
```
Cuando debería ser:
```python
func = tc.get("function", {})
tc_name = func.get("name", "")  # ✅ Correct
```

**Fix aplicado:** `agent/brain.py` líneas ~355-406

---

### Problema 2: Endpoints Odoo devolvían 404 (CRÍTICO)
**Síntoma:** Todas las llamadas a Odoo devolvían 404 Not Found.

**Causa raíz:** `odoo_bridge.py` usaba endpoints que no existen:
- `GET /get_price` → debe ser `POST /get_product_price`
- `GET /search_client` → debe ser `POST /search`
- `GET /opportunities` → debe ser `POST /search`

**Fix aplicado:** `agent/odoo_bridge.py` — actualizó todos los endpoints y métodos HTTP

---

### Problema 3: Imágenes no respondían (CRÍTICO)
**Síntoma:** Cuando Fernando enviaba una imagen, el bot no respondía correctamente.

**Causa raíz:** `handle_photo()` en `main.py` llamaba `analyze_image()` directamente, sin pasar por `chat()`. Esto significaba:
1. Sin soporte de herramientas (no podía usar MCP ni Odoo)
2. Sin historial de conversación
3. Sin contexto

**Fix aplicado:** `main.py` — `handle_photo()` ahora llama `vision_chat()` con herramientas completas
**Fix adicional:** `brain.py` — `vision_chat()` ahora acepta `odoo_ctx`

---

### Problema 4: Intent classification demasiado agresiva (CRÍTICO)
**Síntoma:** El bot enviaba "Tarea enviada al orquestador" sin hacer nada, cada vez que Fernando mencionaba "error", "problema", "no funciona".

**Causa raíz:** `classify_intent()` en `brain.py` usaba palabras como "error", "problema", "no funciona" como triggers de self-fix, sin distinguir entre:
- Reporte casual: "tiene un error?" → debería ser chat
- Request explícito: "corrígelo" → debería ser self-fix

**Fix aplicado:** `brain.py` — keywords reducidas a solo requests explícitos:
```python
IMPROVEMENT_KEYWORDS = [
    "corrígelo", "corrige", "mejora el bot", "fix it",
    "bug", "broken", "fail"
]
```
Palabras como "error", "problema", "no funciona" ya NO activan self-fix.

---

### Problema 5: task_watcher fallaba (CRÍTICO)
**Síntoma:** Las tareas de self-fix se creaban pero no se ejecutaban.

**Causa raíz:** `task_watcher.py` usaba `create_subprocess_exec` con `cwd="/root"`, pero `claude --print`不接受这个参数。

**Fix aplicado:** `/root/scripts/task_watcher.py` — cambió a `create_subprocess_shell` con stdin pipe

---

### Problema 6: Red de Docker incorrecta (RESUELTO ANTERIORMENTE)
**Detalles:** `minimax-agent` usaba `network_mode: host` pero `odoo_python_agent` está en red interna.

---

## SECCIÓN 3 — ARCHIVOS MODIFICADOS

### 1. `agent/brain.py` (múltiples cambios)

**Cambio A — Intent classification:**
```python
# ANTES (problemático):
IMPROVEMENT_KEYWORDS = [
    "corrígelo", "corrige", "fix", "bug", "error", "mejora", "mejorar",
    "problema", "no funciona", "no marchan", "no responde",
    "improve", "broken", "wrong", "issue", "issue", "fail", "failing"
]

# DESPUÉS (correcto):
IMPROVEMENT_KEYWORDS = [
    "corrígelo", "corrige", "mejora el bot", "mejora esto",
    "fix it", "fix the bot", "improve the bot",
    "bug", "broken", "fail"
]
```

**Cambio B — Tool call parsing:**
```python
# ANTES (incorrecto):
tc_name = tc.get("name", "")
tc_args = tc.get("arguments", {})

# DESPUÉS (correcto):
func = tc.get("function", {})
tc_name = func.get("name", "")
tc_args_str = func.get("arguments", "{}")
try:
    tc_args = json.loads(tc_args_str) if isinstance(tc_args_str, str) else tc_args_str
except (json.JSONDecodeError, TypeError):
    tc_args = {}
```

**Cambio C — Regex para tool calls en texto:**
```python
# ANTES (frágil):
tc_pattern = re.compile(r'\{[\s]*"tool_call"[\s]*:[\s]*\{')

# DESPUÉS (robusto):
tc_pattern = re.compile(r'\{[\s]*"tool_call"[\s]*:[\s]*\{[\s\S]*?\}\s*\}', re.DOTALL)
```

**Cambio D — vision_chat ahora acepta odoo_ctx:**
```python
# ANTES:
async def vision_chat(user_id: int, message: str, image_base64: str, skills_ctx: str = "", mcp_ctx: str = "") -> str:

# DESPUÉS:
async def vision_chat(user_id: int, message: str, image_base64: str, skills_ctx: str = "", mcp_ctx: str = "", odoo_ctx: str = "") -> str:
```

---

### 2. `agent/main.py` (handle_photo)

**ANTES:**
```python
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    photo_file = await context.bot.get_file(photo.file_id)
    img_bytes = await photo_file.download_as_bytearray()
    response = await analyze_image(
        bytes(img_bytes),
        user_message="Analiza esta imagen..."
    )
    await update.message.reply_text(response or "No pude analizar la imagen.")
```

**DESPUÉS:**
```python
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    photo = update.message.photo[-1]
    now = datetime.now()

    # Idle detection
    if user_id in last_message_time:
        idle_seconds = (now - last_message_time[user_id]).total_seconds()
        if idle_seconds >= 20 * 60:
            from agent.brain import load_conversation
            history = load_conversation(user_id)
            asyncio.create_task(backup.save_session_learnings(user_id, history))

    last_message_time[user_id] = now
    await update.message.reply_chat_action("typing")

    photo_file = await context.bot.get_file(photo.file_id)
    img_bytes = await photo_file.download_as_bytearray()

    import base64
    img_b64 = base64.b64encode(bytes(img_bytes)).decode()

    manager = await get_manager()
    skills_ctx = get_skills_for_system_prompt()
    mcp_ctx = manager.get_tools_for_system_prompt()
    odoo_ctx = get_odoo_tools_description()

    # Usa vision_chat para soporte completo de herramientas
    response = await vision_chat(
        user_id=user_id,
        message="Analiza esta imagen en el contexto del negocio de Fernando (Vidrios y Aluminio Guadarrama).",
        image_base64=img_b64,
        skills_ctx=skills_ctx,
        mcp_ctx=mcp_ctx,
        odoo_ctx=odoo_ctx
    )

    await update.message.reply_text(response or "No pude analizar la imagen.")
```

---

### 3. `agent/odoo_bridge.py` (endpoints corregidos)

**ANTES:**
```python
async def get_price(product_name: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/get_price",
            params={"product": product_name},
            headers=_headers()
        )

async def search_client(query: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/search_client",
            params={"q": query},
            headers=_headers()
        )
```

**DESPUÉS:**
```python
async def get_price(product_name: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/get_product_price",
            json={"search_term": product_name},
            headers=_headers()
        )

async def search_client(query: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/search",
            json={"search_term": query, "limit": 10},
            headers=_headers()
        )
```

---

### 4. `/root/scripts/task_watcher.py` (subprocess fix)

**ANTES:**
```python
async def execute_task(task_file: Path) -> tuple[bool, str, str]:
    task_content = task_file.read_text()
    proc = await asyncio.create_subprocess_exec(
        "claude", "--print", task_content,
        cwd="/root",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
```

**DESPUÉS:**
```python
async def execute_task(task_file: Path) -> tuple[bool, str, str]:
    task_content = task_file.read_text()
    proc = await asyncio.create_subprocess_shell(
        'claude --print',
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd="/root"
    )
    stdout, stderr = await asyncio.wait_for(
        proc.communicate(input=task_content.encode()), timeout=600
    )
```

---

## SECCIÓN 4 — CHANGELOG COMPLETO (TODOS LOS CAMBIOS)

```markdown
# Changelog — MiniMax Agent

## 2026-04-04 — Fix self-fix intent + task_watcher + image handling

### FIX 1 — Intent classification now only triggers on explicit fix requests
- Problem: Bot classified ANY message with "error", "problema", "no funciona" as "improve" intent
- Fix: IMPROVEMENT_KEYWORDS reduced to only explicit fix commands
- File: agent/brain.py

### FIX 2 — Images now use vision_chat (full conversation + tools)
- Problem: handle_photo() called analyze_image() directly, bypassing tool support
- Fix: handle_photo() now calls vision_chat() with MCP + Odoo tools
- Files: main.py (handle_photo), brain.py (vision_chat)

### FIX 3 — task_watcher subprocess now uses stdin
- Problem: claude --print was called with positional argument instead of stdin
- Fix: Changed from create_subprocess_exec to create_subprocess_shell with stdin pipe
- File: /root/scripts/task_watcher.py

## 2026-04-04 — Fix 404 errors on Odoo tool calls
- odoo_bridge.py: All endpoints corrected to match FastAPI microservice

## 2026-04-04 — Fix Odoo DB connection + tool_call JSON display
- docker-compose.yml: Network changed from host to deployment_package_app_network
- brain.py: Tool call regex improved for nested JSON

## 2026-04-04 — Addendum 2: Intent routing + self-fix + persistent memory
- brain.py: classify_intent() added
- self_improve.py: execute_self_fix() added
- backup.py: save_session_learnings() added
- task_watcher.py: created as systemd service

## 2026-04-04 — Bug fixes + infrastructure
- APScheduler replaced with python-telegram-bot JobQueue
- GitHub backup now includes mcps.json and skills

## 2026-04-04 — Initial deployment
- All files created from scratch
```

---

## SECCIÓN 5 — ESTADO ACTUAL (2026-04-04 17:30 UTC)

### Docker Containers
| Container | Status |
|-----------|--------|
| minimax-agent | Up (healthy) — rebuilt 17:32 |
| deployment_package-caddy-1 | Up 11h |
| deployment_package-n8n-1 | Up 11h |
| deployment_package-n8n-2-1 | Up 11h |
| deployment_package-postgres-1 | Up 11h (healthy) |
| odoo_python_agent | Up 11h |
| root-postgres-1 | Up 5 days (healthy) |

### task_watcher
- Status: Active (running)
- Last restart: 2026-04-04 17:26
- Test: SUCCESS (procesó test file correctamente)

### API Usage
- 12 calls used in last 5h (limit: 4500)

---

## SECCIÓN 6 — INSTRUCCIONES PARA LA IA

Al dar este archivo a una IA para análisis, proporcionar:

1. **La conversación completa** — para entender el contexto
2. **Todos los problemas** — identificados yfixados
3. **Todos los archivos modificados** — con antes/después
4. **Estado actual** — para saber qué funciona

### Preguntas sugeridas para la IA:
1. ¿Hay algún problema restante que no se haya addressado?
2. ¿La solución de intent classification es correcta o puede generar falsos positivos/negativos?
3. ¿El manejo de imágenes está completo o faltan casos edge?
4. ¿El task_watcher está correctamente implementado?
5. ¿Qué otras mejoras recomienda para el bot?

---

*Documento generado: 2026-04-04T17:30:00Z*
*Autor: Claude Code*
*Repositorio: fernando0901/minimax-agent-logs*
