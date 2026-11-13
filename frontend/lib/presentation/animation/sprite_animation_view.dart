import 'dart:ui' as ui;
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import '../../core/constants/sprite_registry.dart';
import '../../core/utils/sprite_sheet_loader.dart';
import '../../domain/entities/assistant_state.dart';
import 'capri_desk_sprites.dart';
import 'capri_rig.dart';
import 'sprite_sheet_painter.dart';

/// Widget que coordina todas las capas visuales de Capri:
/// 1. Rig de cuerpo completo (`assets/capri/capri-full.png` + `shaders/capri.frag` + `CapriActs`).
/// 2. Hojas de sprites oficiales y skin secreta Watcher (`assets/desk/skins/`), pose arrastrada (`dangle.png`),
///    poses acostadas (`lay_*.png`) y Modo Mini Chibi (`assets/desk/mini/`).
/// 3. Capa de efectos 2D (`fx.js`: `cutin-*.png`, secuencia `intro-*.webp`, rayos, retícula con ojos, fragmentos y máscara flotante).
class SpriteAnimationView extends StatefulWidget {
  final AssistantState state;
  final CapriVisualSkin skin;
  final CapriPosture posture;
  final bool isMiniMode;
  final bool isDragging;
  final bool isDancing;
  final VoidCallback? onComplete;
  final VoidCallback? onMiniPoked;
  final VoidCallback? onHeadPatted;
  final double width;
  final double height;

  const SpriteAnimationView({
    super.key,
    required this.state,
    this.skin = CapriVisualSkin.shaderRig,
    this.posture = CapriPosture.standing,
    this.isMiniMode = false,
    this.isDragging = false,
    this.isDancing = false,
    this.onComplete,
    this.onMiniPoked,
    this.onHeadPatted,
    this.width = 211,
    this.height = 319,
  });

  @override
  State<SpriteAnimationView> createState() => SpriteAnimationViewState();
}

class SpriteAnimationViewState extends State<SpriteAnimationView>
    with SingleTickerProviderStateMixin {
  static ui.FragmentProgram? _cachedProgram;

  late final Ticker _ticker;
  final CapriRig _rig = CapriRig();
  final CapriDeskSprites _deskSprites = CapriDeskSprites();

  ui.FragmentShader? _shader;
  ui.Image? _baseImage;

  Duration _lastTick = Duration.zero;
  double _lastElapsedMs = 0.0;
  double _animationTick = 0.0;
  int _repaintGeneration = 0;

  Size get _canvasSize => Size(widget.width, widget.height);

  /// Registra un clic en modo Mini para detectar los 3 toques rápidos de enfado (`mini.py`).
  bool registerMiniTap() {
    final annoyed = _deskSprites.registerMiniPoke(_lastElapsedMs / 1000.0);
    if (annoyed) {
      widget.onMiniPoked?.call();
    }
    return annoyed;
  }

  /// Registra movimiento de cursor sobre la cabeza de Capri para detectar Head Pats (`Capri.cs` `petTurns`).
  void registerCursorHover(Offset localPosition) {
    final patted = _deskSprites.registerCursorRub(
      localPosition.dx,
      localPosition.dy,
      widget.height,
      _lastElapsedMs / 1000.0,
    );
    if (patted) {
      widget.onHeadPatted?.call();
    }
  }

  @override
  void initState() {
    super.initState();
    _rig.setAssistantState(widget.state, 0.0, canvasSize: _canvasSize);
    _rig.tick(0.0, canvasSize: _canvasSize);
    _loadAssets();
    _ticker = createTicker(_onTick)..start();
  }

  @override
  void didUpdateWidget(covariant SpriteAnimationView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.state != widget.state ||
        oldWidget.skin != widget.skin ||
        oldWidget.posture != widget.posture ||
        oldWidget.isMiniMode != widget.isMiniMode ||
        oldWidget.isDragging != widget.isDragging) {
      if (oldWidget.state != widget.state) {
        _rig.setAssistantState(widget.state, _lastElapsedMs, canvasSize: _canvasSize);
        _rig.tick(_lastElapsedMs + 100.0, canvasSize: _canvasSize);
      }
      _repaintGeneration++;
    }
  }

  Future<void> _loadAssets() async {
    final imageFuture = SpriteSheetLoader.load(SpriteRegistry.baseSpriteAsset);
    final shaderFuture = _loadShader();
    final fxFuture = _rig.fx.loadAssets();
    final deskFuture = _deskSprites.loadAll();

    final image = await imageFuture;
    final shader = await shaderFuture;
    await fxFuture;
    await deskFuture;

    if (mounted) {
      setState(() {
        _baseImage = image;
        _shader = shader;
        if (widget.state == AssistantState.intro) {
          _rig.setAssistantState(AssistantState.intro, _lastElapsedMs, canvasSize: _canvasSize);
        }
        _repaintGeneration++;
      });
    }
  }

  Future<ui.FragmentShader?> _loadShader() async {
    try {
      _cachedProgram ??= await ui.FragmentProgram.fromAsset(SpriteRegistry.shaderAsset);
      return _cachedProgram!.fragmentShader();
    } catch (e) {
      if (kDebugMode) {
        print('[SpriteAnimationView] No se pudo cargar el shader (${SpriteRegistry.shaderAsset}): $e');
      }
      return null;
    }
  }

  void _onTick(Duration elapsed) {
    final delta = elapsed - _lastTick;
    _lastTick = elapsed;

    _lastElapsedMs = elapsed.inMicroseconds / 1000.0;
    _animationTick = (_animationTick + delta.inMicroseconds / 1000000.0) % 10.0;

    final prevSeed = _rig.u.seed;
    final prevCollapse = _rig.u.collapse;
    final prevDissolve = _rig.u.dissolve;
    final prevGlitch = _rig.u.glitch;
    final prevAlpha = _rig.u.alpha;
    final prevSilAmount = _rig.u.silAmount;

    final completedOneShot = _rig.tick(_lastElapsedMs, canvasSize: _canvasSize);

    final useContinuousRepaint = widget.isMiniMode ||
        widget.isDragging ||
        widget.isDancing ||
        widget.posture == CapriPosture.lying ||
        widget.skin != CapriVisualSkin.shaderRig ||
        (_lastElapsedMs / 1000.0) < _deskSprites.petGlowUntilSec ||
        _rig.fx.hasActiveItems;

    final changed = useContinuousRepaint ||
        _rig.u.seed != prevSeed ||
        _rig.u.collapse != prevCollapse ||
        _rig.u.dissolve != prevDissolve ||
        _rig.u.glitch != prevGlitch ||
        _rig.u.alpha != prevAlpha ||
        _rig.u.silAmount != prevSilAmount ||
        _shader == null;

    if (changed && mounted) {
      setState(() {
        _repaintGeneration++;
      });
    }

    if (completedOneShot) {
      widget.onComplete?.call();
    }
  }

  @override
  void dispose() {
    _ticker.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final dpr = MediaQuery.maybeDevicePixelRatioOf(context) ?? 1.0;
    final showShaderFx = !widget.isMiniMode &&
        !widget.isDragging &&
        !widget.isDancing &&
        widget.posture != CapriPosture.lying &&
        widget.skin == CapriVisualSkin.shaderRig;

    return MouseRegion(
      onHover: (event) => registerCursorHover(event.localPosition),
      child: SizedBox(
        width: widget.width,
        height: widget.height,
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            // Capa 1: Shader Rig (`capri-full.png`), Hojas de Sprites (`skins/`), Dangle (`dangle.png`) o Mini Chibi (`mini/`)
            Positioned.fill(
              child: CustomPaint(
                size: Size(widget.width, widget.height),
                painter: SpriteSheetPainter(
                  shader: _shader,
                  image: _baseImage,
                  uniforms: _rig.u,
                  deskSprites: _deskSprites,
                  state: widget.state,
                  skin: widget.skin,
                  posture: widget.posture,
                  isMiniMode: widget.isMiniMode,
                  isDragging: widget.isDragging,
                  isDancing: widget.isDancing,
                  devicePixelRatio: dpr,
                  elapsedSeconds: _lastElapsedMs / 1000.0,
                  animationTick: _animationTick,
                  repaintGeneration: _repaintGeneration,
                ),
              ),
            ),

            // Capa 2: Efectos 2D (`cutin-*.png`, `intro-*.webp`, máscara flotante `Mask`, rayos y partículas)
            if (showShaderFx)
              Positioned.fill(
                child: IgnorePointer(
                  child: CustomPaint(
                    size: Size(widget.width, widget.height),
                    painter: CapriFxOverlayPainter(
                      fx: _rig.fx,
                      nowMs: _lastElapsedMs,
                      repaintGeneration: _repaintGeneration,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
