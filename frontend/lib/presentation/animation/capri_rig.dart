// Capri rig state, cue dispatcher & animation loop ported from mochiiwuff/capri-desktop
// (src/renderer/js/capri.js).
// Required Notice: Copyright (c) 2026 mochiiwuff (https://github.com/mochiiwuff/capri-desktop)
// Non-commercial use only, see THIRD_PARTY_NOTICES.md.

import 'dart:math' as math;
import 'dart:ui' as ui;
import '../../domain/entities/assistant_state.dart';
import 'capri_acts.dart';
import 'capri_fx.dart';

class CapriUniforms {
  double seed = 0.0;
  double boil = 0.9;
  double hair = 0.0;
  double head = 0.0;
  double mane = 0.0;
  double armL = 0.0;
  double armR = 0.0;
  double longL = 1.0;
  double longR = 1.0;
  double sit = 0.0;
  double bend = 0.0;
  double kickL = 0.0;
  double kickR = 0.0;
  double smearX = 0.0;
  double smearY = 0.0;
  double echoX = 0.0;
  double echoY = 0.0;
  double glitch = 0.0;
  double glitchSeed = 0.0;
  double split = 0.0;
  double collapse = 0.0;
  double dissolve = 0.0;
  double sparkle = 1.0;
  double grade = 1.0;
  double silR = 0.08;
  double silG = 0.06;
  double silB = 0.11;
  double silAmount = 0.0;
  double misregX = -2.6;
  double misregY = 2.2;
  double rimR = 0.48;
  double rimG = 0.24;
  double rimB = 1.0;
  double alpha = 1.0;

  // Canvas-level transform around feet/seat pivot
  double bob = 0.0;
  double tilt = 0.0;
  double sx = 1.0;
  double sy = 1.0;
  int facing = 1;
}

class CapriRig {
  static const double kOnTwosMs = 1000.0 / 12.0;
  static const double kOnOnesMs = 1000.0 / 24.0;
  static const double kAsleepMs = 1000.0 / 6.0;
  static const double kDozeAfterMs = 3500.0;

  final math.Random _rng = math.Random();
  final CapriUniforms u = CapriUniforms();
  final CapriFxLayer fx = CapriFxLayer();

  String _stance = 'stand';
  AssistantState _state = AssistantState.idle;
  late ActPlayer _basePlayer;
  ActPlayer? _actPlayer;

  double _lastDrawMs = -1000.0;
  double _lastTickMs = 0.0;
  double _nextTwitchMs = 4500.0;

  // Teleport timeline state
  bool _isTeleporting = false;
  bool _arriveOnly = false;
  double _teleportStartMs = 0.0;
  int _teleportFxPhase = 0;

  // Intro state (fx.js intro-*.webp sequence -> arrive)
  bool _isIntroActive = false;

  // Dormant mask state in sleeping (capri.js doze() -> chip.js Mask)
  double _sleepStartMs = 0.0;
  bool _isDozing = false;
  bool _isDormantMask = false;

  // Temporary impact flash sequence ([GREEN, INK, GREEN], etc.)
  double _flashStartMs = -1.0;
  List<List<double>> _flashColors = const [];

  CapriRig() {
    _basePlayer = ActPlayer('stand', startMs: 0.0);
  }

  AssistantState get state => _state;
  String get stance => _stance;

  /// Applies a new [AssistantState] and configures stance, acts, and FX layers.
  void setAssistantState(
    AssistantState newState,
    double nowMs, {
    ui.Size canvasSize = const ui.Size(211, 319),
  }) {
    final prevState = _state;
    _state = newState;

    // Si estaba dormida como máscara y cambia a otro estado, despierta y reconstruye el cuerpo
    if (_isDormantMask || _isDozing) {
      _isDozing = false;
      _isDormantMask = false;
      fx.hideMask();
      u.dissolve = 0.0;
      u.sparkle = 1.0;
      u.alpha = 1.0;
    }

    if (prevState == AssistantState.point && newState != AssistantState.point) {
      fx.clearPointer();
    }

    if (newState != AssistantState.teleporting && newState != AssistantState.intro) {
      _isTeleporting = false;
      _arriveOnly = false;
      _isIntroActive = false;
      u.collapse = 0.0;
      u.dissolve = 0.0;
      u.glitch = 0.0;
      u.split = 0.0;
      u.silAmount = 0.0;
      u.alpha = newState == AssistantState.sleeping ? 0.85 : 1.0;
    }

    final headPos = _headScreenPos(canvasSize);

    switch (newState) {
      case AssistantState.idle:
        if (prevState == AssistantState.point) {
          _setStance('stand', nowMs);
          perform('unpoint', nowMs, dir: 1);
        } else {
          _setStance('stand', nowMs);
          _actPlayer = null;
        }
        break;

      case AssistantState.listening:
        _setStance('stand', nowMs);
        perform('curious', nowMs, dir: 1);
        fx.cutin(headPos.dx - 75.0, headPos.dy, -1, nowMs, kind: 'look', lifeMs: 680.0);
        break;

      case AssistantState.thinking:
        _setStance('stand', nowMs);
        perform('uplink', nowMs, dir: 1);
        break;

      case AssistantState.speaking:
        _setStance('stand', nowMs);
        perform('talk', nowMs);
        break;

      case AssistantState.teleporting:
        _startTeleport(nowMs, arriveOnly: false);
        break;

      case AssistantState.sleeping:
        _setStance('sleep', nowMs);
        _actPlayer = null;
        _sleepStartMs = nowMs;
        _isDozing = false;
        _isDormantMask = false;
        u.alpha = 0.85;
        break;

      case AssistantState.sitting:
        _setStance('sit', nowMs);
        perform('plop', nowMs);
        break;

      case AssistantState.victory:
        _setStance('stand', nowMs);
        perform('victory', nowMs, dir: 1);
        break;

      case AssistantState.peek:
        _setStance('peek', nowMs, dir: 1);
        _actPlayer = null;
        break;

      case AssistantState.point:
        _setStance('pointing', nowMs, dir: 1);
        perform('point', nowMs, dir: 1);
        break;

      case AssistantState.intro:
        _startIntro(nowMs, canvasSize);
        break;
    }
  }

  void _setStance(String newStance, double nowMs, {int dir = 1}) {
    _stance = newStance;
    u.sit = newStance == 'sit' ? 1.0 : 0.0;
    _basePlayer = ActPlayer(newStance, dir: dir, startMs: nowMs);
  }

  void perform(String actName, double nowMs, {int dir = 1}) {
    final candidate = ActPlayer(actName, dir: dir, startMs: nowMs);
    if (_actPlayer != null && _actPlayer!.priority > candidate.priority) {
      return;
    }
    _actPlayer = candidate;
  }

  void _startTeleport(double nowMs, {bool arriveOnly = false}) {
    _isTeleporting = true;
    _arriveOnly = arriveOnly;
    _teleportStartMs = arriveOnly ? nowMs - 340.0 : nowMs;
    _teleportFxPhase = arriveOnly ? 3 : 0;
    u.glitchSeed = _rng.nextDouble() * 100.0;
  }

  void _startIntro(double nowMs, ui.Size canvasSize) {
    _setStance('stand', nowMs);
    _actPlayer = null;
    if (fx.grabFrames.containsKey('grab')) {
      _isIntroActive = true;
      _isTeleporting = false;
      u.alpha = 0.0;
      u.collapse = 1.0;
      u.dissolve = 0.5;
      final head = _headScreenPos(canvasSize);
      fx.startIntro(nowMs, toHead: head, headSize: canvasSize.width * 0.28);
    } else {
      // Fallback si las imágenes intro-*.webp aún no están en memoria (ej. en tests unitarios headless)
      _isIntroActive = false;
      perform('hop', nowMs);
    }
  }

  ui.Offset _headScreenPos(ui.Size canvasSize) {
    final scaleX = canvasSize.width / 352.0;
    final scaleY = canvasSize.height / 532.0;
    return ui.Offset((56.0 + 118.0) * scaleX, (56.0 + 132.0 + u.bob) * scaleY);
  }

  ui.Offset _handScreenPos(ui.Size canvasSize, int dir) {
    final scaleX = canvasSize.width / 352.0;
    final scaleY = canvasSize.height / 532.0;
    final hx = dir < 0 ? (56.0 + 42.0) * scaleX : (56.0 + 198.0) * scaleX;
    final hy = (56.0 + 150.0 + u.bob) * scaleY;
    return ui.Offset(hx, hy);
  }

  void _startFlash(List<List<double>> colors, double nowMs) {
    _flashColors = colors;
    _flashStartMs = nowMs;
  }

  bool _applyActiveFlash(double nowMs) {
    if (_flashStartMs < 0.0 || _flashColors.isEmpty) return false;
    final idx = ((nowMs - _flashStartMs) / kOnOnesMs).floor();
    if (idx >= 0 && idx < _flashColors.length) {
      final c = _flashColors[idx];
      u.silR = c[0];
      u.silG = c[1];
      u.silB = c[2];
      u.silAmount = 1.0;
      return true;
    }
    _flashStartMs = -1.0;
    u.silAmount = 0.0;
    return false;
  }

  /// Ejecuta los efectos y cut-ins asociados al `cue` de un keyframe (`capri.js` `onCue`).
  void _onCue(String cue, double nowMs, ui.Size canvasSize) {
    final h = _headScreenPos(canvasSize);
    final mane = ui.Offset(h.dx, h.dy - 24.0);
    final dir = _actPlayer?.dir ?? 1;

    switch (cue) {
      case 'gather':
        fx.burst(mane.dx, mane.dy, nowMs, count: 16, inward: true, power: 0.7, spread: 75.0);
        break;
      case 'launch':
        fx.slices(h.dx - 40.0, h.dy - 20.0, 95.0, 170.0, nowMs, count: 5);
        break;
      case 'peak':
        fx.lines(mane.dx, mane.dy, nowMs, inner: 70.0);
        fx.ring(mane.dx, mane.dy, nowMs, size: 0.8);
        fx.burst(mane.dx, mane.dy, nowMs, count: 28, power: 1.1, spread: 75.0);
        _startFlash(const [
          [0.21, 1.0, 0.48], // GREEN
          [0.08, 0.06, 0.11], // INK
          [0.21, 1.0, 0.48], // GREEN
        ], nowMs);
        break;
      case 'laugh':
        fx.cutin(
          h.dx - 80.0,
          h.dy - 10.0,
          dir,
          nowMs,
          kind: _rng.nextBool() ? 'laugh' : 'grin',
          lifeMs: 780.0,
        );
        break;
      case 'stare':
        fx.cutin(h.dx - 80.0, h.dy - 10.0, dir, nowMs, kind: 'many', lifeMs: 680.0);
        break;
      case 'notice':
      case 'minds':
      case 'snap':
        u.glitchSeed = _rng.nextDouble() * 100.0;
        u.glitch = 0.22;
        u.split = 2.0;
        break;
      case 'spot':
        final aim = ui.Offset(canvasSize.width * 0.82, canvasSize.height * 0.42);
        fx.ring(aim.dx, aim.dy, nowMs, size: 0.22);
        break;
      case 'coil':
        fx.burst(h.dx, h.dy + 24.0, nowMs, count: 10, inward: true, power: 0.45, spread: 50.0);
        break;
      case 'lock':
        final hand = _handScreenPos(canvasSize, dir);
        final aim = ui.Offset(
          dir > 0 ? canvasSize.width * 0.84 : canvasSize.width * 0.16,
          canvasSize.height * 0.44,
        );
        final targetRect = ui.Rect.fromCenter(center: aim, width: 64.0, height: 48.0);
        fx.bolt(hand, aim, nowMs, lifeMs: 280.0, width: 3.0);
        fx.ring(aim.dx, aim.dy, nowMs, size: 0.45);
        fx.burst(aim.dx, aim.dy, nowMs, count: 10, power: 0.5, spread: 18.0);
        fx.pointer(hand, targetRect, aim, nowMs, label: 'LOCK', lifeMs: 3200.0);
        fx.cutin(h.dx - 85.0, h.dy - 18.0, -dir, nowMs, kind: 'eyes', lifeMs: 560.0);
        break;
      case 'zap':
        final hand = _handScreenPos(canvasSize, dir);
        final aim = ui.Offset(
          dir > 0 ? canvasSize.width * 0.85 : canvasSize.width * 0.15,
          canvasSize.height * 0.5,
        );
        fx.bolt(hand, aim, nowMs, lifeMs: 260.0, width: 3.0);
        fx.burst(aim.dx, aim.dy, nowMs, count: 8, power: 0.4, spread: 16.0);
        fx.ring(aim.dx, aim.dy, nowMs, size: 0.25);
        break;
      case 'grin':
        fx.cutin(h.dx - 80.0, h.dy - 10.0, -dir, nowMs, kind: 'look', lifeMs: 600.0);
        break;
      case 'charge':
        final hand = _handScreenPos(canvasSize, dir);
        fx.burst(hand.dx, hand.dy, nowMs, count: 12, inward: true, power: 0.5, spread: 55.0);
        fx.cutin(h.dx - 85.0, h.dy - 12.0, -dir, nowMs, kind: 'eyes', lifeMs: 620.0);
        break;
      case 'surge':
        final hand = _handScreenPos(canvasSize, dir);
        final top = ui.Offset(canvasSize.width * 0.82, 16.0);
        fx.bolt(hand, top, nowMs, lifeMs: 420.0, width: 3.6);
        fx.ring(hand.dx, hand.dy, nowMs, size: 0.5);
        fx.lines(top.dx, top.dy, nowMs, inner: 40.0, lifeMs: 420.0);
        _startFlash(const [
          [0.08, 0.06, 0.11], // INK
          [1.0, 0.13, 0.32], // RED
        ], nowMs);
        break;
      case 'starlight':
      case 'home':
        u.sparkle = 1.7;
        break;
      case 'stars':
        u.sparkle = 0.25;
        for (int i = 0; i < 6; i++) {
          final a = -math.pi * (0.1 + 0.8 * _rng.nextDouble());
          fx.drift(mane.dx + math.cos(a) * 35.0, mane.dy + math.sin(a) * 25.0, a, nowMs);
        }
        break;
    }
  }

  double _frameIntervalMs() {
    if (_isTeleporting || _isIntroActive || (_actPlayer != null && _actPlayer!.act.fps == 24.0)) {
      return kOnOnesMs;
    }
    if (_state == AssistantState.sleeping && !_isDozing) {
      return kAsleepMs;
    }
    return kOnTwosMs;
  }

  /// Advances the rig and FX layer at [nowMs].
  /// Returns `true` if a one-shot sequence (like teleport/victory/intro) just completed.
  bool tick(
    double nowMs, {
    ui.Size canvasSize = const ui.Size(211, 319),
  }) {
    final dtSeconds = _lastTickMs > 0.0
        ? ((nowMs - _lastTickMs) / 1000.0).clamp(0.0, 0.08)
        : (1.0 / 60.0);
    _lastTickMs = nowMs;

    // 1. Avanzar capa de efectos 2D (cut-ins, intro-*.webp, máscara, rayos, fragmentos)
    final introLanded = fx.tick(nowMs, dtSeconds, canvasSize);
    if (_isIntroActive) {
      if (introLanded) {
        _isIntroActive = false;
        // Al aterrizar el close-up de intro, despliega el cuerpo completo con arrive()
        _startTeleport(nowMs, arriveOnly: true);
      } else {
        return false;
      }
    }

    // 2. Si está teletransportándose (o desplegándose tras la intro)
    if (_isTeleporting) {
      return _tickTeleport(nowMs, canvasSize);
    }

    // 3. Transición de sueño profundo a la máscara flotante (`capri.js` `doze()`)
    if (_state == AssistantState.sleeping) {
      final sleepElapsed = nowMs - _sleepStartMs;
      if (!_isDozing && !_isDormantMask && sleepElapsed >= kDozeAfterMs) {
        _isDozing = true;
        final h = _headScreenPos(canvasSize);
        for (int i = 0; i < 8; i++) {
          final a = -math.pi * (0.05 + 0.9 * _rng.nextDouble());
          fx.drift(h.dx + math.cos(a) * 42.0, h.dy + math.sin(a) * 32.0, a, nowMs);
        }
        fx.burst(h.dx, h.dy + 35.0, nowMs, count: 10, power: 0.35, spread: 65.0);
        u.glitchSeed = _rng.nextDouble() * 100.0;
      }
      if (_isDozing) {
        final dozeT = ((sleepElapsed - kDozeAfterMs) / 700.0).clamp(0.0, 1.0);
        u.seed = _rng.nextDouble() * 100.0;
        u.dissolve = 0.9 * (dozeT * dozeT);
        u.glitch = 0.25 * dozeT;
        u.sparkle = 1.0 - dozeT;
        if (dozeT >= 1.0) {
          _isDozing = false;
          _isDormantMask = true;
          u.alpha = 0.0;
          u.dissolve = 0.0;
          u.glitch = 0.0;
          fx.showMask(nowMs);
        }
        return false;
      }
      if (_isDormantMask) {
        return false;
      }
    }

    // 4. Control de cadencia cel-animation (12 FPS "en doses" o 24 FPS "en unos")
    final interval = _frameIntervalMs();
    if (nowMs - _lastDrawMs < interval - 1.0) {
      _applyActiveFlash(nowMs);
      return false;
    }
    _lastDrawMs = nowMs;

    bool completedOneShotState = false;

    // Nueva semilla por dibujo para que la línea hierva (line boil) como animación tradicional
    u.seed = _rng.nextDouble() * 100.0;

    // Limpiar glitches breves de notice/minds si no hay flash activo
    if (!_applyActiveFlash(nowMs)) {
      if (u.glitch > 0.0) u.glitch = 0.0;
      if (u.split > 0.0) u.split = 0.0;
    }

    // Muestrear postura base (stand, sit, peek, sleep, pointing)
    final under = _basePlayer.sample(nowMs);
    final pose = CapriResolvedPose();
    if (under != null) {
      pose.applyResolved(
        under.pose,
        directional: _basePlayer.act.directional,
        dir: _basePlayer.dir,
        facing: u.facing,
        reachScale: _basePlayer.reach,
      );
      if (under.cue != null) {
        _onCue(under.cue!, nowMs, canvasSize);
      }
    }

    // Muestrear acto superpuesto (victory, point, uplink, curious, look, talk, etc.)
    if (_actPlayer != null) {
      final drawing = _actPlayer!.sample(nowMs);
      if (drawing != null) {
        pose.applyResolved(
          drawing.pose,
          directional: _actPlayer!.act.directional,
          dir: _actPlayer!.dir,
          facing: u.facing,
          reachScale: _actPlayer!.reach,
        );
        if (drawing.cue != null) {
          _onCue(drawing.cue!, nowMs, canvasSize);
        }
      } else {
        final finishedName = _actPlayer!.name;
        _actPlayer = null;

        if (_state == AssistantState.speaking) {
          perform('talk', nowMs);
        } else if (_state == AssistantState.thinking) {
          final nextAct = finishedName == 'uplink'
              ? (_rng.nextBool() ? 'look' : 'alarm')
              : 'uplink';
          perform(nextAct, nowMs, dir: _rng.nextBool() ? 1 : -1);
        } else if (_state == AssistantState.listening) {
          perform('curious', nowMs, dir: 1);
        } else if ((_state == AssistantState.victory && finishedName == 'victory') ||
            (_state == AssistantState.intro && finishedName == 'hop')) {
          completedOneShotState = true;
        }
      }
    } else if (_state == AssistantState.idle && nowMs > _nextTwitchMs) {
      _nextTwitchMs = nowMs + 4500.0 + _rng.nextDouble() * 6500.0;
      _triggerIdleTwitch(nowMs);
    }

    // Devolver gradualmente sparkle a 1.0 si algún cue lo subió
    if (u.sparkle != 1.0 && _state != AssistantState.sleeping) {
      u.sparkle += (1.0 - u.sparkle) * 0.15;
    }

    // Aplicar pose resuelta a los uniformes del shader
    u.head = pose.head;
    u.mane = pose.mane;
    u.hair = pose.hair;
    u.armL = pose.armL;
    u.armR = pose.armR;
    u.longL = pose.longL;
    u.longR = pose.longR;
    u.kickL = pose.kickL;
    u.kickR = pose.kickR;
    u.bend = pose.bend;
    u.smearX = pose.smearX;
    u.smearY = pose.smearY;
    u.echoX = pose.echoX;
    u.echoY = pose.echoY;

    u.bob = _stance == 'sit' ? pose.bob.clamp(-3.0, 2.0) : pose.bob;
    u.tilt = pose.tilt;
    u.sx = pose.sx;
    u.sy = pose.sy;

    return completedOneShotState;
  }

  void _triggerIdleTwitch(double nowMs) {
    final r = _rng.nextDouble();
    final dir = _rng.nextBool() ? 1 : -1;
    if (r < 0.35) {
      perform('curious', nowMs, dir: dir);
    } else if (r < 0.65) {
      perform('look', nowMs);
    } else if (r < 0.80) {
      perform('gaze', nowMs, dir: dir);
    } else if (r < 0.90) {
      perform('spin', nowMs);
    } else {
      perform('split', nowMs);
    }
  }

  /// Secuencia vanish() + arrive() de `capri.js` (líneas 1234-1305) sincronizada con `fx.js`.
  bool _tickTeleport(double nowMs, ui.Size canvasSize) {
    final dt = nowMs - _teleportStartMs;
    u.seed = _rng.nextDouble() * 100.0;
    final h = _headScreenPos(canvasSize);
    final groundY = canvasSize.height * 0.89;

    // Fase 1 (0..90ms): glitch inicial + split cromático
    if (dt < 90.0) {
      final t = (dt / 90.0).clamp(0.0, 1.0);
      u.glitch = 0.35 * t;
      u.split = 3.0 * t;
      u.collapse = 0.0;
      u.dissolve = 0.0;
      u.alpha = 1.0;
      u.silAmount = 0.0;
      return false;
    }

    // Fase 2 (90..260ms): colapso en línea vertical de luz + burst + slices
    if (dt < 260.0) {
      if (_teleportFxPhase < 1) {
        _teleportFxPhase = 1;
        fx.burst(h.dx, h.dy + 40.0, nowMs, count: 20, spread: 80.0);
        fx.slices(h.dx - 40.0, h.dy - 20.0, 95.0, 180.0, nowMs);
      }
      final raw = ((dt - 90.0) / 170.0).clamp(0.0, 1.0);
      final t = raw * raw;
      u.collapse = t;
      u.glitch = 0.35 + (1.0 - 0.35) * t;
      u.dissolve = 0.5 * t;
      u.split = 3.0 + (9.0 - 3.0) * t;
      u.alpha = 1.0;
      u.silAmount = 0.0;
      return false;
    }

    // Fase 3 (260..340ms): desaparecida en el vacío (slit + beam)
    if (dt < 340.0) {
      if (_teleportFxPhase < 2) {
        _teleportFxPhase = 2;
        fx.slit(h.dx, h.dy - 35.0, groundY, nowMs, width: 42.0);
        fx.beam(h.dx, groundY, nowMs, width: 32.0);
      }
      u.alpha = 0.0;
      return false;
    }

    // Fase 4 (340..540ms): arrive — vórtice + columna de luz descendente + despliegue del cuerpo
    if (dt < 540.0) {
      if (_teleportFxPhase < 3) {
        _teleportFxPhase = 3;
        if (!_arriveOnly) {
          fx.beam(h.dx, groundY, nowMs, down: true, width: 32.0);
        }
        fx.vortex(h.dx, h.dy + 18.0, nowMs, radius: 105.0);
      }
      final raw = ((dt - 340.0) / 200.0).clamp(0.0, 1.0);
      final t = 1.0 - (1.0 - raw) * (1.0 - raw);
      u.alpha = 1.0;
      u.collapse = 1.0 - t;
      u.dissolve = 0.5 * (1.0 - t);
      u.glitch = 1.0 + (0.6 - 1.0) * t;
      u.split = 9.0 + (6.0 - 9.0) * t;
      u.silAmount = 0.0;
      return false;
    }

    // Fase 5 (540..582ms): impact frame 1 — silueta verde neón
    if (dt < 582.0) {
      u.collapse = 0.0;
      u.dissolve = 0.0;
      u.silR = 0.21;
      u.silG = 1.0;
      u.silB = 0.48;
      u.silAmount = 1.0;
      return false;
    }

    // Fase 6 (582..624ms): impact frame 2 — silueta tinta (ink)
    if (dt < 624.0) {
      u.silR = 0.08;
      u.silG = 0.06;
      u.silB = 0.11;
      u.silAmount = 1.0;
      return false;
    }

    // Fase 7 (624..844ms): asentamiento final + burst de llegada
    if (dt < 844.0) {
      if (_teleportFxPhase < 4) {
        _teleportFxPhase = 4;
        fx.burst(h.dx, h.dy + 35.0, nowMs, count: 10, power: 0.55, spread: 65.0);
      }
      final raw = ((dt - 624.0) / 220.0).clamp(0.0, 1.0);
      final t = 1.0 - (1.0 - raw) * (1.0 - raw);
      u.silAmount = 0.0;
      u.glitch = 0.6 * (1.0 - t);
      u.split = 6.0 * (1.0 - t);
      return false;
    }

    // ¡Completado!
    u.silAmount = 0.0;
    u.glitch = 0.0;
    u.split = 0.0;
    u.collapse = 0.0;
    u.dissolve = 0.0;
    u.alpha = 1.0;
    _isTeleporting = false;
    _arriveOnly = false;
    return true;
  }
}
