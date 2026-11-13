---
name: capri-flutter-overlay
description: >-
  Especialista en el Frontend de Flutter para Windows (`frontend/lib/`), incluyendo `AssistantController`, el overlay transparente (`CharacterOverlay`), paneles Cyberpunk (`CapriBrainPanel`, `CyberpunkMiniPlayer`, `CapriMiniGamesPanel`, `SpeechBubble`), animaciones de sprites/shaders GLSL y cliente WebSocket. Úsalo para cualquier cambio visual, de estado o de UI en Flutter.
---

# Especialista en Frontend Flutter Overlay (`capri-flutter-overlay`)

## 1. Mapa Exacto de `frontend/lib/domain/state/assistant_controller.dart` (889 líneas)
Usa siempre `read_file` con `StartLine` y `EndLine` según este índice:

| Rango de Líneas | Sección / Métodos | Propósito |
| :--- | :--- | :--- |
| `L1-L145` | Campos de estado, getters, frases offline/head-pats, `_init()` | Inicialización de sonidos (`CapriSfx`) y suscripción a `WebSocketService`. |
| `L146-L347` | `_handleEvent(AssistantEvent)` | Switch central de eventos recibidos del servidor Python (`change_state`, `say`/`speak` + `audio_b64`, `voice_listening`, `voice_transcript`, `voice_status`, `mini`, `posture`, `skin`, `media_state`, `dance`, `open_minigame`, `move_to`, `game_autopilot`, `gamesense`, `lookout_update`, `reminders_update`, `clones`, `hologram`, `brain_status`, `mute`). |
| `L349-L500` | `changeState`, `setSkin`, `setPosture`, `setMiniMode`, `sendMediaCommand`, `openMiniGame`, `requestPerchOnWindow` | Acciones de apariencia, postura, reproductor musical y salto a bordes de ventana (`windowManager.setPosition`). |
| `L501-L642` | `triggerGameAutopilot`, `toggleGameSense`, `toggleBrainPanel`, `saveBrainConfig`, `requestScreenGlance`, `onHeadPatted`, `openChatBox` | Configuración del panel `[BRAIN]` (`configure_brain`), visión de pantalla, caricias y caja de chat. |
| `L644-L758` | `sendUserMessage`, `onAnimationCompleted`, `toggleVoiceListen`, `toggleContinuousVoiceCall`, `toggleTtsVoice` | Envío de mensajes al backend (con fallback local si está desconectado) y controles de micrófono/llamada continua/TTS. |
| `L759-L889` | `showSpeech`, `dismissSpeech`, `toggleMute`, `addLookoutWatch`, `addDatedReminder`, `spawnClones`, `clearClones`, `toggleHologram` | Temporizador dinámico de bocadillo de voz (sincronizado con la duración del audio WAV) y controles de Lookout, Recordatorios, Clones y Holograma (`windowManager.setIgnoreMouseEvents`). |

---

## 2. Mapa de Componentes UI en `frontend/lib/`
- **`lib/main.dart` (`L1-L58`)**: Inicializa `windowManager` sin bordes (`TitleBarStyle.hidden`), fondo `Colors.transparent` y `alwaysOnTop: true`.
- **`lib/presentation/overlay/character_overlay.dart` (`L1-L357`)**: `Stack` raíz que coordina el personaje animado (`SpriteAnimationView`), badges de estado (Clones/Holograma/Conexión), menú de puerta (`DoorContextMenu`), `SpeechBubble`, `CyberpunkMiniPlayer`, `CapriMiniGamesPanel` y `CapriBrainPanel`.
- **`lib/presentation/widgets/capri_brain_panel.dart`**: Modal donde el usuario pega su API Key (Gemini, Groq, NVIDIA, OpenRouter, Claude, OpenAI), elige modelo o activa Ollama, `FollowUps` y `Glances`.
- **`lib/presentation/widgets/speech_bubble.dart`**: Bocadillo estilo videollamada con controles de voz/chat.
- **`lib/presentation/animation/`**: Renderizado del rig con Fragment Shader (`shaders/capri.frag`) y hojas de sprites (`assets/desk/skins/capri/`, `watcher/`, `mini/`).

---

## 3. Verificación Rápida en Flutter
Para validar cambios en Dart sin ejecutar toda la compilación de Windows (ahorrando tiempo y tokens):
```powershell
flutter analyze frontend/lib
```
