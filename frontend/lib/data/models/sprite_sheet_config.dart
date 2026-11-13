import '../../domain/entities/assistant_state.dart';

/// Configuración de recorte y reproducción para una hoja de sprites horizontal.
class SpriteSheetConfig {
  /// Ruta del asset dentro del proyecto Flutter (ej. 'assets/sprites/idle.png')
  final String assetPath;

  /// Cantidad total de cuadros concatenados horizontalmente
  final int frameCount;

  /// Cuadros por segundo deseados (24 o 30 FPS típicamente)
  final double fps;

  /// Si la animación debe repetirse continuamente en bucle
  final bool loop;

  /// Estado al que transicionar al finalizar la animación (si [loop] es false)
  final AssistantState? nextStateOnComplete;

  const SpriteSheetConfig({
    required this.assetPath,
    required this.frameCount,
    this.fps = 24.0,
    this.loop = true,
    this.nextStateOnComplete,
  });

  /// Duración de cada cuadro individual
  Duration get frameDuration => Duration(milliseconds: (1000 / fps).round());

  /// Duración total de la secuencia completa
  Duration get totalDuration => Duration(milliseconds: ((1000 / fps) * frameCount).round());
}
