# Reglas del Directorio Backend (`backend/`)

## 1. Índice Rápido de Líneas (Lee solo el rango necesario)
- **`backend/brain.py` (1644 líneas)**:
  - `L41-L75`: Rutas de datos (`backend/data/`) y personalidad de Capri (`DEFAULT_PERSONALITY_ES`, `SAFETY_AND_MACHINERY_ES`).
  - `L77-L414`: `TOOLS_SCHEMA` (definición JSON de las 13 herramientas para function calling).
  - `L416-L498`: Filtros de naturalidad (`split_followup` con `|||`, `clean_and_fresh_reply`: `Fresh`, `Unclosed`, `Sparing`).
  - `L500-L803`: `CapriDeepMemory` (notas en `me.md`, auto-aprendizaje `learn_from_message`, `transcribe`, búsqueda asociativa `recall_bm25`).
  - `L805-L887`: Captura de pantalla nativa GDI a PNG base64 sin dependencias externas (`capture_screen_png_base64`).
  - `L889-L940`: `PROVIDER_ENDPOINTS`, `detect_provider_from_key` y `BrainStatus`.
  - `L942-L1093`: Inicialización de `CapriBrain`, carga/guardado de `brain_config.json` (`save_config`) y `get_status`.
  - `L1095-L1278`: `build_system_prompt`, `ask_with_tools`, `look_at_screen_with_vision` (`SAW:`/`SAY:`), `check_screen_lookout` y `react_to_event`.
  - `L1280-L1644`: Clientes HTTP multi-proveedor (`_call_active_llm_with_tools`, `_call_openai_compatible`, `_call_anthropic`, `_call_ollama`, `_call_vision_llm`).

- **`backend/router_llm.py` (608 líneas)**:
  - `L29-L41`: Regex de autodetección de API Keys pegadas en el chat (`_PASTED_KEY_RE`) y `AgentResponse`.
  - `L43-L185`: `CapriRouterAgent.process_user_message` (Flujo de 4 pasos: 0. API Key pegada -> 1. Visión de pantalla -> 2. Intención rápida 0ms + comentario LLM -> 3. Tool Calling Agéntico -> 4. Fallback en personaje).
  - `L187-L365`: `_execute_tool_call` (ejecutor real de todas las herramientas de `TOOLS_SCHEMA`).
  - `L367-L608`: `_handle_intent` (atajos de 0ms de `backend/intents.py`) y `_character_fallback`.

## 2. Convenciones de Código en `backend/`
- **Cero dependencias innecesarias en `brain.py`**: Las llamadas HTTP a Gemini, Groq, NVIDIA NIM, OpenRouter, Claude, OpenAI, DeepSeek, Ollama y LM Studio usan `urllib.request` de la librería estándar para máxima portabilidad y rapidez.
- **Seguridad de API Keys**: Nunca hardcodees API keys en el código ni las registres sin enmascarar en logs o `me.md`. Usa `brain_config.json` o variables de entorno.
- **Fallback sin herramientas (`Toolless`)**: Si un modelo o proveedor devuelve HTTP `400`/`404`/`422` al enviar `tools`, conserva siempre el reintento automático con `enable_tools=False`.
