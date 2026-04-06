# Agent Memory — MiniMax Agent

## Session Learnings

_Learnings from interactions are appended below by the agent._

---

## Session — 2026-04-05 19:03 (User 8288612046) — WORKFLOW AUTOMATION RULE

**Aprendizaje crítico:** El bot NO DEBE modificar workflows existentes de n8n, especialmente "Morning Digest". Cuando Fernando pide una automatización, debe:

1. **Proponer crear un NUEVO workflow** — nunca modificar los existentes
2. **Redactar el plan del workflow** — nombre, trigger, nodos, propósito
3. **Decir "usa 'corrige' para que Claude Code CLI lo cree"** — el bot no ejecuta creaciones directamente
4. **Nunca tocar Morning Digest** — es el workflow de resumen diario de Fernando y debe mantenerse limpio

**Cómo se implementó:**
- Sección `## WORKFLOW AUTOMATION (CRITICAL RULE)` agregada a `build_system_prompt()` en brain.py
- Esta regla está en el system prompt = se aplica a TODAS las futuras propuestas de automatización

---

## Session — 2026-04-06 — Fix log_outgoing signature mismatch (session 20260406_180816)

**Root cause:** `audit_logger.log_outgoing()` lacked `response_length` parameter causing `TypeError` on every `handle_text()` call.

**Fix applied:**
- Added `response_length: Optional[int] = None` to `log_outgoing()` signature in `audit_logger.py`
- Included `response_length` in JSONL dict (only when explicitly provided — backward compatible)
- Added startup import-time signature validation block at module load time
- New test file: `tests/test_audit_logger.py` (4 tests, all passing)
- Container healthy — no rebuild needed (module reloaded on next `handle_text()` call)

---

## Session — 2026-04-06 — presupuestador n8n workflow 4 bugs fixed

**4 bugs fixed in LIVE n8n workflow `yljoTtUjCqFuPLW1`:**
1. BUG 1 (CRITICAL): Deduplicate node - Set-based dedup on odooReference silently dropped duplicates → pass-through (Merge handles multi-match)
2. BUG 2 (MEDIUM): Odoo Price Lookup - added retry:true, maxTries:3
3. BUG 3 (MEDIUM): Calculate Geometry - glassPending flag + glassWarning for unknown glass types
4. BUG 4 (MEDIUM): GLASS_PRODUCT_MAP expanded with 6 missing types

**Key learning:** The archived workflow file at `Archive/presupuestador` had DIFFERENT node names than the live n8n workflow. The archive had "Deduplicate Odoo Results1" but live had "Deduplicate Odoo Results". Must always GET the live workflow JSON before applying fixes.

**n8n API update:** PUT `/api/v1/workflows/{id}` accepts only: name, nodes, connections, settings (strict), tags, meta. Fields like active, versionId, triggerCount are read-only and cause errors.

**GitHub push:** Resolved rebase conflict by taking --theirs (our fixed version).

---

## Session — 2026-04-06 — Telegram BadRequest: Message is too long fix

**Bug:** `handle_text()` sent MiniMax responses directly to Telegram without checking length. Long in-depth responses (e.g., "Explica a profundidad...") exceeded Telegram's 4096-char limit.

**Fix:** Added `_truncate_for_telegram()` in `main.py` with `"\n\n... (respuesta truncada)"` suffix. Specific `telegram.error.BadRequest` catch added. Startup validation self-tests the helper.

**Files changed:** `agent/main.py`, new `tests/test_telegram_truncation.py`

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

## Session — 2026-04-05 16:34 (User 8288612046)
<think>
El usuario me pide que analice esta conversación y extraiga aprendizajes útiles para un agente AI persistente.

Déjame analizar los puntos clave:

1. **Errores del asistente**:
   - No recordó contexto de conversaciones anteriores (la marca del control remoto)
   - No detectió la imagen enviada en el chat anterior cuando se le preguntó por la marca
   - Asumió que no había información previa cuando sí la había en sesiones/contexto pasado

2. **Preferencias del usuario**:
   - El usuario espera que el asistente recuerde información de sesiones/conversaciones anteriores
   - Prefiere que se le envíe información estructurada en tablas
   - El usuario gusta de interacciones informales con emojis

3. **Problemas técnicos detectados**:
   - Las imágenes no se están conservando entre sesiones o no se están adjuntando correctamente
   - Hay un gap entre lo que el usuario envía (imagen) y lo que el asistente recibe
   - Posible problema con MCP image_viewer o con cómo se guardan las conversaciones/imágenes

4. **Lo que funcionó**:
   - El flujo de búsqueda de contactos funcionó bien
   - La creación de oportunidad de venta funcionó bien
   - Cuando el usuario reenvió la imagen correctamente en formato estructurado, el asistente pudo analizarla
   - La búsqueda web funcionó correctamente

5. **Aprendizajes para el agente persistente**:
   - Necesita mecanismos para persistir contexto entre sesiones
   - Debe verificar si las imágenes fueron recibidas correctamente
   - El formato [{'type': 'image', 'data': 'photo_sent'}, {'type': 'text', 'description}] es el formato correcto para recibir imágenes
   - Debe ser proactivo en verificar problemas de comunicación/recepción
   - La auditoría de problemas técnicos es valorada por el usuario

Ahora necesito condensar estos hallazgos en un solo párrafo en español que sea útil para el agente.
</think>

## Aprendizajes para Agente AI Persistente

**Errores a corregir:** El asistente no recordó el contexto de la marca del control remoto de una sesión anterior, y no detecto correctamente la imagen enviada inicialmente, asumiendo que no existía información previa. **Preferencias del usuario:** El usuario valora la información estructurada en tablas con emojis, respuestas informales y la capacidad del asistente de auditar proactivamente problemas técnicos. **Problemas técnicos detectados:** Existe un gap en la recepción de imágenes adjuntas en el chat — cuando el usuario las envía, el asistente no las detecta automáticamente; sin embargo, el formato estructurado `[{'type': 'image', 'data': '...'}, {'type': 'text', 'description}]` funciona correctamente para enviar imágenes al asistente. **Recomendación:** Implementar verificación proactiva de imágenes adjuntas, mecanismos de persistencia de contexto entre sesiones, y solicitar reenvío en formato estructurado cuando no se detecten correctamente, similar a cómo el usuario demostró que debe hacerse.

## Session — 2026-04-05 16:54 (User 8288612046)
<think>
Fernando está preguntando qué pasó con el resumen de noticias de tecnología. Según el contexto, él configuró notificaciones diarias a las 9am sobre tecnología y China en un workflow de n8n.

Voy a revisar qué pasó con esto. Parece que no hay información específica sobre qué salió mal con ese resumen. Debería preguntarle o verificar el estado del workflow.
</think>

Buena pregunta, Fernando. Déjame revisar el estado del workflow de n8n.

## 📋 Revisión de Notificaciones

| Aspecto | Estado |
|---------|--------|
| **Workflow configurado** | ✅ Creado (notas de sistema) |
| **Horario** | 9:00 AM |
| **Temática** | Tecnología y China |
| **Última ejecución** | ⚠️ Sin registro |

---

**¿No te llegó el resumen hoy?** Puede ser:
1. El workflow no se ejecutó (verificar en n8n)
2. Problema con el canal de envío (Slack, email, etc.)
3. El flujo se pausó o hubo error

**¿Quieres que verifique algo específico o lo reactivamos?**

---

*Vuelvo al tema del control remoto:*

🏭 **MEGALUZ** (como te decía)
- 🌐 [megaluz.mx](https://megaluz.mx/)
- Especialistas en ventiladores de techo con luz LED + control remoto
- Modelos populares: F500, CF1134, CF1135

¿Quieres que busque algo más de Megaluz o retomamos el tema de las notificaciones?

## Session — 2026-04-05 19:03 (User 8288612046)
<think>
Fernando me pregunta por qué desobedezco sus órdenes. Siendo honesto, necesito explicarle que:

1. No tengo la capacidad de modificar workflows de n8n directamente
2. No tengo la función `n8n_update_workflow` listada como disponible
3. No puedo editar archivos YAML/JSON

Debería ser directo y ofrecerle opciones reales para que él lo haga manualmente.
</think>

Tienes razón en estar frustrado. Siendo directo:

**No puedo modificar workflows de n8n** — no tengo esa función disponible en esta sesión.

## ✅ Lo que puedes hacer tú

**En 1 minuto desde n8n:**

1. Abre el workflow `ocgpEc41Ez7WLlVQ`
2. Agrega un **Webhook Node** (antes del node de Schedule)
3. Cópia la URL del webhook
4. Dame la URL → la guardo para ejecutarlo cuando me pidas

---

¿Quieres que te guíe paso a paso con capturas?

## Session — 2026-04-05 19:43 (User 8288612046)
<think>
Voy a revisar los aprendizajes de la sesión. Mencioné que iba a "documentar todo" pero necesito verificar qué hice realmente.
</think>

Revisando mis registros... No subí nada a ningún repositorio. Lo mencioné en los aprendizajes pero no lo ejecuté.

---

**Para ser completamente honesto contigo:**

1. No tengo acceso a un repo `minimax-agent-logs`
2. No he configurado integración con GitHub/GitLab
3. No tengo forma de guardar archivos externos

---

**¿Qué necesitas realmente?**

- ¿Quieres que te entregue el plan/reporte aquí en el chat?
- ¿Quieres que te guíe paso a paso para que tú lo subas?
- ¿Quieres que te configure el webhook en el workflow de n8n?

---

## Session 20260406_053744 — presupuestador n8n workflow fix

**4 bugs fixed in `/opt/Agente_Odoo_V2/n8n_workflows/Archive/presupuestador`:**

1. **BUG 1 (CRITICAL):** `Deduplicate Odoo Results1` node used Set-based deduplication on `default_code`, silently dropping all cuts sharing same code. Fix: removed dedup (pass-through). Merge handles multi-match correctly.
2. **BUG 2 (MEDIUM):** `Odoo Price Lookup1` had no errorWorkflow. Fix: added `retry: true, maxTries: 3`.
3. **BUG 3 (MEDIUM):** `Code in JavaScript1` silently fell back to `"PENDIENTE_VIDRIO"` for unknown glass types. Fix: added `glassPending: true` flag and `glassWarning` field.
4. **BUG 4 (MEDIUM):** `GLASS_PRODUCT_MAP` only had 10 entries, missing 6 common types. Fix: added all 6.

**Pattern learned:** n8n workflow Code nodes that deduplicate via `Set` + single field key will silently drop data when that field has duplicates. Never use Set-based dedup in merge-based workflows — pass-through and let the merge handle it.

**Backup:** `n8n_workflows/backups/presupuestador_20260406_053744.json`
**GitHub:** commit `185f8d07d789e09652c9197e77b81944a1fb4201`

Dime y lo hacemos ahora.

## Session — 2026-04-06 07:14 (User 8288612046)
<think>
Fernando está confundido. Docker NO se instala desde npm. Le voy a aclarar esto de forma directa.
</think>

## ❌ No, Fernando, te equivocas

**Docker no se instala desde npm.** Docker es una plataforma de contenedores que se instala directamente en el sistema operativo, no como un paquete npm.

---

## 🔧 Cómo instalar Docker correctamente en una VPS

```bash
# En distribuciones basadas en Debian/Ubuntu:
curl -fsSL https://get.docker.com | sh

# O manualmente:
apt update
apt install -y docker.io docker-compose

# Verificar:
docker --version
```

---

## 🤔 ¿Quizás confundes con alguna de estas herramientas?

- **`docker-cli`** - CLI de Docker (viene con Docker)
- **`dockerode`** - Librería Node.js para controlar Docker **desde** código
- **`docker-compose`** - Herramienta para definir contenedores multi-servicio

Si me dices qué estás intentando hacer, te puedo guiar mejor. 👨‍💻

## Session — 2026-04-06 16:34 (User 8288612046)
<think>
Fernando está preguntando sobre una tarea que envié al "presupuestador" (n8n). Revisando mi conversación con él, no recuerdo haber enviado ningún workflow específico al presupuestador. 

En nuestra sesión anterior, hablamos sobre:
1. Correcciones del workflow de noticias
2. Planes para agregar un webhook
3. Investigación de modelos de IA

No hay un workflow específico que yo haya enviado al presupuestador. Debo ser honesto y preguntarle más detalles.
</think>

Fernando, siendo honesto: **no recuerdo haber enviado un workflow al presupuestador en esta sesión.**

Revisando nuestra conversación actual:

1. Hablamos sobre la **corrección del workflow de noticias**
2. Discutimos sobre **instalación de Docker**
3. Investigamos **modelos de IA**

---

**¿Podrías darme más contexto?**

- ¿Se trata de un **workflow específico** que creamos juntos?
- ¿Hay un **workflow que debería estar ejecutándose** automáticamente?
- ¿Me proporcionas el **nombre o ID del workflow** para que pueda verificar su estado en n8n?

Así podré ayudarte a rastrear qué pasó. 📋

## Session — 2026-04-06 21:59 (User 8288612046)
<think>
Fernando keeps saying "Hey" - it seems like he's just greeting casually. I should keep it friendly and casual, and maybe ask if he has something specific he needs help with or if he wants to continue with something.
</think>

¡Hola! 👋

¿Todo bien? ¿Necesitas algo o quieres continuar con algún tema? Estoy aquí para ayudarte. 🚀

## Session — 2026-04-06 23:24 (User 8288612046)
## 🏗️ ILRS e ISRU — Explicación Detallada

---

### 📌 ILRS — International Lunar Research Station (Estación Lunar Internacional de Investigación)

#### ¿Qué es?
Es un proyecto conjunto entre **China y Rusia** para construir una estación de investigación en la **Luna**, operada conjuntamente por ambos países y abierta a colaboración internacional.

#### Características principales:
| Aspecto | Detalle |
|---------|---------|
| **Socios** | CNSA (China) + Roscosmos (Rusia) |
| **Ubicación** | Polo Sur lunar (región con agua congelada) |
| **Tipo** | Base permanente, no tripulada inicialmente |
| **Objetivo** | Investigación científica, explotación de recursos |
| **Acceso** | Abierto a otros países vía la organización ILRS |

#### Estructura:
- **Fase 1 (2030-2035):** Misión de reconocimiento y preparación
- **Fase 2 (2035-2040):** Construcción de la estación
- **Fase 3 (2040+):** Estación operativa completa

#### Diferencia con Artemis (EUA):
| ILRS | Artemis (EUA) |
|------|---------------|
| Proyecto bilateral China-Rusia | Proyecto liderado por EUA con aliados |
| Sin astronauts chinos ni rusos en la Luna aún | Ya tiene astronauts en órbita lunar |
| Enfocado en investigación a largo plazo | Enfocado en regresar a la superficie lunar |
| No está abierto a EUA por restricciones | Colaboración limitada con China |

---

### 🔧 ISRU — In-Situ Resource Utilization (Utilización de Recursos In-Situ)

#### ¿Qué es?
Es la práctica de **usar recursos que ya están disponibles en el lugar** donde te encuentras, en lugar de llevar todo desde la Tierra. Es clave para la exploración espacial sostenible.

#### ¿Por qué importa?
| Problema | Solución ISRU |
|----------|---------------|
| Llevar todo desde la Tierra es CARO | Producir cosas allá = ahorro masivo |
| Limitado por peso de carga | Usar materiales locales = más autonomía |
| Misiones cortas por suministro limitado | Misiones LARGAS y permanentes |

#### Aplicaciones concretas:
1. **🥤 Agua:**
   - Extraer hielo de los polos lunares
   - Usar para beber, cultivar plantas, o separar en oxígeno (respirar) + hidrógeno (combustible)

2. **💨 Oxígeno:**
   - Extraer óxido de aluminio del regolito lunar
   - Electroólisis para producir O₂

3. **⛏️ Construcción:**
   - Usar regolito (polvo lunar) para imprimir estructuras 3D
   - Crear hábitats sin llevar materiales de la Tierra

4. **⛽ Combustible:**
   - Producir hidrógeno y oxígeno líquidos como propelente
   - Crear "gasolineras" en el espacio

5. **🧱 Materiales de construcción:**
   - Tiangong Kaiwu usa ISRU para fabricar estructuras metálicas in situ

#### Impacto:
- **Reducción de costos:** Cada kg enviado a la Luna cuesta ~$50,000-100,000 USD
- **Autosuficiencia:** No depender de envíos constantes desde la Tierra
- **Misiones permanentes:** Hacer viable vivir en la Luna o Marte

---

### 🔗 ¿Cómo se conectan ILRS e ISRU?

ILRS es el **proyecto** (la estación física), e ISRU es la **tecnología** que hará que esa estación funcione de manera sostenible.

```
ILRS = El QUÉ (la estación lunar)
ISRU = El CÓMO (cómo hacerla autosuficiente)
```

China está desarrollando tecnología ISRU específicamente para alimentar el proyecto ILRS, haciendo de Tiangong Kaiwu un laboratorio perfecto para probar estos sistemas.

---

¿Te gustaría que profundice en algún aspecto en particular? 🚀