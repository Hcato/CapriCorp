import 'dart:math' as math;
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import '../../core/constants/app_constants.dart';
import '../../domain/entities/assistant_state.dart';
import 'capri_desk_sprites.dart';
import 'capri_fx.dart';
import 'capri_rig.dart';

/// Painter de alto rendimiento que renderiza a Capri combinando:
/// - El Fragment Shader GLSL (`shaders/capri.frag` + `assets/capri/capri-full.png`),
/// - Las hojas de sprites oficiales y la skin Watcher (`assets/desk/skins/`),
/// - La pose colgando al arrastrarla (`dangle.png`) y acostada (`lay_*.png`),
/// - Y el Modo Mini Chibi (`assets/desk/mini/`).
class SpriteSheetPainter extends CustomPainter {
  final ui.FragmentShader? shader;
  final ui.Image? image;
  final CapriUniforms uniforms;
  final CapriDeskSprites deskSprites;
  final AssistantState state;
  final CapriVisualSkin skin;
  final CapriPosture posture;
  final bool isMiniMode;
  final bool isDragging;
  final bool isDancing;
  final double devicePixelRatio;
  final double elapsedSeconds;
  final double animationTick;
  final int repaintGeneration;

  SpriteSheetPainter({
    required this.shader,
    required this.image,
    required this.uniforms,
    required this.deskSprites,
    required this.state,
    this.skin = CapriVisualSkin.shaderRig,
    this.posture = CapriPosture.standing,
    this.isMiniMode = false,
    this.isDragging = false,
    this.isDancing = false,
    this.devicePixelRatio = 1.0,
    this.elapsedSeconds = 0.0,
    this.animationTick = 0.0,
    this.repaintGeneration = 0,
  });

  @override
  void paint(Canvas canvas, Size size) {
    // 1. Modo Mini Chibi (`assets/desk/mini/`)
    if (isMiniMode && deskSprites.isLoaded) {
      final painted = deskSprites.paintMiniForm(
        canvas: canvas,
        size: size,
        state: state,
        skin: skin,
        posture: posture,
        isDancing: isDancing,
        nowSec: elapsedSeconds,
      );
      if (painted) return;
    }

    // 2. Si está siendo arrastrada (`dangle.png`), en postura acostada (`laydown*` / `lay_*.png`),
    //    bailando al ritmo de la música (`perch_music.png` / `dance.png`),
    //    o usando una de las skins de hojas de sprites (`capri` / `watcher`):
    final useDeskSprites = deskSprites.isLoaded &&
        (isDragging ||
            isDancing ||
            posture == CapriPosture.lying ||
            skin == CapriVisualSkin.capriSprites ||
            skin == CapriVisualSkin.watcherSprites);

    if (useDeskSprites) {
      final folder = skin == CapriVisualSkin.watcherSprites ? 'watcher' : 'capri';
      final painted = deskSprites.paintSkinSprite(
        canvas: canvas,
        size: size,
        skinFolder: folder,
        state: state,
        posture: posture,
        isDragging: isDragging,
        isDancing: isDancing,
        nowSec: elapsedSeconds,
      );
      if (painted) return;
    }

    // 3. Rig de cuerpo completo con Fragment Shader GLSL (`shaders/capri.frag`)
    if (uniforms.alpha <= 0.001) return;

    if (shader != null && image != null) {
      _paintShaderRig(canvas, size);
    } else if (image != null) {
      _paintStaticTextureFallback(canvas, size);
    } else {
      _paintProceduralCyberpunkAvatar(canvas, size);
    }
  }

  /// Ejecuta el Fragment Shader GLSL (`shaders/capri.frag`) con los 37 floats de [CapriUniforms].
  void _paintShaderRig(Canvas canvas, Size size) {
    final s = shader!;
    final u = uniforms;

    s.setFloat(0, size.width);
    s.setFloat(1, size.height);

    s.setFloat(2, u.seed);
    s.setFloat(3, u.boil);
    s.setFloat(4, u.hair);
    s.setFloat(5, u.head);
    s.setFloat(6, u.mane);
    s.setFloat(7, u.armL);
    s.setFloat(8, u.armR);
    s.setFloat(9, u.longL);
    s.setFloat(10, u.longR);
    s.setFloat(11, u.sit);
    s.setFloat(12, u.bend);
    s.setFloat(13, u.kickL);
    s.setFloat(14, u.kickR);

    s.setFloat(15, u.smearX);
    s.setFloat(16, u.smearY);

    s.setFloat(17, u.echoX);
    s.setFloat(18, u.echoY);

    s.setFloat(19, u.glitch);
    s.setFloat(20, u.glitchSeed);
    s.setFloat(21, u.split);
    s.setFloat(22, u.collapse);
    s.setFloat(23, u.dissolve);
    s.setFloat(24, u.sparkle);
    s.setFloat(25, u.grade);

    s.setFloat(26, u.silR);
    s.setFloat(27, u.silG);
    s.setFloat(28, u.silB);
    s.setFloat(29, u.silAmount);

    s.setFloat(30, u.misregX);
    s.setFloat(31, u.misregY);

    s.setFloat(32, u.rimR);
    s.setFloat(33, u.rimG);
    s.setFloat(34, u.rimB);

    s.setFloat(35, u.alpha);

    final double dpr = devicePixelRatio > 0 ? devicePixelRatio : 1.0;
    s.setFloat(36, 352.0 / math.max(1.0, size.width * dpr));

    s.setImageSampler(0, image!);

    final paint = Paint()..shader = s;
    canvas.drawRect(Offset.zero & size, paint);
  }

  void _paintStaticTextureFallback(Canvas canvas, Size size) {
    final rawW = image!.width.toDouble();
    final rawH = image!.height.toDouble();
    final srcRect = Rect.fromLTWH(0, 0, rawW, rawH);

    final scaleX = size.width / 352.0;
    final scaleY = size.height / 532.0;
    final dstRect = Rect.fromLTWH(
      59.0 * scaleX,
      62.0 * scaleY,
      235.0 * scaleX,
      462.0 * scaleY,
    );

    final paint = Paint()
      ..filterQuality = FilterQuality.medium
      ..isAntiAlias = true
      ..color = Color.fromRGBO(255, 255, 255, uniforms.alpha.clamp(0.0, 1.0));

    canvas.drawImageRect(image!, srcRect, dstRect, paint);
  }

  void _paintProceduralCyberpunkAvatar(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final floatY = math.sin(animationTick * math.pi * 2) * 5.0;
    final avatarCenter = center.translate(0, floatY);

    final auraPaint = Paint()
      ..color = AppConstants.neonCyan.withValues(alpha: 0.25)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 18);
    canvas.drawCircle(avatarCenter, size.width * 0.28, auraPaint);

    final corePaint = Paint()
      ..color = const Color(0xFF141824)
      ..style = PaintingStyle.fill;
    canvas.drawCircle(avatarCenter, size.width * 0.22, corePaint);

    final borderPaint = Paint()
      ..color = AppConstants.neonCyan
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.5;
    canvas.drawCircle(avatarCenter, size.width * 0.22, borderPaint);
  }

  @override
  bool shouldRepaint(covariant SpriteSheetPainter oldDelegate) {
    return oldDelegate.repaintGeneration != repaintGeneration ||
        oldDelegate.state != state ||
        oldDelegate.skin != skin ||
        oldDelegate.posture != posture ||
        oldDelegate.isMiniMode != isMiniMode ||
        oldDelegate.isDragging != isDragging ||
        oldDelegate.image != image ||
        oldDelegate.shader != shader;
  }
}

/// Painter de la capa superior de efectos 2D (`fx.js` y `chip.js` de `mochiiwuff/capri-desktop`).
class CapriFxOverlayPainter extends CustomPainter {
  final CapriFxLayer fx;
  final double nowMs;
  final int repaintGeneration;

  CapriFxOverlayPainter({
    required this.fx,
    required this.nowMs,
    required this.repaintGeneration,
  });

  @override
  void paint(Canvas canvas, Size size) {
    fx.paint(canvas, size, nowMs);
  }

  @override
  bool shouldRepaint(covariant CapriFxOverlayPainter oldDelegate) {
    return oldDelegate.repaintGeneration != repaintGeneration ||
        oldDelegate.nowMs != nowMs ||
        fx.hasActiveItems;
  }
}
