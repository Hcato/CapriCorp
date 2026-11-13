import 'package:flutter/material.dart';

/// Constantes generales de la aplicación Capri Desktop Companion.
class AppConstants {
  static const String appTitle = 'Capri Desktop Overlay';
  static const String defaultWsUrl = 'ws://127.0.0.1:8765';

  // Dimensiones de ventana y lienzo del shader (VIEW = 352x532 a escala 0.6 -> 211x319)
  static const Size defaultWindowSize = Size(380, 420);
  static const Size spriteDisplaySize = Size(211, 319);

  // Intervalo de reintento de conexión WebSocket
  static const Duration wsReconnectDelay = Duration(seconds: 3);

  // Cyberpunk Palette
  static const Color neonCyan = Color(0xFF00F0FF);
  static const Color neonPink = Color(0xFFFF007F);
  static const Color neonPurple = Color(0xFF9D00FF);
  static const Color darkGlass = Color(0xCC0D0E15);
  static const Color glowCyan = Color(0x6600F0FF);
}
