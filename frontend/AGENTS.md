# Reglas del Directorio Frontend (`frontend/`)

## 1. Índice Rápido de Archivos Clave en Flutter
- **`lib/main.dart` (58 líneas)**: Configuración de `window_manager` (ventana transparente, frameless, `alwaysOnTop: true`).
- **`lib/domain/state/assistant_controller.dart` (889 líneas)**: `ChangeNotifier` central que gestiona WebSocket, estados (`AssistantState`), skins (`shader`, `capri`, `watcher`), posturas, reproductor musical, minijuegos, panel `BRAIN`, micrófono/voz, `lookout`, recordatorios y clones.
- **`lib/presentation/overlay/character_overlay.dart` (357 líneas)**: `Stack` principal del overlay transparente, atajos de teclado (`Esc` para limpiar clones), burbuja de voz y paneles flotantes.
- **`lib/presentation/widgets/capri_brain_panel.dart`**: Panel de configuración de API Keys, selección de proveedor/modelo y estado del Cerebro IA.
- **`lib/data/services/websocket_service.dart` y `lib/data/models/assistant_event.dart`**: Cliente WebSocket (`ws://127.0.0.1:8765`) y parseo de eventos JSON.

## 2. Reglas de UI y Rendimiento
- **Transparencia del Overlay**: Nunca uses colores opacos en el `Scaffold` raíz ni rompas `Colors.transparent` de `window_manager`.
- **Lectura quirúrgica**: En `assistant_controller.dart`, lee bloques de 100-150 líneas usando `StartLine`/`EndLine` en lugar del archivo entero.
- **Estética Cyberpunk**: Mantén la tipografía `ShareTechMono` y la paleta neón (`#FF1E6E` magenta, `#78FAFF` cian, `#110E18` fondo oscuro translúcido).
