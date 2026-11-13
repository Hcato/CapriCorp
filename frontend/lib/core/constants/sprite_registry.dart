import '../../data/models/sprite_sheet_config.dart';
import '../../domain/entities/assistant_state.dart';

/// Registro central de configuración de animación por estado para Capri Desktop.
/// En la arquitectura original de mochiiwuff/capri-desktop, todos los estados
/// deforman en tiempo real la textura única `assets/capri/capri-full.png` mediante
/// el shader GLSL (`shaders/capri.frag`) y las hojas de exposición (`CapriActs`).
class SpriteRegistry {
  static const String baseSpriteAsset = 'assets/capri/capri-full.png';
  static const String shaderAsset = 'shaders/capri.frag';

  static const Map<AssistantState, SpriteSheetConfig> _defaultConfigs = {
    AssistantState.idle: SpriteSheetConfig(
      assetPath: baseSpriteAsset,
      frameCount: 1,
      fps: 12.0,
      loop: true,
    ),
    AssistantState.listening: SpriteSheetConfig(
      assetPath: baseSpriteAsset,
      frameCount: 1,
      fps: 12.0,
      loop: true,
    ),
    AssistantState.thinking: SpriteSheetConfig(
      assetPath: baseSpriteAsset,
      frameCount: 1,
      fps: 12.0,
      loop: true,
    ),
    AssistantState.speaking: SpriteSheetConfig(
      assetPath: baseSpriteAsset,
      frameCount: 1,
      fps: 12.0,
      loop: true,
    ),
    AssistantState.teleporting: SpriteSheetConfig(
      assetPath: baseSpriteAsset,
      frameCount: 1,
      fps: 24.0,
      loop: false,
      nextStateOnComplete: AssistantState.idle,
    ),
    AssistantState.sleeping: SpriteSheetConfig(
      assetPath: baseSpriteAsset,
      frameCount: 1,
      fps: 6.0,
      loop: true,
    ),
    AssistantState.sitting: SpriteSheetConfig(
      assetPath: baseSpriteAsset,
      frameCount: 1,
      fps: 12.0,
      loop: true,
    ),
    AssistantState.victory: SpriteSheetConfig(
      assetPath: baseSpriteAsset,
      frameCount: 1,
      fps: 12.0,
      loop: false,
      nextStateOnComplete: AssistantState.idle,
    ),
    AssistantState.peek: SpriteSheetConfig(
      assetPath: baseSpriteAsset,
      frameCount: 1,
      fps: 12.0,
      loop: true,
    ),
    AssistantState.point: SpriteSheetConfig(
      assetPath: baseSpriteAsset,
      frameCount: 1,
      fps: 12.0,
      loop: true,
    ),
    AssistantState.intro: SpriteSheetConfig(
      assetPath: baseSpriteAsset,
      frameCount: 1,
      fps: 24.0,
      loop: false,
      nextStateOnComplete: AssistantState.idle,
    ),
  };

  /// Obtiene el retrato de expresión facial (`assets/capri/face-*.png`) para el bocadillo de diálogo.
  static String getFacePortraitAsset(AssistantState state) {
    switch (state) {
      case AssistantState.idle:
        return 'assets/capri/face-calm.png';
      case AssistantState.listening:
        return 'assets/capri/face-look.png';
      case AssistantState.thinking:
        return 'assets/capri/face-aside.png';
      case AssistantState.speaking:
        return 'assets/capri/face-smug.png';
      case AssistantState.victory:
        return 'assets/capri/face-laugh.png';
      case AssistantState.teleporting:
      case AssistantState.intro:
        return 'assets/capri/face-many.png';
      case AssistantState.sleeping:
      case AssistantState.sitting:
      case AssistantState.peek:
      case AssistantState.point:
        return 'assets/capri/capri-face.png';
    }
  }

  /// Obtiene la configuración para el estado dado.
  static SpriteSheetConfig getConfig(AssistantState state) {
    return _defaultConfigs[state] ?? _defaultConfigs[AssistantState.idle]!;
  }
}
