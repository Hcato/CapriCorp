---
name: capri-team-orchestrator
description: >-
  Guía de orquestación en equipo para desarrollar Capri Desktop Companion sin agotar la cuota de tokens. Úsalo cuando una tarea abarque múltiples capas (Router IA + Servidor WebSocket + Frontend Flutter) o requiera investigación, pruebas visuales o revisión de código con subagentes.
---

# Orquestador de Equipo para Capri (`capri-team-orchestrator`)

Cuando una funcionalidad o corrección en Capri involucre varias partes del sistema, actúa como **Líder Técnico** y divide el trabajo siguiendo este protocolo para minimizar el gasto de tokens en la conversación principal:

## 1. División de Roles del Equipo
1. **Arquitecto de Cerebro y Enrutador (`capri-router-brain`)**:
   - Ámbito exclusivo: `backend/brain.py`, `backend/router_llm.py`, `backend/intents.py`.
   - Responsabilidad: Proveedores de API Key, prompts en personaje, memoria BM25 (`me.md` / `memories.md`) y `TOOLS_SCHEMA`.
2. **Ingeniero de Servidor y Habilidades PC (`capri-backend-ws`)**:
   - Ámbito exclusivo: `backend_test_server.py`, `backend/voice_engine.py`, `backend/pc_hands.py`, `backend/media_player.py`, `backend/game_agent.py`, `backend/lookout.py`, `backend/reminders_dated.py`, `backend/clones_manager.py`.
   - Responsabilidad: Eventos WebSocket (`ws://127.0.0.1:8765`), TTS/STT y automatización Win32.
3. **Ingeniero de Overlay Flutter (`capri-flutter-overlay`)**:
   - Ámbito exclusivo: `frontend/lib/` y `frontend/shaders/`.
   - Responsabilidad: `AssistantController`, widgets Cyberpunk, animaciones y recepción de eventos WebSocket.
4. **Explorador de Código (Subagente `research`)**:
   - Cuándo invocarlo: Cuando no sepas en qué archivo o línea está un comportamiento específico. Pídele que busque y devuelva **únicamente la ruta del archivo, el rango de líneas (`Lxx-Lyy`) y un resumen de 5 líneas**.
5. **Revisor de Calidad (Subagente `code-reviewer` de CodeRabbit)**:
   - Cuándo invocarlo: Al terminar una funcionalidad multi-archivo antes de hacer commit, para revisar errores de concurrencia, fugas de timers o desajustes en el contrato JSON entre Python y Flutter en su propio contexto aislado.

## 2. Flujo de Trabajo Paso a Paso (Anti-Desperdicio de Tokens)
1. **Definir el Contrato JSON Primero**: Antes de editar archivos, define en 3-5 líneas qué evento JSON se enviará entre `backend_test_server.py` y `assistant_controller.dart` (ej. `{"event": "mi_evento", "payload": {...}}`).
2. **Lectura Quirúrgica por Rangos**: Consulta los mapas de líneas en `capri-router-brain`, `capri-backend-ws` o `capri-flutter-overlay` y usa `read_file` con rangos de máximo 80-120 líneas.
3. **Edición Directa y Verificación Ligera**:
   - En Python: ejecuta `.\.venv\Scripts\python.exe -m py_compile <archivo.py>`.
   - En Flutter: ejecuta `flutter analyze <archivo.dart>`.
4. **Higiene de Contexto**: Si la tarea ya completó una fase importante, recomienda al usuario ejecutar `/compact` antes de pasar al siguiente módulo.
