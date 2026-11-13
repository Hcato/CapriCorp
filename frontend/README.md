# Capri Desktop Companion (Frontend Flutter)

Overlay de escritorio interactivo y transparente para Windows 11, diseñado como compañero de IA desacoplado siguiendo el **Patrón de Enrutador**.

---

## 🏛️ Arquitectura del Frontend (`lib/`)

El proyecto sigue los principios de **Clean Architecture**, dividiendo la lógica en capas desacopladas y testeables:

```
frontend/
├── assets/
│   └── sprites/                      # Coloca aquí los spritesheets (.png / .webp)
│       ├── idle.png
│       ├── teleport.png
│       ├── faces.png
│       ├── sit.png
│       └── sleep.png
│
├── lib/
│   ├── core/
│   │   ├── constants/
│   │   │   ├── app_constants.dart    # Tamaños de ventana, endpoint WS, paleta Cyberpunk
│   │   │   └── sprite_registry.dart  # Mapeo de estados a spritesheets, conteo de frames y FPS
│   │   ├── theme/
│   │   │   └── cyberpunk_theme.dart  # Tema visual oscuro y vidrio (glassmorphism)
│   │   └── utils/
│   │       └── sprite_sheet_loader.dart # Carga y caché en memoria de texturas ui.Image
│   │
│   ├── data/
│   │   ├── models/
│   │   │   ├── assistant_event.dart     # Serialización y parsing de eventos JSON
│   │   │   └── sprite_sheet_config.dart # Configuración de recorte (frames, fps, bucle)
│   │   └── services/
│   │       └── websocket_service.dart   # Cliente WebSocket con reconexión automática
│   │
│   ├── domain/
│   │   ├── entities/
│   │   │   └── assistant_state.dart     # Enum: idle, listening, thinking, teleporting, speaking...
│   │   └── state/
│   │       └── assistant_controller.dart# Máquina de Estados reactiva (ChangeNotifier)
│   │
│   ├── presentation/
│   │   ├── animation/
│   │   │   ├── sprite_sheet_painter.dart# CustomPainter con recorte horizontal y fallback procedural
│   │   │   └── sprite_animation_view.dart# Bucle de animación a 24/30 FPS usando Ticker
│   │   ├── overlay/
│   │   │   ├── character_overlay.dart   # Overlay principal, arrastre nativo Win32 y gestos
│   │   │   └── overlay_context_menu.dart# Menú contextual con clic derecho (Opciones, Silenciar, Cerrar)
│   │   └── widgets/
│   │       ├── connection_badge.dart    # Badge discreto con estado del enlace WebSocket
│   │       └── speech_bubble.dart       # Bocadillo de diálogo flotante estilo Cyberpunk
│   │
│   └── main.dart                     # Bootstrap y orquestación de ventana transparente (window_manager)
```

---

## ⚙️ Características Implementadas

1. **Ventana Overlay Totalmente Transparente (Windows 11):**
   - Configurada con `window_manager`.
   - Sin marcos (`setAsFrameless()`), sin barra de título (`TitleBarStyle.hidden`), fondo transparente (`setBackgroundColor(Colors.transparent)`) y siempre encima de todas las ventanas (`alwaysOnTop: true`).

2. **Interactividad Nativa:**
   - **Arrastre fluido por pantalla:** Al presionar y arrastrar sobre el personaje (`onPanStart`), delega en `windowManager.startDragging()`, ejecutando el arrastre a través de la API nativa de Windows con aceleración por hardware.
   - **Menú Contextual (Clic Derecho):** Incluye opciones para silenciar, probar estados manualmente, ver opciones del sistema y cerrar la aplicación.
   - **Doble Toque:** Dispara una animación especial (ej. teletransporte).

3. **Motor de Renderizado de Sprites (State Machine):**
   - **Recorte horizontal de spritesheets:** Lee una imagen de ancho $W$ y la divide exactamente en $N$ frames horizontales de ancho $W / N$ proyectándolos mediante `canvas.drawImageRect`.
   - **Control de FPS:** Animado a 24 o 30 FPS mediante un `Ticker` de Flutter de bajo consumo.
   - **Avatar Procedural de Respaldo:** Si aún no has colocado los archivos `.png` en `assets/sprites/`, el motor renderiza automáticamente un avatar holográfico Cyberpunk interactivo con ojos reactivos, ondas de sonido y partículas, permitiendo ejecutar y probar la aplicación de inmediato sin errores de carga.

4. **Sistema Nervioso (WebSocket Bidireccional):**
   - Se conecta por defecto a `ws://127.0.0.1:8765`.
   - Procesa eventos JSON entrantes:
     ```json
     {"event": "change_state", "state": "Thinking"}
     {"event": "say", "state": "Speaking", "text": "Procesando respuesta en Ollama..."}
     {"event": "mute", "muted": true}
     ```
   - **Reconexión Automática:** Si el backend de Python se apaga o reinicia, el frontend reintenta la conexión periódicamente sin congelarse.

---

## 🚀 Cómo Ejecutar la Aplicación

### Paso 1: Iniciar el Frontend en Modo Windows
Desde la terminal en la carpeta `frontend/`:

```powershell
flutter run -d windows
```

### Paso 2: Probar la Conexión con el Servidor de Prueba
En otra terminal en la raíz del proyecto (`Capri/`), ejecuta el servidor simulador:

```powershell
pip install websockets
python backend_test_server.py
```

Podrás seleccionar opciones numéricas (1 a 6) para ver al personaje cambiar de estado y hablar en tiempo real.
