// Sprite-strip, 60-FPS music perch/laydown, head-pat particles, and Mini Chibi animation engine
// ported from Capri-cmd/capri-ai and lachydotmcg/capri-desktop.
// Art by xilia_world00 (Discord).

import 'dart:math' as math;
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import '../../core/utils/sprite_sheet_loader.dart';
import '../../domain/entities/assistant_state.dart';

/// Skins / motores visuales disponibles en el menú "Skins".
enum CapriVisualSkin {
  shaderRig('Capri (Shader GLSL)', 'shader'),
  capriSprites('Capri (Sprites 60 FPS)', 'capri'),
  watcherSprites('Watcher (Skin Secreta)', 'watcher');

  final String label;
  final String id;
  const CapriVisualSkin(this.label, this.id);

  static CapriVisualSkin fromId(String? id) {
    final clean = (id ?? '').trim().toLowerCase();
    for (final s in CapriVisualSkin.values) {
      if (s.id == clean || s.name.toLowerCase() == clean) return s;
    }
    return CapriVisualSkin.shaderRig;
  }
}

/// Postura en escritorio (De pie, Sentada en borde de ventana o Acostada).
enum CapriPosture {
  standing('De pie'),
  perched('Sentada en ventana'),
  lying('Acostada');

  final String label;
  const CapriPosture(this.label);
}

class _ClipSpec {
  final int frames;
  final double fps;
  final double heightRatio;
  const _ClipSpec(this.frames, this.fps, this.heightRatio);
}

/// Gestiona la carga y pintado de las tiras de sprites (`assets/desk/skins/<skin>/`),
/// los clips de 60 FPS (`perch_music`, `perch_talk`, `laydown*`, `dance`, `walk`),
/// las notas musicales flotantes (`Note` de `Capri.cs`), los Head Pats y el modo Mini Chibi (`assets/desk/mini/`).
class CapriDeskSprites {
  static const Map<String, _ClipSpec> _clipSpecs = {
    'idle': _ClipSpec(16, 8.0, 1.11),
    'blink': _ClipSpec(4, 8.0, 1.11),
    'blink_glitch': _ClipSpec(4, 8.0, 1.11),
    'grin': _ClipSpec(16, 8.0, 1.11),
    'glitch': _ClipSpec(10, 15.0, 1.11),
    'dangle': _ClipSpec(24, 10.0, 1.11),
    'sleep': _ClipSpec(16, 6.0, 1.11),
    'wake': _ClipSpec(13, 15.0, 1.11),
    'mouth': _ClipSpec(5, 12.0, 1.11),
    'dance': _ClipSpec(16, 10.0, 1.11),
    'walk': _ClipSpec(12, 12.0, 1.11),
    'arrive': _ClipSpec(14, 15.0, 1.11),
    'leave': _ClipSpec(12, 15.0, 1.11),
    'perch': _ClipSpec(16, 8.0, 1.0),
    'perch_blink': _ClipSpec(4, 8.0, 1.0),
    'perch_blink_glitch': _ClipSpec(4, 8.0, 1.0),
    'perch_glitch': _ClipSpec(10, 15.0, 1.0),
    // Clips de 60 frames a 30 FPS de lachydotmcg/capri-desktop:
    'perch_music': _ClipSpec(60, 30.0, 1.0),
    'perch_talk': _ClipSpec(60, 30.0, 1.0),
    'laydown': _ClipSpec(60, 30.0, 0.85),
    'laydown_talk': _ClipSpec(60, 30.0, 0.85),
    'laydown_sleep': _ClipSpec(60, 30.0, 0.85),
    'laydown_blink': _ClipSpec(8, 30.0, 0.85),
    'laydown_glitch': _ClipSpec(10, 15.0, 0.85),
  };

  static const List<String> layNames = ['lay_awake', 'lay', 'lay_talk', 'lay_talk2'];

  static const List<String> miniNames = [
    'idle',
    'blink',
    'talk',
    'talk2',
    'look_left',
    'look_right',
    'annoyed',
    'annoyed_talk',
    'glitch',
    'watcher',
  ];

  static const Map<String, List<String>> _miniFallbacks = {
    'idle': [],
    'blink': ['sleep', 'idle'],
    'talk': ['idle'],
    'sleep': ['blink', 'idle'],
    'sleep_talk': ['talk', 'sleep'],
    'annoyed': ['idle'],
    'annoyed_talk': ['talk', 'annoyed'],
    'annoyed_blink': ['blink', 'annoyed'],
    'look_left': ['idle'],
    'look_right': ['idle'],
    'lay': ['sleep', 'idle'],
    'lay_awake': ['lay', 'idle'],
    'lay_talk': ['talk'],
    'talk2': ['talk'],
    'lay_talk2': ['lay_talk'],
    'glitch': ['idle'],
  };

  final math.Random _rng = math.Random();

  // Mapas de texturas cargadas: skinFolder -> clipName -> ui.Image
  final Map<String, Map<String, ui.Image>> _skinClips = {
    'capri': {},
    'watcher': {},
  };
  final Map<String, Map<String, ui.Image>> _skinLays = {
    'capri': {},
    'watcher': {},
  };
  final Map<String, ui.Image> _miniImages = {};

  bool isLoaded = false;

  // Estado interno de parpadeo / glitch espontáneo
  double _nextBlinkAtSec = 2.8;
  double _blinkUntilSec = 0.0;
  String _activeBlinkClip = 'blink';

  // Estado del Modo Mini (`mini.py` `Chip`)
  int miniLookDir = 0; // -1 = izquierda, 0 = centro, 1 = derecha
  double _miniNextLookAtSec = 1.5;
  double miniAnnoyedUntilSec = 0.0;
  final List<double> _pokeTimesSec = [];

  // Estado de Head Pats (`Capri.cs` `petTurns`)
  double petGlowUntilSec = 0.0;
  final List<int> _petDirectionTurns = [];
  double _lastPetX = 0.0;
  int _lastPetDir = 0;

  Future<void> loadAll() async {
    if (isLoaded) return;

    for (final skin in const ['capri', 'watcher']) {
      for (final clipName in _clipSpecs.keys) {
        final img = await SpriteSheetLoader.load('assets/desk/skins/$skin/$clipName.png');
        if (img != null) {
          _skinClips[skin]![clipName] = img;
        }
      }
      for (final layName in layNames) {
        final img = await SpriteSheetLoader.load('assets/desk/skins/$skin/$layName.png');
        if (img != null) {
          _skinLays[skin]![layName] = img;
        }
      }
    }

    for (final name in miniNames) {
      final img = await SpriteSheetLoader.load('assets/desk/mini/$name.png');
      if (img != null) {
        _miniImages[name] = img;
      }
    }

    isLoaded = true;
  }

  /// Registra el movimiento horizontal del cursor sobre la cabeza de Capri (`Capri.cs` `petTurns`).
  /// Si el usuario frota el cursor de lado a lado 4 veces en menos de 1.8s, dispara un Head Pat.
  bool registerCursorRub(double localX, double localY, double canvasHeight, double nowSec) {
    // Solo en la mitad superior (cabeza/pelo de Capri)
    if (localY > canvasHeight * 0.52) return false;
    final dx = localX - _lastPetX;
    if (dx.abs() < 8.0) return false;
    _lastPetX = localX;

    final dir = dx > 0 ? 1 : -1;
    if (dir != _lastPetDir) {
      _lastPetDir = dir;
      final nowMs = (nowSec * 1000).round();
      _petDirectionTurns.removeWhere((t) => nowMs - t > 1800);
      _petDirectionTurns.add(nowMs);
      if (_petDirectionTurns.length >= 5 && nowSec > petGlowUntilSec) {
        _petDirectionTurns.clear();
        petGlowUntilSec = nowSec + 3.8;
        return true;
      }
    }
    return false;
  }

  /// Registra un clic sobre Capri en modo Mini; si recibe 3 toques rápidos se enfada (`mini.py` `pokes`).
  bool registerMiniPoke(double nowSec) {
    _pokeTimesSec.removeWhere((t) => nowSec - t > 2.2);
    _pokeTimesSec.add(nowSec);
    if (_pokeTimesSec.length >= 3) {
      _pokeTimesSec.clear();
      miniAnnoyedUntilSec = nowSec + 4.5;
      return true;
    }
    return false;
  }

  /// Determina qué clip de `_clipSpecs` usar según el estado, postura, música/baile y arrastre.
  String selectClipName({
    String skinFolder = 'capri',
    required AssistantState state,
    required CapriPosture posture,
    required bool isDragging,
    bool isDancing = false,
    required double nowSec,
  }) {
    final clips = _skinClips[skinFolder] ?? _skinClips['capri']!;

    if (isDragging) {
      return 'dangle';
    }

    final isSeated = posture == CapriPosture.perched || state == AssistantState.sitting;

    // Si acaba de recibir Head Pats, sonríe (`grin`)
    if (nowSec < petGlowUntilSec && !isSeated) {
      return 'grin';
    }

    switch (state) {
      case AssistantState.sleeping:
        return 'sleep';
      case AssistantState.speaking:
        if (isSeated) {
          return clips.containsKey('perch_talk') ? 'perch_talk' : 'perch';
        }
        return 'mouth';
      case AssistantState.thinking:
      case AssistantState.teleporting:
        return isSeated ? 'perch_glitch' : 'glitch';
      case AssistantState.victory:
      case AssistantState.point:
        return 'grin';
      case AssistantState.intro:
        return 'wake';
      case AssistantState.listening:
      case AssistantState.peek:
      case AssistantState.sitting:
      case AssistantState.idle:
        break;
    }

    // Si está sonando música o bailando (`Capri.cs` `perchDance` / `dance`)
    if (isDancing) {
      if (isSeated && clips.containsKey('perch_music')) {
        return 'perch_music';
      }
      if (!isSeated && clips.containsKey('dance')) {
        return 'dance';
      }
    }

    // Parpadeo y micro-glitch periódico en reposo
    if (nowSec >= _nextBlinkAtSec) {
      final doGlitch = _rng.nextDouble() < 0.25;
      _activeBlinkClip = isSeated
          ? (doGlitch ? 'perch_blink_glitch' : 'perch_blink')
          : (doGlitch ? 'blink_glitch' : 'blink');
      _blinkUntilSec = nowSec + 0.5;
      _nextBlinkAtSec = nowSec + 2.4 + _rng.nextDouble() * 3.4;
    }

    if (nowSec < _blinkUntilSec) {
      return _activeBlinkClip;
    }

    return isSeated ? 'perch' : 'idle';
  }

  /// Pinta la tira de sprites horizontal o la pose acostada (`laydown` 60 FPS o `LayArt`) para la skin seleccionada.
  bool paintSkinSprite({
    required Canvas canvas,
    required Size size,
    required String skinFolder,
    required AssistantState state,
    required CapriPosture posture,
    required bool isDragging,
    required bool isDancing,
    required double nowSec,
  }) {
    final clips = _skinClips[skinFolder] ?? _skinClips['capri']!;
    final lays = _skinLays[skinFolder] ?? _skinLays['capri']!;

    // 1. Si está en postura acostada (y no arrastrándose):
    //    Usar primero las tiras de 60 FPS `laydown*` de `lachydotmcg/capri-desktop` si están disponibles;
    //    si no (como en la skin `watcher`), usar las imágenes `lay_awake` / `lay` / `lay_talk`.
    if (!isDragging && posture == CapriPosture.lying) {
      if (clips.containsKey('laydown')) {
        String layClip = 'laydown';
        if (state == AssistantState.sleeping && clips.containsKey('laydown_sleep')) {
          layClip = 'laydown_sleep';
        } else if (state == AssistantState.speaking && clips.containsKey('laydown_talk')) {
          layClip = 'laydown_talk';
        } else if ((state == AssistantState.thinking || state == AssistantState.teleporting) &&
            clips.containsKey('laydown_glitch')) {
          layClip = 'laydown_glitch';
        } else if (nowSec < _blinkUntilSec && clips.containsKey('laydown_blink')) {
          layClip = 'laydown_blink';
        } else if (nowSec >= _nextBlinkAtSec) {
          _blinkUntilSec = nowSec + 0.28;
          _nextBlinkAtSec = nowSec + 2.8 + _rng.nextDouble() * 3.5;
          if (clips.containsKey('laydown_blink')) layClip = 'laydown_blink';
        }

        final spec = _clipSpecs[layClip] ?? _clipSpecs['laydown']!;
        final strip = clips[layClip] ?? clips['laydown']!;
        final frameCount = spec.frames;
        final frameIndex = ((nowSec * spec.fps).floor()) % frameCount;
        final fw = strip.width / frameCount;
        final fh = strip.height.toDouble();
        final srcRect = Rect.fromLTWH(frameIndex * fw, 0, fw, fh);

        final drawW = size.width * 0.92;
        final drawH = drawW * (fh / fw);
        final dstRect = Rect.fromCenter(
          center: Offset(size.width * 0.5, size.height * 0.62),
          width: drawW,
          height: drawH,
        );
        canvas.drawImageRect(
          strip,
          srcRect,
          dstRect,
          Paint()..filterQuality = FilterQuality.medium,
        );
        if (state == AssistantState.sleeping) {
          _paintSleepingZs(canvas, size.width * 0.62, size.height * 0.42, 1.2, nowSec);
        }
        if (nowSec < petGlowUntilSec) {
          _paintHeadPatHearts(canvas, size.width * 0.5, size.height * 0.35, nowSec);
        }
        return true;
      } else if (lays.isNotEmpty) {
        String layKey = 'lay_awake';
        if (state == AssistantState.sleeping) {
          layKey = 'lay';
        } else if (state == AssistantState.speaking) {
          final flap = ((nowSec * 9.0).floor()) % 3;
          layKey = flap == 0 ? 'lay_talk' : (flap == 1 ? 'lay_talk2' : 'lay_awake');
        } else if (nowSec < _blinkUntilSec) {
          layKey = 'lay';
        } else if (nowSec >= _nextBlinkAtSec) {
          _blinkUntilSec = nowSec + 0.35;
          _nextBlinkAtSec = nowSec + 2.8 + _rng.nextDouble() * 3.5;
          layKey = 'lay';
        }

        final img = lays[layKey] ?? lays['lay_awake'] ?? lays.values.first;
        _paintCenteredImage(canvas, size, img, scaleBoost: 1.05);
        return true;
      }
    }

    // 2. Seleccionar tira horizontal (`_clipSpecs`)
    final clipName = selectClipName(
      skinFolder: skinFolder,
      state: state,
      posture: posture,
      isDragging: isDragging,
      isDancing: isDancing,
      nowSec: nowSec,
    );
    final spec = _clipSpecs[clipName] ?? _clipSpecs['idle']!;
    final strip = clips[clipName] ?? clips['idle'];
    if (strip == null) return false;

    final frameCount = spec.frames;
    final frameIndex = ((nowSec * spec.fps).floor()) % frameCount;
    final fw = strip.width / frameCount;
    final fh = strip.height.toDouble();

    final srcRect = Rect.fromLTWH(frameIndex * fw, 0, fw, fh);

    // Cabeceo rítmico (`nodGain` de `Capri.cs`) cuando suena música
    final beatNod = (isDancing && !isDragging && state != AssistantState.sleeping)
        ? math.sin(nowSec * 6.8).abs() * 3.5
        : 0.0;

    final drawH = size.height * 0.90;
    final drawW = drawH * (fw / fh);
    final dstRect = Rect.fromCenter(
      center: Offset(size.width * 0.5, size.height * 0.52 + beatNod),
      width: drawW,
      height: drawH,
    );

    canvas.drawImageRect(
      strip,
      srcRect,
      dstRect,
      Paint()..filterQuality = FilterQuality.medium,
    );

    // 3. Efectos de partículas adicionales (`Note` de música o corazones de Head Pats)
    if (isDancing && !isDragging && state != AssistantState.sleeping) {
      paintMusicNotes(canvas, size, nowSec);
    }
    if (nowSec < petGlowUntilSec) {
      _paintHeadPatHearts(canvas, size.width * 0.5, size.height * 0.18, nowSec);
    }
    return true;
  }

  /// Pinta corcheas musicales neón flotando a los lados de Capri (`Note` en `Capri.cs`).
  void paintMusicNotes(Canvas canvas, Size size, double nowSec) {
    const glyphs = ['♪', '♫', '♬'];
    const colors = [Color(0xFFFF1E6E), Color(0xFF78FAFF), Color(0xFF34F5A0)];
    for (int i = 0; i < 3; i++) {
      final phase = ((nowSec * 0.65) + i * 0.33) % 1.0;
      final double alpha = (math.sin(math.pi * phase) * 0.92).clamp(0.0, 1.0).toDouble();
      final side = i.isEven ? -1.0 : 1.0;
      final x = size.width * 0.5 + side * (size.width * 0.24 + phase * 18.0) + math.sin(phase * 6.0 + i) * 5.0;
      final y = size.height * 0.44 - phase * 48.0;

      final tp = TextPainter(
        text: TextSpan(
          text: glyphs[i % glyphs.length],
          style: TextStyle(
            fontSize: 14.0 + phase * 5.0,
            fontWeight: FontWeight.bold,
            color: colors[i % colors.length].withValues(alpha: alpha),
            shadows: [
              Shadow(
                color: colors[i % colors.length].withValues(alpha: alpha * 0.6),
                blurRadius: 6,
              ),
            ],
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(x, y));
    }
  }

  /// Pinta corazones/chispas neón cuando el usuario acaricia a Capri (`Head Pats` en `Capri.cs`).
  void _paintHeadPatHearts(Canvas canvas, double cx, double topY, double nowSec) {
    const colors = [Color(0xFFFF2E70), Color(0xFF78FAFF), Color(0xFF34F5A0)];
    for (int i = 0; i < 3; i++) {
      final phase = ((nowSec * 0.9) + i * 0.33) % 1.0;
      final double alpha = (math.sin(math.pi * phase) * 0.95).clamp(0.0, 1.0).toDouble();
      final dx = cx + (i - 1) * 24.0 + math.sin(phase * 5.0 + i) * 6.0;
      final dy = topY - phase * 26.0;

      final tp = TextPainter(
        text: TextSpan(
          text: i == 1 ? '♥' : '✦',
          style: TextStyle(
            fontSize: 13.0 + phase * 4.0,
            fontWeight: FontWeight.bold,
            color: colors[i].withValues(alpha: alpha),
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(dx, dy));
    }
  }

  /// Pinta la versión Mini Chibi (`assets/desk/mini/` y `capri/desk/mini.py` `_paint_art`).
  bool paintMiniForm({
    required Canvas canvas,
    required Size size,
    required AssistantState state,
    required CapriVisualSkin skin,
    required CapriPosture posture,
    required bool isDancing,
    required double nowSec,
  }) {
    if (_miniImages.isEmpty) return false;

    ui.Image? art;
    if (skin == CapriVisualSkin.watcherSprites && _miniImages.containsKey('watcher')) {
      art = _miniImages['watcher'];
    } else {
      final stateKey = _pickMiniStateKey(state, posture, nowSec);
      art = _resolveMiniImage(stateKey);
    }
    if (art == null) return false;

    final side = math.min(size.width, size.height) * 0.58;
    final u = side / 100.0;
    final isLay = posture == CapriPosture.lying;
    final isSleeping = state == AssistantState.sleeping;
    final isGlitch = state == AssistantState.thinking || state == AssistantState.teleporting;

    final danceBob = isDancing ? math.sin(nowSec * 7.0).abs() * 4.5 * u : 0.0;
    final bob = isLay ? 0.0 : math.sin(nowSec * 1.9) * 2.5 * u - danceBob;
    final breathe = math.sin(nowSec * (isLay ? 1.2 : 1.9) + 0.6);
    final cx = size.width * 0.5;
    final floorY = size.height * 0.66;
    final baseSize = (isLay ? 112.0 : 98.0) * u;
    final aspect = art.height / math.max(1, art.width);
    final w = baseSize * (1.0 - 0.025 * breathe);
    final h = baseSize * aspect * (1.0 + 0.03 * breathe);
    final x = cx - w * 0.5 + (isGlitch ? _rng.nextInt(5) - 2 : 0) * u;
    final y = floorY - h + (isSleeping ? 3.0 * u : bob);

    // Sombra suave bajo el chibi
    final shadowW = (isLay ? 64.0 : 48.0) * u;
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(cx, floorY + 2.0 * u),
        width: shadowW,
        height: 7.0 * u,
      ),
      Paint()..color = const Color(0x6E000000),
    );

    final srcRect = Rect.fromLTWH(0, 0, art.width.toDouble(), art.height.toDouble());
    final dstRect = Rect.fromLTWH(x, y, w, h);

    // Aberración cromática cuando glitchea
    if (isGlitch) {
      canvas.drawImageRect(
        art,
        srcRect,
        dstRect.shift(Offset(-3.0 * u, 0)),
        Paint()
          ..colorFilter = const ColorFilter.mode(Color(0x66FF1E6E), BlendMode.modulate)
          ..filterQuality = FilterQuality.medium,
      );
      canvas.drawImageRect(
        art,
        srcRect,
        dstRect.shift(Offset(3.0 * u, 0)),
        Paint()
          ..colorFilter = const ColorFilter.mode(Color(0x6678FAFF), BlendMode.modulate)
          ..filterQuality = FilterQuality.medium,
      );
    }

    canvas.drawImageRect(
      art,
      srcRect,
      dstRect,
      Paint()..filterQuality = FilterQuality.medium,
    );

    if (isSleeping) {
      _paintSleepingZs(canvas, cx + 22.0 * u, y + 6.0 * u, u, nowSec);
    }
    if (isDancing && !isSleeping) {
      paintMusicNotes(canvas, size, nowSec);
    }
    if (nowSec < petGlowUntilSec) {
      _paintHeadPatHearts(canvas, cx, y - 8.0 * u, nowSec);
    }
    return true;
  }

  String _pickMiniStateKey(AssistantState state, CapriPosture posture, double nowSec) {
    final annoyed = nowSec < miniAnnoyedUntilSec;
    final talking = state == AssistantState.speaking;
    final flap = ((nowSec * 9.0).floor()) % 3;

    if (state == AssistantState.thinking || state == AssistantState.teleporting) {
      return 'glitch';
    }

    if (posture == CapriPosture.lying) {
      if (talking) {
        return flap == 0 ? 'lay_talk' : (flap == 1 ? 'lay_talk2' : 'lay_awake');
      }
      return state == AssistantState.sleeping ? 'lay' : 'lay_awake';
    }

    if (state == AssistantState.sleeping) {
      return talking && flap == 0 ? 'sleep_talk' : 'sleep';
    }

    if (talking) {
      if (annoyed) return flap < 2 ? 'annoyed_talk' : 'annoyed';
      return flap == 0 ? 'talk' : (flap == 1 ? 'talk2' : 'idle');
    }

    if (nowSec >= _nextBlinkAtSec) {
      _blinkUntilSec = nowSec + 0.16;
      _nextBlinkAtSec = nowSec + 2.2 + _rng.nextDouble() * 3.0;
    }
    if (nowSec < _blinkUntilSec) {
      return annoyed ? 'annoyed_blink' : 'blink';
    }

    if (annoyed) return 'annoyed';

    if (nowSec >= _miniNextLookAtSec) {
      final pick = _rng.nextDouble();
      miniLookDir = pick < 0.22 ? -1 : (pick < 0.44 ? 1 : 0);
      _miniNextLookAtSec = nowSec + 1.8 + _rng.nextDouble() * 2.8;
    }
    if (miniLookDir < 0) return 'look_left';
    if (miniLookDir > 0) return 'look_right';
    return 'idle';
  }

  ui.Image? _resolveMiniImage(String stateKey) {
    final seen = <String>{};
    final queue = <String>[stateKey];
    while (queue.isNotEmpty) {
      final cur = queue.removeAt(0);
      if (!seen.add(cur)) continue;
      if (_miniImages.containsKey(cur)) {
        return _miniImages[cur];
      }
      queue.addAll(_miniFallbacks[cur] ?? const []);
      queue.add('idle');
    }
    return _miniImages['idle'];
  }

  void _paintSleepingZs(Canvas canvas, double x, double y, double u, double nowSec) {
    for (int i = 0; i < 3; i++) {
      final k = ((nowSec * 0.45) + i / 3.0) % 1.0;
      final fontSize = math.max(8.0, (8.0 + 7.0 * k) * u);
      final double alpha = (math.sin(math.pi * k) * 0.9).clamp(0.0, 1.0).toDouble();
      final tp = TextPainter(
        text: TextSpan(
          text: 'z',
          style: TextStyle(
            fontFamily: 'ShareTechMono',
            fontSize: fontSize,
            fontWeight: FontWeight.bold,
            color: const Color(0xFF78FAFF).withValues(alpha: alpha),
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      final dx = x + 10.0 * k * u + math.sin(k * 6.0) * 2.0 * u;
      final dy = y - 26.0 * k * u;
      tp.paint(canvas, Offset(dx, dy));
    }
  }

  void _paintCenteredImage(Canvas canvas, Size size, ui.Image img, {double scaleBoost = 1.0}) {
    final iw = img.width.toDouble();
    final ih = img.height.toDouble();
    final scale = math.min(size.width / iw, size.height / ih) * 0.92 * scaleBoost;
    final dw = iw * scale;
    final dh = ih * scale;
    final dst = Rect.fromCenter(
      center: Offset(size.width * 0.5, size.height * 0.62),
      width: dw,
      height: dh,
    );
    canvas.drawImageRect(
      img,
      Rect.fromLTWH(0, 0, iw, ih),
      dst,
      Paint()..filterQuality = FilterQuality.medium,
    );
  }
}
