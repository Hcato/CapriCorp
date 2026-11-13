---
name: capri-backend-ws
description: >-
  Especialista en el servidor WebSocket (`backend_test_server.py`), motor de voz (`backend/voice_engine.py`, Kokoro 82M, Groq Whisper STT, Windows TTS) y habilidades de sistema en Windows (`pc_hands.py`, `media_player.py`, `game_agent.py`, `lookout.py`, `clones_manager.py`, `reminders_dated.py`). Úsalo para depurar eventos en tiempo real, audio/TTS/STT o automatización de PC.
---

# Especialista en Servidor WebSocket, Voz y Habilidades de PC (`capri-backend-ws`)

## 1. Mapa Exacto de `backend_test_server.py` (808 líneas)
Usa siempre `read_file` con `StartLine` y `EndLine` según la tabla:

| Rango de Líneas | Función / Bloque | Propósito |
| :--- | :--- | :--- |
| `L1-L60` | Imports, `AGENT`, `VOICE`, `build_brain_status_event`, `build_voice_status_event` | Instanciación global en `ws://127.0.0.1:8765` y payloads de estado (`brain_status`, `voice_status`). |
| `L62-L143` | `emit_spoken_say`, `handle_user_chat` | Síntesis de voz en hilo de fondo (`audio_b64`), cálculo de duración de habla, envío de segundo pensamiento (`follow_up` tras `|||`) y reactivación de escucha en llamada continua. |
| `L145-L211` | `handle_voice_listen`, `handle_minigame_reaction`, `handle_screen_glance` | Grabación de micrófono + transcripción STT (`Groq Whisper`), reacciones de minijuego y miradas GDI a la pantalla. |
| `L213-L305` | `background_monitor_loop` | Bucle cada `1.5s`: monitorea música activa (GSMTC/Win32), recordatorios vencidos (`dated_reminders` y `hands`), condiciones visuales (`lookout`), `GameSense` y `proactive_glances`. |
| `L307-L544` | `handler(websocket)` | Router de eventos entrantes desde Flutter (`user_message`, `voice_listen_toggle`, `voice_call_toggle`, `voice_tts_toggle`, `voice_pack_download`, `get_brain_status`, `configure_brain`, `minigame_event`, `screen_glance`, `media_command`, `perch_window`, `game_autopilot`, `gamesense_toggle`, `lookout_*`, `reminder_*`, `clones_*`, `hologram_toggle`). |
| `L546-L808` | `broadcast_event`, `interactive_console`, `main` | Envío seguro a todos los clientes Flutter conectados (ocultando `audio_b64` en logs) y menú interactivo de consola (`[1]`-`[9]`, `[b]`, `[v]`, `[c]`, `[r]`, `[x]`, `[o]`, `[t]`, `[y]`). |

---

## 2. Módulos Especializados en `backend/`
- **`backend/voice_engine.py`**: Síntesis de voz (Kokoro 82M `capri-voice-1` Speaker 53 / Dora Speaker 28, Windows WinRT Laura con pitch/speed WSOLA, ElevenLabs, armonizador Cyberpunk) y STT con micrófono + Groq Whisper.
- **`backend/pc_hands.py`**: Apertura de apps/sitios, gestión de ventanas Win32 (`focus`, `minimize`, `maximize`, `close`), detección de bordes de ventanas (`find_best_perch_ledge`) y temporizadores cortos.
- **`backend/media_player.py`**: Control multimedia de Windows (Spotify, YouTube, VLC) y consulta de pista actual (`poll_current_tune`).
- **`backend/game_agent.py`**: Piloto automático de videojuegos (`explore`, `combat`, `circle`, `jump_spam`) y sensor visual `GameSense`.
- **`backend/lookout.py`**: Vigilante periódico de condiciones visuales en pantalla.
- **`backend/reminders_dated.py`**: Recordatorios persistentes en lenguaje natural.
- **`backend/clones_manager.py`**: Enjambre de clones Chibi y modo Holograma (`click-through`).

---

## 3. Verificación Rápida
Para verificar que los módulos compilan sin errores de sintaxis tras un cambio sin levantar todo el bucle interactivo:
```powershell
.\.venv\Scripts\python.exe -m py_compile backend_test_server.py backend/brain.py backend/router_llm.py
```
