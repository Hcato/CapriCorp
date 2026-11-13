import 'dart:async';
import 'dart:ui' as ui;
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// Cargador asíncrono y gestor de caché de imágenes de spritesheets.
class SpriteSheetLoader {
  static final Map<String, ui.Image> _cache = {};
  static final Set<String> _failedAssets = {};

  /// Carga una imagen de spritesheet desde los assets locales de Flutter.
  /// Si el archivo no existe o no se puede decodificar, retorna null sin lanzar excepciones.
  static Future<ui.Image?> load(String assetPath) async {
    if (_cache.containsKey(assetPath)) {
      return _cache[assetPath];
    }

    if (_failedAssets.contains(assetPath)) {
      return null;
    }

    try {
      final ByteData data = await rootBundle.load(assetPath);
      final ui.Codec codec = await ui.instantiateImageCodec(data.buffer.asUint8List());
      final ui.FrameInfo frameInfo = await codec.getNextFrame();
      final ui.Image image = frameInfo.image;

      _cache[assetPath] = image;
      return image;
    } catch (e) {
      if (kDebugMode) {
        print('[SpriteSheetLoader] Asset no disponible ($assetPath): Usando renderizador procedural.');
      }
      _failedAssets.add(assetPath);
      return null;
    }
  }

  /// Limpia la caché si se reemplazan assets en tiempo de ejecución.
  static void clearCache() {
    _cache.clear();
    _failedAssets.clear();
  }
}
