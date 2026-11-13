import 'package:flutter/material.dart';
import 'package:window_manager/window_manager.dart';
import 'core/constants/app_constants.dart';
import 'core/theme/cyberpunk_theme.dart';
import 'domain/state/assistant_controller.dart';
import 'presentation/overlay/character_overlay.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // 1. Inicialización del motor de gestión de ventanas para Windows
  await windowManager.ensureInitialized();

  const windowOptions = WindowOptions(
    size: AppConstants.defaultWindowSize,
    center: true,
    backgroundColor: Colors.transparent,
    skipTaskbar: false,
    titleBarStyle: TitleBarStyle.hidden,
    alwaysOnTop: true,
  );

  // 2. Configurar ventana totalmente transparente, sin marcos y "Always on Top"
  await windowManager.waitUntilReadyToShow(windowOptions, () async {
    await windowManager.setAsFrameless();
    await windowManager.setHasShadow(false);
    await windowManager.setBackgroundColor(Colors.transparent);
    await windowManager.setAlwaysOnTop(true);
    await windowManager.show();
    await windowManager.focus();
  });

  // 3. Inicializar el controlador del asistente (WebSocket + State Machine)
  final assistantController = AssistantController();

  runApp(CapriOverlayApp(controller: assistantController));
}

/// Aplicación raíz de Capri Desktop Companion
class CapriOverlayApp extends StatelessWidget {
  final AssistantController controller;

  const CapriOverlayApp({
    super.key,
    required this.controller,
  });

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: AppConstants.appTitle,
      debugShowCheckedModeBanner: false,
      theme: CyberpunkTheme.darkTheme,
      color: Colors.transparent,
      home: CharacterOverlay(controller: controller),
    );
  }
}
