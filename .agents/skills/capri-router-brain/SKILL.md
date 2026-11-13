---
name: capri-router-brain
description: >-
  Especialista en el modelo enrutador y cerebro multi-proveedor de Capri (`backend/brain.py`, `backend/router_llm.py`, `backend/intents.py`). Úsalo cuando el usuario pida modificar el enrutamiento por API Key (Gemini, Groq, NVIDIA, OpenRouter, Claude, OpenAI, DeepSeek, Ollama, LM Studio), añadir o depurar herramientas (Tool Calling), ajustar la personalidad/filtros de voz o gestionar la memoria BM25 de 3 capas.
---

# Especialista en Cerebro IA y Modelo Enrutador (`capri-router-brain`)

## 1. Regla de Eficiencia de Contexto
**NUNCA** leas `backend/brain.py` (1644 líneas) ni `backend/router_llm.py` (608 líneas) completos. Usa siempre `read_file` con `StartLine` y `EndLine` guiándote por este mapa:

### Mapa Exacto de `backend/brain.py`
| Rango de Líneas | Sección / Símbolos | Propósito |
| :--- | :--- | :--- |
| `L41-L75` | `DATA_DIR`, `DEFAULT_PERSONALITY_ES`, `SAFETY_AND_MACHINERY_ES` | Rutas (`brain_config.json`, `me.md`, `memories.md`) y prompt base de Capri. |
| `L77-L414` | `TOOLS_SCHEMA` | Catálogo OpenAI/Anthropic de 13 herramientas (`open_app`, `open_website`, `play_music`, `media_control`, `window_control`, `move_yourself`, `mini_game`, `game_autopilot`, `remind`, `remember`, `look_at_screen`, `lookout`, `dated_reminder`, `clones`, `hologram`). |
| `L416-L498` | `split_followup`, `clean_and_fresh_reply` | División por `|||` y filtros `Fresh`, `Unclosed` y `Sparing` (evita abusar de "choom"). |
| `L500-L803` | `CapriDeepMemory` | Auto-aprendizaje (`learn_from_message`), notas en `me.md`, transcripciones diarias y búsqueda asociativa `recall_bm25` en 0ms. |
| `L805-L887` | `capture_screen_png_base64` | Captura de pantalla GDI Win32 (`640x360`) codificada a PNG base64 en memoria sin librerías externas. |
| `L889-L940` | `PROVIDER_ENDPOINTS`, `detect_provider_from_key`, `BrainStatus` | Autodetección de proveedor según prefijo de API key (`AIza`/`AQ.` -> `google`, `gsk_` -> `groq`, `nvapi-` -> `nvidia`, `sk-or-` -> `openrouter`, `sk-ant-` -> `anthropic`, `sk-` -> `openai`/`deepseek`). |
| `L942-L1093` | `CapriBrain.__init__`, `_load_config`, `save_config`, `get_status` | Persistencia en `backend/data/brain_config.json` y sondas locales a Ollama (`:11434`) y LM Studio (`:1234`). |
| `L1095-L1278` | `build_system_prompt`, `ask_with_tools`, `look_at_screen_with_vision`, `check_screen_lookout`, `react_to_event` | Ciclo agéntico completo con pre-ejecución o invocación dinámica de herramientas y visión (`SAW:` / `SAY:`). |
| `L1280-L1644` | `_call_active_llm_with_tools`, `_call_openai_compatible`, `_call_anthropic`, `_call_ollama`, `_call_vision_llm` | Clientes HTTP nativos (`urllib.request`), rotación automática en error `429` de Groq y fallback `Toolless` (`enable_tools=False`). |

### Mapa Exacto de `backend/router_llm.py`
| Rango de Líneas | Sección / Símbolos | Propósito |
| :--- | :--- | :--- |
| `L29-L60` | `_PASTED_KEY_RE`, `AgentResponse`, `CapriRouterAgent.__init__` | Inicialización de subsistemas y detección de API keys pegadas directamente en el chat. |
| `L61-L185` | `_build_live_context`, `process_user_message`, `react_to_live_event` | Pipeline de 4 etapas: `0.` Auto-guardado de API Key pegada -> `1.` Visión de pantalla -> `2.` Atajo rápido 0ms (`intents.py`) comentado por el LLM -> `3.` Conversación libre + Tool Calling -> `4.` Fallback local en personaje. |
| `L187-L365` | `_execute_tool_call` | Ejecución real en Windows de cada herramienta de `TOOLS_SCHEMA` y generación de `extra_events` para Flutter. |
| `L367-L608` | `_handle_intent`, `_character_fallback` | Respuestas inmediatas de 0ms y respuestas offline en personaje. |

---

## 2. Procedimiento para Añadir una Nueva Herramienta (Tool Calling)
1. **Declarar esquema**: Lee `backend/brain.py` (`L380-L414`) y añade la definición en `TOOLS_SCHEMA`.
2. **Implementar ejecutor**: Lee `backend/router_llm.py` (`L330-L365`) y añade la rama `if t == "nueva_herramienta":` en `_execute_tool_call`, retornando `(mensaje_resultado, lista_eventos_ws)`.
3. **Atajo opcional de 0ms**: Si requiere detección instantánea por regex sin esperar al LLM, añádelo en `backend/intents.py` y su manejador en `_handle_intent` (`backend/router_llm.py`).
4. **Sincronizar Frontend**: Si emite un nuevo `event` por WebSocket, usa el skill `capri-flutter-overlay` para registrarlo en `assistant_controller.dart`.
