// Full-screen & overlay effect layer ported from mochiiwuff/capri-desktop
// (src/renderer/js/fx.js and src/renderer/js/chip.js).
// Required Notice: Copyright (c) 2026 mochiiwuff (https://github.com/mochiiwuff/capri-desktop)
// Non-commercial use only, see THIRD_PARTY_NOTICES.md.

import 'dart:math' as math;
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import '../../core/utils/sprite_sheet_loader.dart';

class CapriFxColors {
  static const Color red = Color(0xFFFF2152);
  static const Color green = Color(0xFF36FF7A);
  static const Color ink = Color(0xFF14101C);
  static const Color violet = Color(0xFF7B3DFF);
  static const Color paper = Color(0xFFFFF4F6);
  static const Color blue = Color(0xFF3D6BFF);
  static const Color maneRed = Color(0xFFFA0448);
  static const Color grabIris = Color(0xFF026FFE);
  static const Color grabPupil = Color(0xFFFDFDFB);
  static const Color grabInk = Color(0xFF010207);
}

/// Constantes geométricas del close-up de intro (`assets/capri/intro-*.webp`, 1672x941)
class _GrabGeom {
  static const double w = 1672.0;
  static const double h = 941.0;
  static const Offset face = Offset(830.0, 330.0);
  static const double faceSize = 430.0;
  static const List<Offset> eyes = [Offset(719.5, 382.5), Offset(935.0, 297.5)];
  static const double tilt = -0.38;
  static const double socket = 48.0;
  static const double iris = 34.0;
  static const double pupil = 13.5;
  static const Offset tag = Offset(1110.0, 175.0);
  static const double top = -48.0;
  static const List<Offset> hands = [Offset(0.0, 610.0), Offset(1672.0, 520.0)];

  static const List<List<double>> lock = [
    [926, 20],
    [983, 20],
    [978, -48],
  ];

  static const List<List<double>> mane = [
    [531, 480], [322, 472], [240, 444], [192, 440], [62, 415], [337, 371], [339, 299], [245, 245],
    [222, 229], [132, 170], [381, 214], [380, 137], [326, 62], [311, 39], [249, -47], [471, 81],
    [344, -142], [331, -256], [302, -321], [297, -435], [516, -153], [609, -203], [647, -286],
    [653, -328], [682, -459], [757, -155], [857, -288], [934, -360], [959, -396], [1049, -510],
    [989, -203], [1124, -240], [1226, -280], [1282, -330], [1403, -388], [1214, -121], [1208, 15],
    [1318, -8], [1382, -34], [1491, -47], [1247, 108], [1277, 174], [1350, 196], [1382, 200],
    [1493, 215], [1256, 268], [1278, 331], [1329, 372], [1380, 387], [1468, 435], [1243, 410],
    [1129, 480], [1030, 590], [630, 590],
  ];
}

/// Tiempos clave (en cuadros a 24 FPS) de la secuencia de intro (`fx.js` `INTRO_T`)
class _IntroT {
  static const int hands = 6;
  static const int right = 8;
  static const int reach = 10;
  static const int grab = 16;
  static const int hold = 21;
  static const int blink = 29;
  static const int hi = 34;
  static const int wave = 46;
  static const int regrab = 63;
  static const int happy = 65;
  static const int glance = 75;
  static const int slip = 80;
  static const int antic = 86;
  static const int shrink = 88;
  static const int land = 98;
  static const int end = 101;
}

class _FxItem {
  final String type;
  final double bornMs;
  double lifeMs;

  double x;
  double y;
  double vx;
  double vy;
  double rot;
  double vr;
  double len;
  double wid;
  Color color;
  int dir;
  double size;
  double width;
  double top;
  double bottom;
  bool down;
  String kind;
  String text;
  Offset from;
  Offset to;
  Rect rect;
  List<_VortexParticle> vortexPs;
  int cuedFrame = -1;
  bool landedFired = false;

  _FxItem({
    required this.type,
    required this.bornMs,
    required this.lifeMs,
    this.x = 0.0,
    this.y = 0.0,
    this.vx = 0.0,
    this.vy = 0.0,
    this.rot = 0.0,
    this.vr = 0.0,
    this.len = 16.0,
    this.wid = 5.0,
    this.color = CapriFxColors.red,
    this.dir = 1,
    this.size = 1.0,
    this.width = 30.0,
    this.top = 0.0,
    this.bottom = 100.0,
    this.down = false,
    this.kind = 'grin',
    this.text = '',
    this.from = Offset.zero,
    this.to = Offset.zero,
    this.rect = Rect.zero,
    this.vortexPs = const [],
  });
}

class _VortexParticle {
  final double a;
  final double r;
  final bool eye;
  final Color color;
  final double len;
  final double wid;

  const _VortexParticle({
    required this.a,
    required this.r,
    required this.eye,
    required this.color,
    required this.len,
    required this.wid,
  });
}

/// Gestiona los assets adicionales (`cutin-*.png`, `intro-*.webp`), la máscara durmiente (`chip.js`)
/// y todas las partículas/efectos de `fx.js` de `mochiiwuff/capri-desktop`.
class CapriFxLayer {
  static const double kFrameMs = 1000.0 / 24.0;
  static const List<String> cutinNames = ['grin', 'laugh', 'eyes', 'many', 'look'];
  static const List<String> grabFrameNames = [
    'grab',
    'mouth1',
    'mouth2',
    'mouth3',
    'wave1',
    'wave2',
    'wave3',
    'smear',
    'happy',
  ];
  static const List<String> _sayHiFrames = [
    'mouth1', 'mouth1', 'mouth3', 'mouth3', 'mouth3',
    'mouth3', 'mouth2', 'mouth2', 'mouth1', 'mouth1',
  ];
  static const List<String> _waveFrames = ['wave1', 'wave3', 'wave2', 'wave3', 'wave1'];

  final math.Random _rng = math.Random();
  final List<_FxItem> _items = [];

  final Map<String, ui.Image> cutins = {};
  final Map<String, ui.Image> grabFrames = {};
  bool assetsLoaded = false;

  // Estado de la máscara flotante cuando Capri duerme profundamente (`chip.js` Mask)
  bool maskVisible = false;
  bool maskWaking = false;
  double maskShownAtMs = 0.0;
  double maskNextPeekMs = 0.0;
  int? maskPeekEye;
  double maskPeekUntilMs = 0.0;

  bool get hasActiveItems => _items.isNotEmpty || maskVisible;

  /// Carga asíncronamente todas las imágenes `cutin-*.png` y `intro-*.webp`.
  Future<void> loadAssets() async {
    if (assetsLoaded) return;

    for (final name in cutinNames) {
      final img = await SpriteSheetLoader.load('assets/capri/cutin-$name.png');
      if (img != null) {
        cutins[name] = img;
      }
    }
    for (final name in grabFrameNames) {
      final img = await SpriteSheetLoader.load('assets/capri/intro-$name.webp');
      if (img != null) {
        grabFrames[name] = img;
      }
    }
    assetsLoaded = true;
  }

  void clear() {
    _items.clear();
  }

  double _rand(double min, double max) => min + _rng.nextDouble() * (max - min);

  T _pick<T>(List<T> list) => list[_rng.nextInt(list.length)];

  static double _hash(int i, int seed) {
    final v = math.sin(i * 127.1 + seed * 311.7) * 43758.5453;
    return v - v.floorToDouble();
  }

  // ---------- Efectos de fx.js ----------

  /// Anime cut-in (`assets/capri/cutin-<kind>.png`): banda inclinada con líneas de velocidad.
  void cutin(double x, double y, int dir, double nowMs, {String kind = 'grin', double lifeMs = 760.0}) {
    _items.add(_FxItem(
      type: 'cutin',
      bornMs: nowMs,
      lifeMs: lifeMs,
      x: x,
      y: y,
      dir: dir,
      kind: kind,
    ));
  }

  /// Secuencia completa de intro (`assets/capri/intro-*.webp`) agarrando los bordes de la ventana.
  void startIntro(double nowMs, {required Offset toHead, double headSize = 60.0}) {
    _items.removeWhere((it) => it.type == 'intro');
    _items.add(_FxItem(
      type: 'intro',
      bornMs: nowMs,
      lifeMs: kFrameMs * (_IntroT.end + 1),
      to: toHead,
      size: headSize,
      text: 'hi',
      kind: 'PROJECT CAPRICORN',
    ));
  }

  /// Explosión o succión de fragmentos poligonales (`shard`).
  void burst(
    double x,
    double y,
    double nowMs, {
    int count = 18,
    double power = 1.0,
    bool inward = false,
    double spread = 55.0,
  }) {
    const palette = [
      CapriFxColors.red,
      CapriFxColors.red,
      CapriFxColors.red,
      CapriFxColors.ink,
      CapriFxColors.green,
      CapriFxColors.violet,
      CapriFxColors.paper,
    ];
    for (int i = 0; i < count; i++) {
      final angle = _rand(0, math.pi * 2);
      final speed = _rand(150, 440) * power;
      final ox = x + _rand(-spread, spread) * 0.5;
      final oy = y + _rand(-spread, spread);
      final life = _rand(240, 560);
      _items.add(_FxItem(
        type: 'shard',
        bornMs: nowMs,
        lifeMs: life,
        x: inward ? ox + math.cos(angle) * speed * life / 1600.0 : ox,
        y: inward ? oy + math.sin(angle) * speed * life / 1600.0 : oy,
        vx: math.cos(angle) * speed * (inward ? -1.0 : 1.0),
        vy: math.sin(angle) * speed * (inward ? -1.0 : 1.0),
        rot: _rand(0, math.pi * 2),
        vr: _rand(-9, 9),
        len: _rand(8, 26),
        wid: _rand(3, 8),
        color: _pick(palette),
      ));
    }
  }

  /// Fragmento de melena que se desprende y flota hacia arriba (`drift`).
  void drift(double x, double y, double angle, double nowMs) {
    final speed = _rand(14, 30);
    _items.add(_FxItem(
      type: 'drift',
      bornMs: nowMs,
      lifeMs: _rand(1600, 2500),
      x: x,
      y: y,
      vx: math.cos(angle) * speed,
      vy: math.sin(angle) * speed - 10.0,
      rot: angle + _rand(-0.4, 0.4),
      vr: _rand(-0.8, 0.8),
      len: _rand(8, 16),
      wid: _rand(3, 5),
      color: _pick(const [
        CapriFxColors.red,
        CapriFxColors.red,
        CapriFxColors.ink,
        CapriFxColors.paper,
      ]),
    ));
  }

  /// Columna vertical de luz para teletransporte (`beam`).
  void beam(double x, double bottom, double nowMs, {bool down = false, double lifeMs = 200.0, double width = 28.0}) {
    _items.add(_FxItem(
      type: 'beam',
      bornMs: nowMs,
      lifeMs: lifeMs,
      x: x,
      bottom: bottom,
      down: down,
      width: width,
    ));
  }

  /// Hendidura del vacío (`slit`) con línea roja central.
  void slit(double x, double top, double bottom, double nowMs, {double width = 42.0, double lifeMs = 210.0}) {
    _items.add(_FxItem(
      type: 'slit',
      bornMs: nowMs,
      lifeMs: lifeMs,
      x: x,
      top: top,
      bottom: bottom,
      width: width,
    ));
  }

  /// Tiras horizontales de glitch desplazadas lateralmente (`slices`).
  void slices(double x, double y, double w, double h, double nowMs, {int count = 6, double lifeMs = 160.0}) {
    for (int i = 0; i < count; i++) {
      _items.add(_FxItem(
        type: 'slice',
        bornMs: nowMs,
        lifeMs: lifeMs * _rand(0.6, 1.0),
        x: x + _rand(-w * 0.25, w * 0.25),
        y: y + _rand(0, h),
        len: _rand(w * 0.3, w * 0.95),
        wid: _rand(2, 6),
        vx: _rand(-45, 45),
        color: _pick(const [
          CapriFxColors.red,
          CapriFxColors.green,
          CapriFxColors.violet,
          CapriFxColors.paper,
        ]),
      ));
    }
  }

  /// Vórtice de fragmentos de melena y estrellas verdes de 4 puntas al aparecer (`vortex`).
  void vortex(double x, double y, double nowMs, {double radius = 120.0, double lifeMs = 360.0, int count = 16}) {
    final ps = List<_VortexParticle>.generate(count, (i) {
      return _VortexParticle(
        a: (i / count) * math.pi * 2 + _rand(-0.25, 0.25),
        r: _rand(0.65, 1.1),
        eye: i % 4 == 0,
        color: _pick(const [
          CapriFxColors.red,
          CapriFxColors.red,
          CapriFxColors.ink,
          CapriFxColors.violet,
        ]),
        len: _rand(10, 24),
        wid: _rand(3, 7),
      );
    });
    _items.add(_FxItem(
      type: 'vortex',
      bornMs: nowMs,
      lifeMs: lifeMs,
      x: x,
      y: y,
      size: radius,
      vortexPs: ps,
    ));
  }

  /// Onda de choque de bordes duros (`ring`).
  void ring(double x, double y, double nowMs, {double size = 0.7}) {
    _items.add(_FxItem(
      type: 'ring',
      bornMs: nowMs,
      lifeMs: 280.0,
      x: x,
      y: y,
      size: size,
    ));
  }

  /// Líneas de concentración estilo manga (`lines`).
  void lines(double x, double y, double nowMs, {double inner = 85.0, double lifeMs = 440.0}) {
    _items.add(_FxItem(
      type: 'lines',
      bornMs: nowMs,
      lifeMs: lifeMs,
      x: x,
      y: y,
      size: inner,
    ));
  }

  /// Rayo quebrado rojo/violeta/blanco (`bolt`).
  void bolt(Offset from, Offset to, double nowMs, {double lifeMs = 340.0, double width = 2.8}) {
    _items.add(_FxItem(
      type: 'bolt',
      bornMs: nowMs,
      lifeMs: lifeMs,
      from: from,
      to: to,
      width: width,
    ));
  }

  /// Retícula de fijación con cable punteado y ojos de Capri (`pointer`).
  void pointer(Offset from, Rect rect, Offset aim, double nowMs, {String label = 'TARGET', double lifeMs = 2600.0}) {
    _items.removeWhere((it) => it.type == 'pointer');
    _items.add(_FxItem(
      type: 'pointer',
      bornMs: nowMs,
      lifeMs: lifeMs,
      from: from,
      to: aim,
      rect: rect,
      text: label,
    ));
  }

  void clearPointer() {
    _items.removeWhere((it) => it.type == 'pointer');
  }

  // ---------- Control de la máscara durmiente (`chip.js` Mask) ----------

  void showMask(double nowMs) {
    if (maskVisible) return;
    maskVisible = true;
    maskWaking = false;
    maskShownAtMs = nowMs;
    maskNextPeekMs = nowMs + _rand(3500, 6500);
    maskPeekEye = null;
  }

  void wakeMask(double nowMs) {
    maskWaking = true;
  }

  void hideMask() {
    maskVisible = false;
    maskWaking = false;
    maskPeekEye = null;
  }

  /// Actualiza física y ciclo de vida de los efectos activos.
  /// Retorna `true` si la intro acaba de aterrizar en `T.land` para desplegar el cuerpo.
  bool tick(double nowMs, double dtSeconds, Size canvasSize) {
    bool introLandedNow = false;

    _items.removeWhere((it) => (nowMs - it.bornMs) >= it.lifeMs);

    for (final it in List<_FxItem>.from(_items)) {
      if (it.type == 'shard') {
        it.x += it.vx * dtSeconds;
        it.y += it.vy * dtSeconds;
        it.vx *= 0.88;
        it.vy *= 0.88;
        it.rot += it.vr * dtSeconds;
      } else if (it.type == 'intro') {
        final frame = ((nowMs - it.bornMs) / kFrameMs).floor();
        if (frame >= _IntroT.land && !it.landedFired) {
          it.landedFired = true;
          introLandedNow = true;
        }
      }
    }

    return introLandedNow;
  }

  // ---------- Renderizado Canvas 2D ----------

  void paint(Canvas canvas, Size size, double nowMs) {
    if (maskVisible) {
      _paintSleepingMask(canvas, size, nowMs);
    }

    for (final it in List<_FxItem>.from(_items)) {
      final age = nowMs - it.bornMs;
      if (age < 0 || age >= it.lifeMs) continue;
      final t = (age / it.lifeMs).clamp(0.0, 1.0);
      _paintItem(canvas, size, it, t, age, nowMs);
    }
  }

  void _paintSleepingMask(Canvas canvas, Size size, double nowMs) {
    final step = (nowMs / (1000.0 / 12.0)).floor();
    final bob = const [0.0, -1.5, -3.0, -1.5][(step ~/ 6) % 4];
    final cx = size.width * 0.5;
    final cy = size.height * 0.45 + bob;
    final k = (size.width / 352.0) * 1.1;

    final landing = (nowMs - maskShownAtMs) < 125.0;
    if (landing) {
      drawMask(canvas, cx, cy, k, flat: CapriFxColors.paper);
      return;
    }

    List<double> eyes = [0.0, 0.0];
    if (nowMs > maskNextPeekMs && maskPeekEye == null) {
      maskPeekEye = _rng.nextBool() ? 0 : 1;
      maskPeekUntilMs = nowMs + _rand(700, 1100);
      maskNextPeekMs = nowMs + _rand(5000, 9000);
    }
    if (maskPeekEye != null) {
      if (nowMs > maskPeekUntilMs) {
        maskPeekEye = null;
      } else {
        eyes[maskPeekEye!] = 0.45; // Guiño de un ojo mientras duerme
      }
    }
    if (maskWaking) {
      eyes = [1.0, 1.0];
    }
    final shake = maskWaking ? _rand(-2.0, 2.0) : 0.0;
    drawMask(canvas, cx + shake, cy, k, eyes: eyes);
  }

  /// Dibuja la máscara verde de Capri (`fx.js` `drawMask` líneas 137-226).
  static void drawMask(
    Canvas canvas,
    double x,
    double y,
    double k, {
    List<double> eyes = const [1.0, 1.0],
    Offset? look,
    bool spike = true,
    Color? flat,
  }) {
    const facePts = <List<double>>[
      [-48, -20], [-12, -22], [48, -26], [46, 20], [-45, 23],
    ];
    const spikePts = <List<double>>[
      [-32, -20], [-37, -50], [-22, -63], [6, -67], [24, -75], [34, -99],
      [49, -90], [44, -66], [30, -48], [2, -42], [-10, -40], [-12, -21],
    ];
    const fangPts = <List<double>>[
      [-6, 22], [1, 27], [8, 22], [13, 26], [22, 21], [8, 52],
    ];
    const eyeCenters = <List<double>>[
      [-23, 0],
      [22, -3],
    ];

    Path buildPoly(List<List<double>> pts, [double dx = 0.0, double dy = 0.0]) {
      final path = Path();
      for (int i = 0; i < pts.length; i++) {
        final px = pts[i][0] + dx;
        final py = pts[i][1] + dy;
        if (i == 0) {
          path.moveTo(px, py);
        } else {
          path.lineTo(px, py);
        }
      }
      path.close();
      return path;
    }

    final shapes = spike ? [spikePts, facePts, fangPts] : [facePts, fangPts];

    canvas.save();
    canvas.translate(x, y);
    canvas.scale(k, k);

    final shadowPaint = Paint()
      ..color = flat ?? CapriFxColors.violet
      ..style = PaintingStyle.fill;
    for (final s in shapes) {
      canvas.drawPath(buildPoly(s, 3.0, 3.0), shadowPaint);
    }

    if (flat != null) {
      for (final s in shapes) {
        canvas.drawPath(buildPoly(s), shadowPaint);
      }
      canvas.restore();
      return;
    }

    final greenFill = Paint()
      ..color = CapriFxColors.green
      ..style = PaintingStyle.fill;
    if (spike) {
      canvas.drawPath(buildPoly(spikePts), greenFill);
    }
    canvas.drawPath(buildPoly(facePts), greenFill);

    final fangPath = buildPoly(fangPts);
    canvas.drawPath(
      fangPath,
      Paint()
        ..color = CapriFxColors.paper
        ..style = PaintingStyle.fill,
    );
    canvas.drawPath(
      fangPath,
      Paint()
        ..color = CapriFxColors.green
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.2,
    );

    for (int i = 0; i < eyeCenters.length; i++) {
      final ex = eyeCenters[i][0];
      final ey = eyeCenters[i][1];
      final o = i < eyes.length ? eyes[i] : 1.0;

      if (o < 0.15) {
        final shutPath = Path()
          ..moveTo(ex - 15, ey - 4)
          ..lineTo(ex, ey + 5)
          ..lineTo(ex + 15, ey - 4);
        canvas.drawPath(
          shutPath,
          Paint()
            ..color = CapriFxColors.ink
            ..style = PaintingStyle.stroke
            ..strokeWidth = 4.5,
        );
        continue;
      }

      double px = 0.0, py = 0.0;
      if (look != null) {
        final dx = look.dx - (x + ex * k);
        final dy = look.dy - (y + ey * k);
        final d = math.sqrt(dx * dx + dy * dy);
        if (d > 0.001) {
          px = (dx / d) * 2.6;
          py = (dy / d) * 2.2;
        }
      }

      canvas.save();
      canvas.translate(ex, ey);
      canvas.scale(1.0, o);

      final almond = Path()
        ..moveTo(-19, 0)
        ..quadraticBezierTo(0, -24, 19, 0)
        ..quadraticBezierTo(0, 24, -19, 0)
        ..close();
      canvas.drawPath(almond, Paint()..color = CapriFxColors.ink);

      canvas.drawCircle(Offset(px * 0.4, py * 0.4), 10.5, Paint()..color = CapriFxColors.green);
      canvas.drawCircle(Offset(px * 0.4, py * 0.4), 8.8, Paint()..color = CapriFxColors.ink);
      canvas.drawCircle(Offset(px * 0.7, py * 0.7), 7.6, Paint()..color = CapriFxColors.blue);
      canvas.drawOval(
        Rect.fromCenter(center: Offset(px, py), width: 6.0, height: 8.0),
        Paint()..color = CapriFxColors.paper,
      );
      canvas.restore();
    }

    canvas.restore();
  }

  /// Dibuja uno de los ojos de Capri (`fx.js` `drawEye` líneas 230-259).
  static void drawEye(Canvas canvas, double x, double y, double r, double open, {Offset? look}) {
    if (open <= 0.02) return;
    double px = 0.0, py = 0.0;
    if (look != null) {
      final dx = look.dx - x;
      final dy = look.dy - y;
      final d = math.sqrt(dx * dx + dy * dy);
      if (d > 0.001) {
        px = (dx / d) * r * 0.2;
        py = (dy / d) * r * 0.2;
      }
    }
    canvas.save();
    canvas.translate(x, y);
    canvas.scale(1.0, open);
    canvas.drawCircle(const Offset(-3, 3), r, Paint()..color = CapriFxColors.violet);
    canvas.drawCircle(Offset.zero, r, Paint()..color = CapriFxColors.ink);
    canvas.drawCircle(
      Offset.zero,
      r * 0.8,
      Paint()
        ..color = CapriFxColors.green
        ..style = PaintingStyle.stroke
        ..strokeWidth = r * 0.16,
    );
    canvas.drawCircle(Offset(px * 0.6, py * 0.6), r * 0.52, Paint()..color = CapriFxColors.blue);
    canvas.drawOval(
      Rect.fromCenter(center: Offset(px, py), width: r * 0.32, height: r * 0.48),
      Paint()..color = CapriFxColors.paper,
    );
    canvas.restore();
  }

  void _paintShard(Canvas canvas, double len, double wid, Color color) {
    Path shape(double dx, double dy) {
      return Path()
        ..moveTo(-len * 0.5 + dx, dy)
        ..lineTo(dx, -wid * 0.5 + dy)
        ..lineTo(len * 0.5 + dx, wid * 0.15 + dy)
        ..lineTo(-len * 0.1 + dx, wid * 0.5 + dy)
        ..close();
    }

    canvas.drawPath(shape(-2, 2), Paint()..color = CapriFxColors.violet);
    canvas.drawPath(shape(0, 0), Paint()..color = color);
  }

  void _paintSparkle(Canvas canvas, double x, double y, double s, Color fill, [Color? core]) {
    Path starPath(double dx, double dy, double k) {
      final r = s * k;
      final w = r * 0.24;
      return Path()
        ..moveTo(x + dx, y - r + dy)
        ..lineTo(x + w + dx, y - w + dy)
        ..lineTo(x + r + dx, y + dy)
        ..lineTo(x + w + dx, y + w + dy)
        ..lineTo(x + dx, y + r + dy)
        ..lineTo(x - w + dx, y + w + dy)
        ..lineTo(x - r + dx, y + dy)
        ..lineTo(x - w + dx, y - w + dy)
        ..close();
    }

    canvas.drawPath(starPath(-2, 2, 1.0), Paint()..color = CapriFxColors.violet);
    canvas.drawPath(starPath(0, 0, 1.0), Paint()..color = fill);
    if (core != null) {
      canvas.drawPath(starPath(0, 0, 0.36), Paint()..color = core);
    }
  }

  void _strokePolyline(Canvas canvas, List<Offset> pts, Color color, double width, [double dx = 0, double dy = 0]) {
    if (pts.length < 2) return;
    final path = Path();
    for (int i = 0; i < pts.length; i++) {
      final px = pts[i].dx + dx;
      final py = pts[i].dy + dy;
      if (i == 0) {
        path.moveTo(px, py);
      } else {
        path.lineTo(px, py);
      }
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = width
        ..strokeJoin = StrokeJoin.miter,
    );
  }

  List<Offset> _jag(Offset a, Offset b, double jitter, {bool zig = false}) {
    final dx = b.dx - a.dx;
    final dy = b.dy - a.dy;
    final len = math.sqrt(dx * dx + dy * dy);
    if (len < 1.0) return [a, b];
    final nx = -dy / len;
    final ny = dx / len;
    final n = math.max(5, (len / (zig ? 28.0 : 22.0)).round());
    int side = _rng.nextBool() ? 1 : -1;
    final pts = <Offset>[];
    for (int i = 0; i <= n; i++) {
      double t = i / n;
      double off = 0.0;
      if (i > 0 && i < n) {
        if (zig) {
          t += _rand(-0.25, 0.25) / n;
          if (_rng.nextDouble() < 0.8) side = -side;
          off = side * _rand(0.2, 1.0) * jitter;
        } else {
          off = _rand(-1.0, 1.0) * jitter;
        }
      }
      pts.add(Offset(
        ui.lerpDouble(a.dx, b.dx, t)! + nx * off,
        ui.lerpDouble(a.dy, b.dy, t)! + ny * off,
      ));
    }
    return pts;
  }

  void _paintItem(Canvas canvas, Size size, _FxItem it, double t, double ageMs, double nowMs) {
    switch (it.type) {
      case 'shard':
        final k = t < 0.7 ? 1.0 : 1.0 - (t - 0.7) / 0.3;
        canvas.save();
        canvas.translate(it.x, it.y);
        canvas.rotate(it.rot);
        _paintShard(canvas, it.len * k, it.wid * k, it.color);
        canvas.restore();
        break;

      case 'drift':
        final age = (((t * it.lifeMs) / 1000.0 * 12.0).floorToDouble()) / 12.0;
        final k = t < 0.6 ? 1.0 : 1.0 - (t - 0.6) / 0.4;
        canvas.save();
        canvas.translate(it.x + it.vx * age, it.y + it.vy * age);
        canvas.rotate(it.rot + it.vr * age);
        _paintShard(canvas, it.len * (0.6 + 0.4 * k), it.wid * k, it.color);
        canvas.restore();
        break;

      case 'slice':
        final paint = Paint()..color = it.color.withValues(alpha: (1.0 - t).clamp(0.0, 1.0));
        canvas.drawRect(Rect.fromLTWH(it.x + it.vx * t, it.y, it.len, it.wid), paint);
        break;

      case 'slit':
        final k = (t * 5.0).floorToDouble() / 5.0;
        final w = math.max(3.0, it.width * (1.0 - k));
        final h = it.bottom - it.top;
        canvas.drawRect(Rect.fromLTWH(it.x - w / 2 - 3, it.top, w + 6, h), Paint()..color = CapriFxColors.violet);
        canvas.drawRect(Rect.fromLTWH(it.x - w / 2, it.top, w, h), Paint()..color = CapriFxColors.ink);
        canvas.drawRect(Rect.fromLTWH(it.x - 1, it.top + h * 0.08, 2, h * 0.84), Paint()..color = CapriFxColors.red);
        break;

      case 'beam':
        final k = it.down ? 1.0 - t : t;
        final w = it.width * (1.0 - t) + 2.0;
        final top = it.down ? it.bottom * k * 0.15 : 0.0;
        final h = it.bottom - top;
        final leftPts = <Offset>[];
        final rightPts = <Offset>[];
        for (double y = top; y <= it.bottom; y += 16.0) {
          leftPts.add(Offset(it.x - (w / 2 + _rand(0, w * 0.35)), y));
          rightPts.add(Offset(it.x + (w / 2 + _rand(0, w * 0.35)), y));
        }
        final allPts = [...leftPts, ...rightPts.reversed];
        Path poly(double dx) {
          final p = Path();
          for (int i = 0; i < allPts.length; i++) {
            if (i == 0) {
              p.moveTo(allPts[i].dx + dx, allPts[i].dy);
            } else {
              p.lineTo(allPts[i].dx + dx, allPts[i].dy);
            }
          }
          p.close();
          return p;
        }
        canvas.drawPath(poly(-4.0), Paint()..color = CapriFxColors.violet);
        canvas.drawPath(poly(0.0), Paint()..color = CapriFxColors.red);
        canvas.drawRect(
          Rect.fromLTWH(it.x - math.max(1.0, w * 0.12), top, math.max(2.0, w * 0.24), h),
          Paint()..color = CapriFxColors.paper,
        );
        break;

      case 'vortex':
        final k = (t * 8.0).floorToDouble() / 8.0;
        for (final p in it.vortexPs) {
          final ang = p.a + k * 4.2;
          final rr = it.size * p.r * (1.0 - k);
          final px = it.x + math.cos(ang) * rr;
          final py = it.y + math.sin(ang) * rr * 0.85;
          if (p.eye) {
            _paintSparkle(canvas, px, py, 10.0 * (1.0 - k) + 3.0, CapriFxColors.green, CapriFxColors.ink);
          } else {
            canvas.save();
            canvas.translate(px, py);
            canvas.rotate(ang + math.pi / 2);
            _paintShard(canvas, p.len * (1.0 - k * 0.6), p.wid * (1.0 - k * 0.5), p.color);
            canvas.restore();
          }
        }
        break;

      case 'ring':
        final k = (t * 6.0).floorToDouble() / 6.0;
        final r = (30.0 + 160.0 * k) * it.size;
        final lw = math.max(1.0, 6.5 * (1.0 - k) * it.size);
        canvas.drawCircle(
          Offset(it.x - 2.5, it.y + 2.5),
          r,
          Paint()
            ..color = CapriFxColors.violet
            ..style = PaintingStyle.stroke
            ..strokeWidth = lw,
        );
        canvas.drawCircle(
          Offset(it.x, it.y),
          r,
          Paint()
            ..color = CapriFxColors.red
            ..style = PaintingStyle.stroke
            ..strokeWidth = lw,
        );
        break;

      case 'lines':
        final outer = it.size * 2.8;
        final alpha = t > 0.7 ? (1.0 - (((t - 0.7) / 0.3) * 3.0).floorToDouble() / 3.0).clamp(0.0, 1.0) : 1.0;
        if (alpha <= 0.0) break;
        final seed = (ageMs / (kFrameMs * 2)).floor();
        for (int i = 0; i < 24; i++) {
          final a = _hash(i, seed) * math.pi * 2;
          final w = 0.01 + _hash(i + 30, seed) * 0.02;
          final r0 = it.size * (1.0 + _hash(i + 60, seed) * 0.5);
          final cPick = i % 5 == 0
              ? CapriFxColors.red
              : (i % 4 == 0 ? CapriFxColors.violet : CapriFxColors.paper);
          final path = Path()
            ..moveTo(it.x + math.cos(a - w) * outer, it.y + math.sin(a - w) * outer)
            ..lineTo(it.x + math.cos(a) * r0, it.y + math.sin(a) * r0)
            ..lineTo(it.x + math.cos(a + w) * outer, it.y + math.sin(a + w) * outer)
            ..close();
          canvas.drawPath(path, Paint()..color = cPick.withValues(alpha: alpha));
        }
        break;

      case 'bolt':
        final frame = (ageMs / kFrameMs).floor();
        if (frame % 3 == 2) break;
        final pts = _jag(it.from, it.to, 12.0, zig: true);
        _strokePolyline(canvas, pts, CapriFxColors.violet, it.width + 1.0, -1.5, 1.5);
        _strokePolyline(canvas, pts, CapriFxColors.red, it.width + 1.0);
        _strokePolyline(canvas, pts, CapriFxColors.paper, math.max(0.8, it.width * 0.35));
        break;

      case 'pointer':
        _paintPointerReticle(canvas, size, it, ageMs);
        break;

      case 'cutin':
        _paintCutin(canvas, size, it, t);
        break;

      case 'intro':
        _paintIntro(canvas, size, it, ageMs);
        break;
    }
  }

  /// Renderiza el banner anime `cutin-*.png` (`fx.js` `case 'cutin':` líneas 1800-1838).
  void _paintCutin(Canvas canvas, Size size, _FxItem it, double t) {
    final img = cutins[it.kind] ?? cutins['grin'];
    if (img == null) return;

    const double baseW = 195.0;
    const double baseH = 76.0;
    const double skew = 18.0;

    final open = t < 0.06 ? 0.3 : (t < 0.12 ? 0.7 : 1.0);
    final tall = t > 0.9 ? 0.12 : (t > 0.82 ? 0.5 : 1.0);
    final w = baseW * open;
    final h = baseH * tall;

    final rawX0 = it.dir > 0 ? it.x : it.x - w;
    final double x0 = rawX0.clamp(6.0, math.max(6.0, size.width - w - skew - 8.0)).toDouble();
    final double y0 = (it.y - h / 2).clamp(8.0, math.max(8.0, size.height - h - 8.0)).toDouble();

    Path band(double dx, double dy) {
      return Path()
        ..moveTo(x0 + skew + dx, y0 + dy)
        ..lineTo(x0 + w + skew + dx, y0 + dy)
        ..lineTo(x0 + w + dx, y0 + h + dy)
        ..lineTo(x0 + dx, y0 + h + dy)
        ..close();
    }

    canvas.save();
    canvas.drawPath(band(5.0, 5.0), Paint()..color = CapriFxColors.violet);
    final mainBand = band(0.0, 0.0);
    canvas.drawPath(mainBand, Paint()..color = CapriFxColors.ink);
    canvas.clipPath(mainBand);

    // Líneas de velocidad horizontales
    for (int i = 0; i < 8; i++) {
      final lineColor = (i % 3 != 0) ? CapriFxColors.red : CapriFxColors.paper;
      canvas.drawRect(
        Rect.fromLTWH(
          x0 + _rand(-15, w),
          y0 + _rand(0, h),
          _rand(25, 85),
          _rand(1, 2.5),
        ),
        Paint()..color = lineColor,
      );
    }

    // Imagen close-up del show (`cutin-*.png` 360x240) con ligero zoom y vibración
    final zoom = ((h * 1.12) / 240.0) * (1.0 + t * 0.08);
    final fw = 360.0 * zoom;
    final fh = 240.0 * zoom;
    final cx = x0 + w / 2 + skew / 2 + _rand(-1.5, 1.5);
    final cy = y0 + h / 2 + _rand(-1.5, 1.5);

    canvas.drawImageRect(
      img,
      Rect.fromLTWH(0, 0, img.width.toDouble(), img.height.toDouble()),
      Rect.fromCenter(center: Offset(cx, cy), width: fw, height: fh),
      Paint()..filterQuality = FilterQuality.medium,
    );

    // Borde superior rojo
    canvas.drawRect(Rect.fromLTWH(x0, y0, w + skew, 3.0), Paint()..color = CapriFxColors.red);
    canvas.restore();
  }

  /// Renderiza la retícula de apuntado con cable de datos y ojos de Capri (`fx.js` `case 'pointer':`).
  void _paintPointerReticle(Canvas canvas, Size size, _FxItem it, double ageMs) {
    final frame = (ageMs / kFrameMs).floor();
    final leftMs = it.lifeMs - ageMs;
    final back = leftMs < 180.0 ? ((180.0 - leftMs) / 180.0).clamp(0.0, 1.0) : 0.0;
    final grow = (math.min(1.0, (frame + 1) / 2.0) * (1.0 - back)).clamp(0.0, 1.0);

    final a = it.from;
    final b = it.to;
    final ex = ui.lerpDouble(a.dx, b.dx, grow)!;
    final ey = ui.lerpDouble(a.dy, b.dy, grow)!;

    // Cable segmentado con partículas de datos corriendo hacia el objetivo
    _strokePolyline(canvas, [a, Offset(ex, ey)], CapriFxColors.violet, 3.0, -1.5, 1.5);
    _strokePolyline(canvas, [a, Offset(ex, ey)], CapriFxColors.paper, 1.6);

    if (back == 0.0) {
      for (int i = 0; i < 3; i++) {
        final u = ((frame ~/ 2) * 0.06 + i / 3.0) % 1.0;
        if (u > grow) continue;
        final px = ui.lerpDouble(a.dx, b.dx, u)!;
        final py = ui.lerpDouble(a.dy, b.dy, u)!;
        canvas.drawRect(Rect.fromLTWH(px - 3, py - 1, 4, 4), Paint()..color = CapriFxColors.violet);
        canvas.drawRect(
          Rect.fromLTWH(px - 2, py - 2, 4, 4),
          Paint()..color = i > 0 ? CapriFxColors.green : CapriFxColors.paper,
        );
      }
    }

    // Retícula en las esquinas
    const slam = [40.0, 22.0, 10.0, 2.0, 7.0, 4.0];
    double pad = frame < slam.length ? slam[frame] : 4.0;
    if (back > 0) pad += back * 35.0;

    final r = it.rect.inflate(pad);
    final flash = frame < 5;
    final mainColor = flash ? CapriFxColors.paper : CapriFxColors.red;
    final arm = math.min(18.0, math.min(r.width / 3.0, r.height / 3.0));

    final corners = [
      [r.left, r.top, 1.0, 1.0],
      [r.right, r.top, -1.0, 1.0],
      [r.left, r.bottom, 1.0, -1.0],
      [r.right, r.bottom, -1.0, -1.0],
    ];

    for (final c in corners) {
      final cx = c[0], cy = c[1], sx = c[2], sy = c[3];
      final pts = [Offset(cx, cy + sy * arm), Offset(cx, cy), Offset(cx + sx * arm, cy)];
      _strokePolyline(canvas, pts, CapriFxColors.violet, 4.0, -1.5, 1.5);
      _strokePolyline(canvas, pts, mainColor, 3.0);
    }

    // Dos ojos de Capri abriéndose en las esquinas de la retícula
    if (back == 0.0 && frame >= 6) {
      final open = math.min(1.0, (frame - 6) / 3.0);
      final blink = (frame % 70 > 66) ? 0.15 : 1.0;
      drawEye(canvas, r.right - 3, r.top + 3, 6.5, open * blink, look: r.center);
      drawEye(canvas, r.left + 3, r.bottom - 3, 6.5, open * blink, look: r.center);
    }
  }

  // ---------- Renderizado de la Intro (`assets/capri/intro-*.webp`, fx.js líneas 1839-2085) ----------

  void _paintIntro(Canvas canvas, Size size, _FxItem it, double ageMs) {
    final baseGrab = grabFrames['grab'];
    if (baseGrab == null) return;

    final vw = size.width;
    final vh = size.height;
    final s = math.max(vw / _GrabGeom.w, vh / _GrabGeom.h);
    const k = 1.07;
    final low = math.min(
      (_GrabGeom.face.dy - _GrabGeom.top) * s * k + 8.0,
      vh - 20.0 - (_GrabGeom.hands[0].dy - _GrabGeom.face.dy) * s * k,
    );
    final at = Offset(
      (vw - _GrabGeom.w * s) / 2.0 + _GrabGeom.face.dx * s,
      math.max((vh - _GrabGeom.h * s) / 2.0 + _GrabGeom.face.dy * s, low),
    );
    final to = it.to;
    final ctrl = Offset(
      ui.lerpDouble(at.dx, to.dx, 0.25)! - (to.dx - at.dx) * 0.2,
      ui.lerpDouble(at.dy, to.dy, 0.15)!,
    );

    final t = ageMs / kFrameMs;
    final frame = t.floor();

    Offset onScreen(Offset p, [double x = 0, double y = 0, double scaleK = 1.0]) {
      final cx = x == 0 ? at.dx : x;
      final cy = y == 0 ? at.dy : y;
      return Offset(
        cx + (p.dx - _GrabGeom.face.dx) * s * scaleK,
        cy + (p.dy - _GrabGeom.face.dy) * s * scaleK,
      );
    }

    // Disparar efectos por cuadro una sola vez
    for (int f = it.cuedFrame + 1; f <= frame; f++) {
      if (f == _IntroT.hands || f == _IntroT.right) {
        final hand = onScreen(_GrabGeom.hands[f == _IntroT.hands ? 0 : 1]);
        burst(hand.dx.clamp(10.0, vw - 10.0), hand.dy, ageMs + it.bornMs, count: 8, power: 0.6, spread: 40);
      } else if (f == _IntroT.grab) {
        lines(at.dx, at.dy, ageMs + it.bornMs, inner: math.min(vw, vh) * 0.35, lifeMs: 300);
        burst(at.dx, at.dy, ageMs + it.bornMs, count: 14, power: 0.9, spread: 90);
      }
    }
    it.cuedFrame = frame;

    // Dirección de la mirada en la intro
    final towardX = (to.dx - at.dx).sign == 0 ? 1.0 : (to.dx - at.dx).sign;
    final towardY = (to.dy - at.dy).sign == 0 ? 1.0 : (to.dy - at.dy).sign;
    final sinceHold = frame - _IntroT.hold;
    Offset look = const Offset(0, 3);
    if (sinceHold < 3) {
      look = Offset.zero;
    } else if (sinceHold < 7) {
      look = const Offset(-10, -3);
    } else if (sinceHold < 11) {
      look = const Offset(10, -4);
    } else if (frame >= _IntroT.glance) {
      look = Offset(towardX * 10.0, towardY * 7.0);
    }

    final b = frame - _IntroT.blink;
    final open = (b == 0 || b == 3) ? 0.5 : ((b == 1 || b == 2) ? 0.0 : 1.0);
    final n = frame >> 1;
    double noise(int seed) => _hash(n, seed) * 2.0 - 1.0;

    if (frame < _IntroT.hands) {
      if (frame % 2 == 0 || frame == _IntroT.hands - 1) {
        _paintScreenEdges(canvas, vw, vh, frame);
      }
      return;
    }

    if (frame < _IntroT.reach) {
      const rL = 0.16;
      final rR = frame >= _IntroT.right ? 0.16 : 0.0;
      final g = frame - (frame >= _IntroT.right ? _IntroT.right : _IntroT.hands);
      final jolt = g == 0 ? 7.0 : (g == 1 ? -3.0 : 0.0);
      _paintGrabbed(
        canvas,
        s,
        at.dx + jolt * (frame >= _IntroT.right ? 1.0 : -1.0),
        at.dy + 70.0 * s,
        1.04,
        look: look,
        open: open,
        clipPath: _cutEdges(rL, rR, frame),
      );
      return;
    }

    if (frame < _IntroT.grab) {
      final u = ((t - _IntroT.reach + 1.0) / (_IntroT.grab - _IntroT.reach)).clamp(0.0, 1.0);
      final r = ui.lerpDouble(0.16, 1.2, u * u)!;
      _paintGrabbed(
        canvas,
        s,
        at.dx,
        at.dy + 70.0 * s * (1.0 - u * u),
        ui.lerpDouble(1.04, 1.02, u)!,
        look: look,
        open: open,
        clipPath: _cutEdges(r, r, frame),
      );
      return;
    }

    if (frame < _IntroT.hold) {
      final g = frame - _IntroT.grab;
      const shakes = [24.0, -17.0, 11.0, -6.0, 3.0];
      final shake = shakes[g.clamp(0, shakes.length - 1)];
      final x = at.dx + shake * 0.5;
      final y = at.dy - shake * 0.25;
      if (g == 0) {
        _paintGrabbed(canvas, s, x, y, 1.18, flatColor: CapriFxColors.paper);
      } else if (g == 1) {
        _paintGrabbed(canvas, s, x + 6, y + 6, 1.08, flatColor: CapriFxColors.violet);
        _paintGrabbed(canvas, s, x, y, 1.08, flatColor: CapriFxColors.ink);
      } else {
        const scales = [1.05, 1.02, 1.03];
        _paintGrabbed(canvas, s, x, y, scales[(g - 2).clamp(0, 2)], look: look, open: open);
      }
      return;
    }

    final tagAt = onScreen(_GrabGeom.tag);
    final fs = (vh * 0.065).clamp(24.0, 44.0);

    if (frame < _IntroT.slip) {
      final h0 = frame - _IntroT.hi - 2;
      final hiIdx = frame - _IntroT.hi;
      String cel = (hiIdx >= 0 && hiIdx < _sayHiFrames.length) ? _sayHiFrames[hiIdx] : 'grab';
      double shake = 0.0;

      if (frame >= _IntroT.wave && frame < _IntroT.wave + 2) {
        cel = 'smear';
        if (frame == _IntroT.wave) shake = 4.0;
      } else if (frame >= _IntroT.wave + 2 && frame < _IntroT.regrab) {
        final wIdx = ((frame - _IntroT.wave - 2) ~/ 3).clamp(0, _waveFrames.length - 1);
        cel = _waveFrames[wIdx];
      } else if (frame >= _IntroT.regrab && frame < _IntroT.happy) {
        cel = 'smear';
      } else if (frame >= _IntroT.happy && frame < _IntroT.glance) {
        cel = 'happy';
        if (frame < _IntroT.happy + 2) {
          shake = frame == _IntroT.happy ? 5.0 : -3.0;
        }
      }

      const bobs = [0.024, 0.024, -0.017, -0.017, 0.009, 0.009, 0.0, 0.0];
      final bob = (h0 >= 0 && h0 < bobs.length) ? bobs[h0] : 0.0;
      final pop = h0 == 0 ? 0.025 : (h0 == 1 ? 0.012 : 0.0);
      final creep = 0.03 * ((t - _IntroT.hold) / (_IntroT.slip - _IntroT.hold)).clamp(0.0, 1.0);
      final scaleK = 1.025 + pop + creep + 0.006 * math.sin(t / 7.0);

      _paintGrabbed(
        canvas,
        s,
        at.dx + noise(1) * 1.5 + shake,
        at.dy + noise(2) * 1.5,
        scaleK,
        rot: noise(3) * 0.003 + bob,
        look: look,
        open: open,
        cel: cel,
      );

      if (h0 >= 0) {
        final tagScale = h0 == 0 ? 0.35 : (h0 == 1 ? 1.22 : (h0 == 2 ? 0.94 : 1.0));
        _paintHiTag(canvas, tagAt.dx.clamp(16.0, vw - 90.0), tagAt.dy.clamp(24.0, vh - 40.0), it.text, fs, tagScale, 1.0);
      }
      return;
    }

    const kHold = 1.055;
    if (frame < _IntroT.antic) {
      final g = frame - _IntroT.slip;
      final u = ((t - _IntroT.slip + 1.0) / (_IntroT.antic - _IntroT.slip)).clamp(0.0, 1.0);
      final half = ui.lerpDouble(_GrabGeom.w * 0.5 + 60.0, 330.0, 1.0 - (1.0 - u) * (1.0 - u))!;
      final y = at.dy + 56.0 * s * u * u;
      _paintGrabbed(
        canvas,
        s,
        at.dx,
        y,
        kHold,
        look: look,
        open: open,
        clipPath: _cutBand(half, frame),
      );
      if (g == 0) {
        _paintHiTag(canvas, tagAt.dx.clamp(16.0, vw - 90.0), tagAt.dy.clamp(24.0, vh - 40.0), it.text, fs, 1.0, 0.45);
      }
      return;
    }

    const headR = 370.0;
    final start = Offset(at.dx, at.dy + 56.0 * s);
    if (frame < _IntroT.shrink) {
      final g = (frame - _IntroT.antic).clamp(0, 1);
      final sx = g == 0 ? 1.08 : 0.94;
      final sy = g == 0 ? 0.88 : 1.12;
      final dy = g == 0 ? 24.0 : -30.0;
      _paintGrabbed(
        canvas,
        s,
        start.dx,
        start.dy + dy * s,
        kHold * 0.9,
        sx: sx,
        sy: sy,
        look: look,
        clipPath: _cutHead(headR, frame),
      );
      return;
    }

    if (frame < _IntroT.land) {
      final u = ((t - _IntroT.shrink + 1.0) / (_IntroT.land - _IntroT.shrink)).clamp(0.0, 1.0);
      const k0 = kHold * 0.9;
      final k1 = (it.size * 1.5) / (_GrabGeom.faceSize * s);

      ({Offset pos, double k}) place(double v) {
        final e = v * v;
        final a = (1.0 - e) * (1.0 - e);
        final c2 = 2.0 * e * (1.0 - e);
        final c = e * e;
        return (
          pos: Offset(
            a * start.dx + c2 * ctrl.dx + c * to.dx,
            a * start.dy + c2 * ctrl.dy + c * to.dy,
          ),
          k: ui.lerpDouble(k0, k1, 1.0 - (1.0 - v) * (1.0 - v))!,
        );
      }

      final trail = <Offset>[];
      for (int j = 0; j <= 10; j++) {
        final q = place(math.max(0.0, u - 0.45 + (j / 10.0) * 0.45));
        final jitterX = (j % 2 == 1 ? 1.0 : -1.0) * (3.0 + _hash(j, frame) * 6.0);
        trail.add(Offset(q.pos.dx + jitterX, q.pos.dy));
      }
      _strokePolyline(canvas, trail, CapriFxColors.violet, 4.5, -2.5, 2.5);
      _strokePolyline(canvas, trail, CapriFxColors.red, 3.5);
      _strokePolyline(canvas, trail, CapriFxColors.paper, 1.2);

      final headClip = _cutHead(headR, frame);
      final q = place(u);
      _paintGrabbed(
        canvas,
        s,
        q.pos.dx,
        q.pos.dy,
        q.k,
        look: Offset(towardX * 10.0, towardY * 7.0),
        clipPath: headClip,
      );
      return;
    }

    final g = frame - _IntroT.land;
    if (g < 2) {
      final w = it.size * (g == 0 ? 0.4 : 0.1);
      final h = it.size * 1.5;
      canvas.drawRect(Rect.fromCenter(center: to, width: w + 6, height: h), Paint()..color = CapriFxColors.violet);
      canvas.drawRect(Rect.fromCenter(center: to, width: w, height: h), Paint()..color = CapriFxColors.ink);
      canvas.drawRect(Rect.fromCenter(center: to, width: 2.0, height: h * 0.84), Paint()..color = CapriFxColors.red);
    }
  }

  void _paintGrabbed(
    Canvas canvas,
    double s,
    double x,
    double y,
    double k, {
    double rot = 0.0,
    double sx = 1.0,
    double sy = 1.0,
    Color? flatColor,
    Offset look = Offset.zero,
    double open = 1.0,
    Path? clipPath,
    String cel = 'grab',
  }) {
    final img = grabFrames[cel] ?? grabFrames['grab'];
    if (img == null) return;

    canvas.save();
    canvas.translate(x, y);
    if (rot != 0.0) canvas.rotate(rot);
    canvas.scale(s * k * sx, s * k * sy);
    canvas.translate(-_GrabGeom.face.dx, -_GrabGeom.face.dy);

    if (clipPath != null) {
      canvas.clipPath(clipPath);
    }

    // 1. Melena poligonal roja detrás del personaje (`GRAB.mane`)
    final manePath = Path();
    for (int i = 0; i < _GrabGeom.mane.length; i++) {
      final pt = _GrabGeom.mane[i];
      if (i == 0) {
        manePath.moveTo(pt[0], pt[1]);
      } else {
        manePath.lineTo(pt[0], pt[1]);
      }
    }
    manePath.close();
    canvas.drawPath(
      manePath,
      Paint()..color = flatColor ?? CapriFxColors.maneRed,
    );

    // 2. Imagen close-up (`intro-<cel>.webp`)
    final paint = Paint()..filterQuality = FilterQuality.medium;
    if (flatColor != null) {
      paint.colorFilter = ColorFilter.mode(flatColor, BlendMode.srcIn);
    }
    canvas.drawImage(img, Offset.zero, paint);

    // 3. Ojos animados encima de la imagen (salvo en 'happy' donde están cerrados de alegría)
    if (flatColor == null && cel != 'happy') {
      for (final e in _GrabGeom.eyes) {
        _paintGrabEye(canvas, e, look, open);
      }
    }

    // 4. Punta del mechón superior (`GRAB.lock`)
    final lockPath = Path();
    for (int i = 0; i < _GrabGeom.lock.length; i++) {
      final pt = _GrabGeom.lock[i];
      if (i == 0) {
        lockPath.moveTo(pt[0], pt[1]);
      } else {
        lockPath.lineTo(pt[0], pt[1]);
      }
    }
    lockPath.close();
    canvas.drawPath(lockPath, Paint()..color = flatColor ?? CapriFxColors.grabInk);

    canvas.restore();
  }

  void _paintGrabEye(Canvas canvas, Offset e, Offset look, double open) {
    canvas.save();
    final socketPath = Path()..addOval(Rect.fromCircle(center: e, radius: _GrabGeom.socket));
    canvas.drawPath(socketPath, Paint()..color = CapriFxColors.grabInk);
    canvas.clipPath(socketPath);

    if (open > 0.0) {
      canvas.drawCircle(e + look, _GrabGeom.iris, Paint()..color = CapriFxColors.grabIris);
      canvas.drawCircle(e + look * 1.15, _GrabGeom.pupil + 1.6, Paint()..color = CapriFxColors.grabInk);
      canvas.drawCircle(e + look * 1.15, _GrabGeom.pupil, Paint()..color = CapriFxColors.grabPupil);
    }
    if (open < 1.0) {
      canvas.translate(e.dx, e.dy);
      canvas.rotate(_GrabGeom.tilt);
      final edge = open > 0.0 ? -_GrabGeom.socket * 0.1 : _GrabGeom.socket * 0.15;
      canvas.drawRect(
        Rect.fromLTWH(-_GrabGeom.socket, -_GrabGeom.socket, _GrabGeom.socket * 2, _GrabGeom.socket + edge),
        Paint()..color = CapriFxColors.grabInk,
      );
      final lidPath = Path()
        ..moveTo(-_GrabGeom.socket, edge - 6)
        ..quadraticBezierTo(0, edge + 10, _GrabGeom.socket, edge - 6);
      canvas.drawPath(
        lidPath,
        Paint()
          ..color = CapriFxColors.green
          ..style = PaintingStyle.stroke
          ..strokeWidth = 6.0,
      );
    }
    canvas.restore();
  }

  void _paintHiTag(Canvas canvas, double x, double y, String text, double fs, double k, double ky) {
    final skew = fs * 0.32;
    final th = fs * 1.18;
    final tw = text.length * fs * 0.62 + fs * 0.9 + skew;

    Path band(double dx, double dy) {
      return Path()
        ..moveTo(skew + dx, -th / 2 + dy)
        ..lineTo(tw + dx, -th / 2 + dy)
        ..lineTo(tw - skew + dx, th / 2 + dy)
        ..lineTo(dx, th / 2 + dy)
        ..close();
    }

    canvas.save();
    canvas.translate(x, y);
    canvas.scale(k, k * ky);
    canvas.drawPath(band(5.0, 5.0), Paint()..color = CapriFxColors.violet);
    canvas.drawPath(band(0.0, 0.0), Paint()..color = CapriFxColors.red);

    final tp = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(
          color: CapriFxColors.paper,
          fontSize: fs,
          fontWeight: FontWeight.w700,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, Offset((tw - tp.width) / 2.0, -tp.height / 2.0));
    canvas.restore();
  }

  void _paintScreenEdges(Canvas canvas, double w, double h, int seed) {
    int idx = 0;
    double r(double a, double b) => a + _hash(idx++, seed) * (b - a);
    void runs(bool horizontal, double fixed, double len) {
      for (double p = r(-40, 0); p < len; p += r(55, 160)) {
        final l = r(35, 120);
        final t = r(3, 7);
        final rect = horizontal ? Rect.fromLTWH(p, fixed, l, t) : Rect.fromLTWH(fixed, p, t, l);
        canvas.drawRect(rect.shift(const Offset(2, 2)), Paint()..color = CapriFxColors.violet);
        canvas.drawRect(rect, Paint()..color = CapriFxColors.red);
      }
    }

    runs(true, 0, w);
    runs(true, h - 7, w);
    runs(false, 0, h);
    runs(false, w - 7, h);
  }

  Path _cutEdges(double rL, double rR, int seed) {
    const jag = 70.0;
    const jagAmp = 46.0;
    final path = Path();

    void addSide(double r, bool left) {
      if (r <= 0.0) return;
      final reach = r * _GrabGeom.w * 0.5;
      final amp = jagAmp * math.min(1.0, r * 4.0);
      path.moveTo(left ? -60.0 : _GrabGeom.w + 60.0, -60.0);
      int i = 0;
      for (double y = -60.0; y <= _GrabGeom.h + 60.0 + jag; y += jag, i++) {
        final x = reach + (_hash(i, seed + (left ? 0 : 50)) - 0.5) * 2.0 * amp;
        path.lineTo(left ? x : _GrabGeom.w - x, y);
      }
      path.lineTo(left ? -60.0 : _GrabGeom.w + 60.0, _GrabGeom.h + 60.0 + jag);
      path.close();
    }

    addSide(rL, true);
    addSide(rR, false);
    return path;
  }

  Path _cutBand(double half, int seed) {
    const jag = 70.0;
    const jagAmp = 46.0;
    final cx = _GrabGeom.face.dx;
    final ys = <double>[];
    for (double y = -60.0; y <= _GrabGeom.h + 60.0 + jag; y += jag) {
      ys.add(y);
    }
    final path = Path();
    for (int i = 0; i < ys.length; i++) {
      final x = cx - half - (_hash(i, seed) - 0.5) * 2.0 * jagAmp;
      if (i == 0) {
        path.moveTo(x, ys[i]);
      } else {
        path.lineTo(x, ys[i]);
      }
    }
    for (int i = ys.length - 1; i >= 0; i--) {
      final x = cx + half + (_hash(i, seed + 50) - 0.5) * 2.0 * jagAmp;
      path.lineTo(x, ys[i]);
    }
    path.close();
    return path;
  }

  Path _cutHead(double radius, int seed) {
    const n = 30;
    final path = Path();
    for (int i = 0; i < n; i++) {
      final a = (i / n) * math.pi * 2;
      final r = radius * (i % 2 == 1 ? 0.78 : 1.0) * (0.92 + _hash(i, seed) * 0.16);
      final x = _GrabGeom.face.dx + math.cos(a) * r * 1.15;
      final y = _GrabGeom.face.dy + math.sin(a) * r * 0.95;
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    path.close();
    return path;
  }
}

