# Reglas Globales del Proyecto Capri Desktop Companion

## 1. Presupuesto Estricto de Tokens y Contexto (Regla de Oro)
Este repositorio contiene archivos extensos (`backend/brain.py` ~1644 líneas, `frontend/lib/domain/state/assistant_controller.dart` ~889 líneas, `backend_test_server.py` ~808 líneas, `backend/router_llm.py` ~608 líneas). Para evitar agotar la cuota de tokens en un solo prompt:

- **PROHIBIDO leer archivos grandes completos**: Nunca llames a `read_file` sin `StartLine` y `EndLine` sobre `backend/brain.py`, `backend/router_llm.py`, `backend_test_server.py` o `assistant_controller.dart`.
- **Usa primero los Skills del proyecto (`.agents/skills/`)**: Activa el skill correspondiente (`capri-router-brain`, `capri-backend-ws`, `capri-flutter-overlay`) para consultar el mapa exacto de líneas antes de leer o editar código.
- **Delega búsquedas amplias**: Si necesitas explorar varios archivos o buscar un bug transversal, delega la investigación al subagente `research` para mantener limpio el contexto principal.

## 2. Arquitectura General del Sistema
- **Servidor Principal y Orquestador WebSocket**: `backend_test_server.py` (`ws://127.0.0.1:8765`).
- **Cerebro IA y Enrutador Multi-Proveedor (API Keys + Local)**: `backend/brain.py` (`CapriBrain`, `CapriDeepMemory`) y `backend/router_llm.py` (`CapriRouterAgent`).
- **Frontend Overlay (Flutter Windows)**: `frontend/lib/` conectado por WebSocket mediante `AssistantController` (`frontend/lib/domain/state/assistant_controller.dart`).
- *(Nota)*: Los archivos en la raíz `llm_router.py`, `main.py`, `audio_listener.py`, `voice_synth.py` y `config.py` pertenecen al prototipo inicial "Claret"; el motor activo de Capri reside en `backend/` + `backend_test_server.py` + `frontend/`.

## 3. Sincronización de Contratos (Backend <-> Frontend)
- Todo evento JSON emitido por `broadcast_event({...})` en `backend_test_server.py` o `extra_events` en `backend/router_llm.py` debe tener su manejador correspondiente en `frontend/lib/domain/state/assistant_controller.dart` y `frontend/lib/data/models/assistant_event.dart`.
- Toda herramienta declarada en `TOOLS_SCHEMA` (`backend/brain.py`) debe implementarse en `CapriRouterAgent._execute_tool_call` (`backend/router_llm.py`).
