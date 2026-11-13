// Cyberpunk neon glitch door menu ported from Capri-cmd/capri-ai
// (capri/desk/doormenu.py and assets/desk/door/).
// Art by xilia_world00 (Discord).

import 'dart:async';
import 'dart:math' as math;
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:window_manager/window_manager.dart';
import '../../core/audio/capri_sfx.dart';
import '../../core/utils/sprite_sheet_loader.dart';
import '../../domain/entities/assistant_state.dart';
import '../../domain/state/assistant_controller.dart';
import '../animation/capri_desk_sprites.dart';

class _DoorMenuEntry {
  final String label;
  final bool? checked;
  final bool isSubmenu;
  final bool isBack;
  final Color? textColor;
  final VoidCallback onTap;

  const _DoorMenuEntry({
    required this.label,
    required this.onTap,
    this.checked,
    this.isSubmenu = false,
    this.isBack = false,
    this.textColor,
  });
}

/// Caché estático de los 22 frames de apertura (`intro/1..22.png`) y 9 frames de loop (`idle/1..9.png`).
class DoorMenuAssets {
  static final List<ui.Image> introFrames = [];
  static final List<ui.Image> idleFrames = [];
  static bool _loaded = false;
  static bool _loading = false;

  static Future<void> ensureLoaded() async {
    if (_loaded || _loading) return;
    _loading = true;
    for (int i = 1; i <= 22; i++) {
      final img = await SpriteSheetLoader.load('assets/desk/door/intro/$i.png');
      if (img != null) introFrames.add(img);
    }
    for (int i = 1; i <= 9; i++) {
      final img = await SpriteSheetLoader.load('assets/desk/door/idle/$i.png');
      if (img != null) idleFrames.add(img);
    }
    _loaded = introFrames.isNotEmpty && idleFrames.isNotEmpty;
    _loading = false;
  }
}

/// Widget interactivo de la Puerta Cyberpunk (`capri/desk/doormenu.py`).
/// Se abre con `intro/1..22.png` (19 FPS) + `door_open.wav`, cicla en `idle/1..9.png` (10 FPS),
/// navega submenús con un glitch de 180ms (`TEAR`), y se cierra reproduciendo `intro` al revés (22 FPS) + `door_close.wav`.
class CyberpunkDoorMenu extends StatefulWidget {
  final AssistantController controller;
  final VoidCallback onClosed;

  const CyberpunkDoorMenu({
    super.key,
    required this.controller,
    required this.onClosed,
  });

  @override
  State<CyberpunkDoorMenu> createState() => _CyberpunkDoorMenuState();
}

class _CyberpunkDoorMenuState extends State<CyberpunkDoorMenu> {
  static const Rect _cropRect = Rect.fromLTWH(90, 0, 476, 640);
  static const Rect _insideRect = Rect.fromLTWH(117, 61, 240, 536);
  static const int _menuAtFrame = 11;

  static const Color _pink = Color(0xFFFF1E6E);
  static const Color _cyan = Color(0xFF78FAFF);
  static const Color _mint = Color(0xFF34F5A0);
  static const Color _yellow = Color(0xFFFFD15C);
  static const Color _white = Color(0xFFF6F0FA);
  static const Color _dim = Color(0xFF9682AA);

  String _phase = 'in'; // 'in' | 'open' | 'out'
  int _frameIndex = 0;
  String _currentPage = 'root'; // 'root' | 'skins' | 'posture' | 'states' | 'net'
  int _hoverIndex = -1;
  DateTime _lastTearAt = DateTime.fromMillisecondsSinceEpoch(0);
  Timer? _timer;
  VoidCallback? _pendingActionOnClose;

  @override
  void initState() {
    super.initState();
    CapriSfx.instance.play('door_open');
    _initDoor();
  }

  Future<void> _initDoor() async {
    await DoorMenuAssets.ensureLoaded();
    if (!mounted) return;
    _startPhase('in');
  }

  void _startPhase(String phase) {
    _timer?.cancel();
    _phase = phase;
    if (phase != 'out') {
      _frameIndex = 0;
    }
    final int fps = phase == 'in' ? 19 : (phase == 'open' ? 10 : 22);
    _timer = Timer.periodic(Duration(milliseconds: (1000 / fps).round()), (_) => _onTick());
    if (mounted) setState(() {});
  }

  void _onTick() {
    if (!mounted) return;
    final int len = _phase == 'open'
        ? math.max(1, DoorMenuAssets.idleFrames.length)
        : math.max(1, DoorMenuAssets.introFrames.length);

    if (_frameIndex + 1 < len) {
      setState(() {
        _frameIndex++;
      });
    } else if (_phase == 'in') {
      _startPhase('open');
    } else if (_phase == 'open') {
      setState(() {
        _frameIndex = 0;
      });
    } else {
      // Fin de 'out'
      _timer?.cancel();
      final action = _pendingActionOnClose;
      widget.onClosed();
      action?.call();
    }
  }

  void closeDoor({VoidCallback? afterClose}) {
    if (_phase == 'out') return;
    _pendingActionOnClose = afterClose;
    final introLen = math.max(1, DoorMenuAssets.introFrames.length);
    final at = _phase == 'in' ? _frameIndex : introLen - 1;
    _frameIndex = (introLen - 1 - at).clamp(0, introLen - 1);
    CapriSfx.instance.play('door_close');
    _startPhase('out');
  }

  void _navigatePage(String page) {
    CapriSfx.instance.play('key');
    setState(() {
      _currentPage = page;
      _hoverIndex = -1;
      _lastTearAt = DateTime.now();
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  List<_DoorMenuEntry> _buildEntries() {
    final c = widget.controller;

    switch (_currentPage) {
      case 'lookout':
        return [
          _DoorMenuEntry(
            label: 'Volver',
            isBack: true,
            onTap: () => _navigatePage('root'),
          ),
          _DoorMenuEntry(
            label: 'Vigilar: Fin Descarga',
            textColor: _mint,
            onTap: () {
              c.addLookoutWatch('avísame cuando termine la descarga');
              closeDoor();
            },
          ),
          _DoorMenuEntry(
            label: 'Vigilar: Salud Baja',
            textColor: _pink,
            onTap: () {
              c.addLookoutWatch('avísame si mi salud baja de la mitad', repeat: true);
              closeDoor();
            },
          ),
          _DoorMenuEntry(
            label: 'Vigilar: Render/Build',
            textColor: _cyan,
            onTap: () {
              c.addLookoutWatch('avísame cuando termine el render o la compilación');
              closeDoor();
            },
          ),
          _DoorMenuEntry(
            label: 'Detener Vigilante',
            onTap: () {
              c.stopLookoutWatch('');
              closeDoor();
            },
          ),
          if (c.activeWatches.isNotEmpty)
            ...c.activeWatches.map((w) => _DoorMenuEntry(
                  label: '#${w['id']}: ${w['text']}',
                  textColor: _yellow,
                  onTap: () {
                    c.stopLookoutWatch('${w['id']}');
                    closeDoor();
                  },
                )),
        ];

      case 'reminders':
        return [
          _DoorMenuEntry(
            label: 'Volver',
            isBack: true,
            onTap: () => _navigatePage('root'),
          ),
          _DoorMenuEntry(
            label: 'Temporizador 5 min',
            textColor: _mint,
            onTap: () {
              c.addDatedReminder('en 5 minutos temporizador');
              closeDoor();
            },
          ),
          _DoorMenuEntry(
            label: 'Temporizador 15 min',
            textColor: _cyan,
            onTap: () {
              c.addDatedReminder('en 15 minutos');
              closeDoor();
            },
          ),
          _DoorMenuEntry(
            label: 'Temporizador 30 min',
            onTap: () {
              c.addDatedReminder('en 30 minutos');
              closeDoor();
            },
          ),
          _DoorMenuEntry(
            label: 'Mañana a las 9:00',
            textColor: _yellow,
            onTap: () {
              c.addDatedReminder('mañana a las 9am');
              closeDoor();
            },
          ),
          _DoorMenuEntry(
            label: 'Cancelar Todos',
            onTap: () {
              c.cancelDatedReminder('');
              closeDoor();
            },
          ),
          if (c.pendingReminders.isNotEmpty)
            ...c.pendingReminders.map((r) => _DoorMenuEntry(
                  label: '#${r['id']} (${r['due']}): ${r['text']}',
                  textColor: _mint,
                  onTap: () {
                    c.cancelDatedReminder('${r['id']}');
                    closeDoor();
                  },
                )),
        ];

      case 'clones':
        return [
          _DoorMenuEntry(
            label: 'Volver',
            isBack: true,
            onTap: () => _navigatePage('root'),
          ),
          _DoorMenuEntry(
            label: 'Holograma (Clicks)',
            checked: c.isHologramEnabled,
            textColor: _cyan,
            onTap: () {
              c.toggleHologram();
              setState(() {});
            },
          ),
          _DoorMenuEntry(
            label: 'Invocar 3 Clones',
            textColor: _mint,
            onTap: () {
              c.spawnClones(3);
              closeDoor();
            },
          ),
          _DoorMenuEntry(
            label: 'Invocar 5 Clones',
            textColor: _yellow,
            onTap: () {
              c.spawnClones(5);
              closeDoor();
            },
          ),
          _DoorMenuEntry(
            label: 'Desvanecer Clones (Esc)',
            textColor: _pink,
            onTap: () {
              c.clearClones();
              closeDoor();
            },
          ),
        ];

      case 'skins':
        return [
          _DoorMenuEntry(
            label: 'Volver',
            isBack: true,
            onTap: () => _navigatePage('root'),
          ),
          ...CapriVisualSkin.values.map((skin) {
            return _DoorMenuEntry(
              label: skin.label,
              checked: c.currentSkin == skin,
              onTap: () {
                c.setSkin(skin);
                closeDoor();
              },
            );
          }),
        ];

      case 'posture':
        return [
          _DoorMenuEntry(
            label: 'Volver',
            isBack: true,
            onTap: () => _navigatePage('root'),
          ),
          ...CapriPosture.values.map((pos) {
            return _DoorMenuEntry(
              label: pos.label,
              checked: c.currentPosture == pos,
              onTap: () {
                c.setPosture(pos);
                closeDoor();
              },
            );
          }),
          _DoorMenuEntry(
            label: 'Saltar a Ventana',
            textColor: _cyan,
            onTap: () => closeDoor(afterClose: c.requestPerchOnWindow),
          ),
        ];

      case 'music':
        return [
          _DoorMenuEntry(
            label: 'Volver',
            isBack: true,
            onTap: () => _navigatePage('root'),
          ),
          _DoorMenuEntry(
            label: 'Mini Player',
            checked: c.isMiniPlayerOpen,
            onTap: () {
              c.toggleMiniPlayer();
              setState(() {});
            },
          ),
          _DoorMenuEntry(
            label: 'Bailar al Ritmo',
            checked: c.isDancing,
            onTap: () {
              c.toggleDancing();
              setState(() {});
            },
          ),
          _DoorMenuEntry(
            label: 'Play / Pause PC',
            onTap: () {
              c.sendMediaCommand('toggle');
              closeDoor();
            },
          ),
          _DoorMenuEntry(
            label: 'Siguiente Pista',
            onTap: () {
              c.sendMediaCommand('next');
              closeDoor();
            },
          ),
          _DoorMenuEntry(
            label: 'Radio Night City',
            textColor: _cyan,
            onTap: () => closeDoor(
              afterClose: () => c.sendUserMessage('pon música'),
            ),
          ),
        ];

      case 'games':
        return [
          _DoorMenuEntry(
            label: 'Volver',
            isBack: true,
            onTap: () => _navigatePage('root'),
          ),
          _DoorMenuEntry(
            label: 'Tres en Raya',
            onTap: () => closeDoor(afterClose: () => c.openMiniGame('tic_tac_toe')),
          ),
          _DoorMenuEntry(
            label: 'Conecta 4',
            onTap: () => closeDoor(afterClose: () => c.openMiniGame('connect_four')),
          ),
          _DoorMenuEntry(
            label: 'Piedra Papel Tijera',
            onTap: () => closeDoor(afterClose: () => c.openMiniGame('rock_paper_scissors')),
          ),
          _DoorMenuEntry(
            label: 'GameSense (Vigilar)',
            checked: c.isGameSenseEnabled,
            onTap: () {
              c.toggleGameSense();
              closeDoor();
            },
          ),
          _DoorMenuEntry(
            label: 'Piloto: Explorar',
            textColor: _mint,
            onTap: () => closeDoor(afterClose: () => c.triggerGameAutopilot('explore')),
          ),
          _DoorMenuEntry(
            label: 'Piloto: Combate',
            textColor: _pink,
            onTap: () => closeDoor(afterClose: () => c.triggerGameAutopilot('combat')),
          ),
          _DoorMenuEntry(
            label: 'Detener Piloto',
            textColor: _cyan,
            onTap: () => closeDoor(afterClose: () => c.triggerGameAutopilot('stop')),
          ),
        ];

      case 'states':
        return [
          _DoorMenuEntry(
            label: 'Volver',
            isBack: true,
            onTap: () => _navigatePage('root'),
          ),
          ...AssistantState.values.map((st) {
            return _DoorMenuEntry(
              label: st.name.toUpperCase(),
              checked: c.currentState == st,
              onTap: () {
                c.changeState(st, notifyBackend: true, force: true);
                closeDoor();
              },
            );
          }),
        ];

      case 'net':
        final connected = c.wsStatus.name == 'connected';
        return [
          _DoorMenuEntry(
            label: 'Volver',
            isBack: true,
            onTap: () => _navigatePage('root'),
          ),
          _DoorMenuEntry(
            label: connected ? 'WS: CONECTADO' : 'WS: OFFLINE',
            textColor: connected ? _mint : _pink,
            onTap: () {},
          ),
          _DoorMenuEntry(
            label: 'Reconectar WS',
            onTap: () {
              c.reconnectWebSocket();
              closeDoor();
            },
          ),
          _DoorMenuEntry(
            label: 'Disparar Intro',
            onTap: () {
              c.changeState(AssistantState.intro, notifyBackend: true, force: true);
              closeDoor();
            },
          ),
        ];

      case 'root':
      default:
        return [
          _DoorMenuEntry(
            label: c.isListeningMic ? '🎤 Escuchando...' : '🎤 Hablar por Voz',
            textColor: _mint,
            checked: c.isListeningMic,
            onTap: () => closeDoor(afterClose: c.toggleVoiceListen),
          ),
          _DoorMenuEntry(
            label: 'Llamada Continua',
            textColor: _cyan,
            checked: c.isContinuousVoiceCall,
            onTap: () {
              c.toggleContinuousVoiceCall();
              closeDoor();
            },
          ),
          _DoorMenuEntry(
            label: 'Voz Hablada (TTS)',
            checked: c.isTtsEnabled,
            onTap: () {
              c.toggleTtsVoice();
              setState(() {});
            },
          ),
          _DoorMenuEntry(
            label: 'Escribir a Capri',
            onTap: () => closeDoor(afterClose: c.openChatBox),
          ),
          _DoorMenuEntry(
            label: 'Cerebro IA (Brain)',
            textColor: _cyan,
            checked: c.brainStatus.isLiveBrainActive,
            onTap: () => closeDoor(afterClose: c.toggleBrainPanel),
          ),
          _DoorMenuEntry(
            label: 'Mirar mi Pantalla',
            textColor: _mint,
            onTap: () => closeDoor(afterClose: c.requestScreenGlance),
          ),
          _DoorMenuEntry(
            label: '👁️ Vigilar Pantalla',
            isSubmenu: true,
            textColor: _cyan,
            onTap: () => _navigatePage('lookout'),
          ),
          _DoorMenuEntry(
            label: '⏰ Recordatorios',
            isSubmenu: true,
            textColor: _yellow,
            onTap: () => _navigatePage('reminders'),
          ),
          _DoorMenuEntry(
            label: '👯 Clones y Holograma',
            isSubmenu: true,
            textColor: _mint,
            onTap: () => _navigatePage('clones'),
          ),
          _DoorMenuEntry(
            label: 'Jugar con Capri',
            isSubmenu: true,
            textColor: _mint,
            onTap: () => _navigatePage('games'),
          ),
          _DoorMenuEntry(
            label: 'Música / Baile',
            isSubmenu: true,
            textColor: _cyan,
            onTap: () => _navigatePage('music'),
          ),
          _DoorMenuEntry(
            label: 'Modo Mini',
            checked: c.isMiniMode,
            onTap: () {
              c.toggleMiniMode();
              setState(() {});
            },
          ),
          _DoorMenuEntry(
            label: 'Postura / Ventana',
            isSubmenu: true,
            onTap: () => _navigatePage('posture'),
          ),
          _DoorMenuEntry(
            label: 'Skins',
            isSubmenu: true,
            onTap: () => _navigatePage('skins'),
          ),
          _DoorMenuEntry(
            label: 'Animaciones',
            isSubmenu: true,
            onTap: () => _navigatePage('states'),
          ),
          _DoorMenuEntry(
            label: 'Silenciar SFX',
            checked: c.isMuted,
            onTap: () {
              c.toggleMute();
              setState(() {});
            },
          ),
          _DoorMenuEntry(
            label: 'Red / Estado',
            isSubmenu: true,
            onTap: () => _navigatePage('net'),
          ),
          _DoorMenuEntry(
            label: 'Salir',
            textColor: _pink,
            onTap: () => closeDoor(afterClose: () => windowManager.close()),
          ),
        ];
    }
  }

  ui.Image? _currentDoorImage() {
    if (_phase == 'open') {
      if (DoorMenuAssets.idleFrames.isEmpty) return null;
      return DoorMenuAssets.idleFrames[_frameIndex % DoorMenuAssets.idleFrames.length];
    }
    if (DoorMenuAssets.introFrames.isEmpty) return null;
    if (_phase == 'in') {
      return DoorMenuAssets.introFrames[_frameIndex.clamp(0, DoorMenuAssets.introFrames.length - 1)];
    }
    // 'out' reproduce intro al revés
    final revIdx = (DoorMenuAssets.introFrames.length - 1 - _frameIndex)
        .clamp(0, DoorMenuAssets.introFrames.length - 1);
    return DoorMenuAssets.introFrames[revIdx];
  }

  bool get _showMenuText {
    if (_phase == 'open') return true;
    if (_phase == 'in') return _frameIndex >= _menuAtFrame;
    if (_phase == 'out') {
      final revIdx = DoorMenuAssets.introFrames.length - 1 - _frameIndex;
      return revIdx >= _menuAtFrame;
    }
    return false;
  }

  @override
  Widget build(BuildContext context) {
    final entries = _buildEntries();
    final doorImg = _currentDoorImage();
    final tearElapsed = DateTime.now().difference(_lastTearAt).inMilliseconds / 1000.0;
    final tearProgress = tearElapsed < 0.18 ? (1.0 - tearElapsed / 0.18) : 0.0;

    return GestureDetector(
      behavior: HitTestBehavior.translucent,
      onTap: closeDoor,
      onSecondaryTap: closeDoor,
      child: SizedBox.expand(
        child: Center(
          child: GestureDetector(
            onTap: () {}, // Absorber clics dentro de la puerta
            child: SizedBox(
              width: 245,
              height: 345,
              child: Stack(
                children: [
                  // 1. Arte de la Puerta Cyberpunk (`assets/desk/door/`)
                  Positioned.fill(
                    child: CustomPaint(
                      painter: _DoorFramePainter(
                        image: doorImg,
                        cropRect: _cropRect,
                        insideRect: _insideRect,
                        tearProgress: tearProgress,
                      ),
                    ),
                  ),

                  // 2. Filas interactivas dentro del área oscura de la puerta (`INSIDE`)
                  if (_showMenuText)
                    Positioned(
                      left: (_insideRect.left / _cropRect.width) * 245 + 6,
                      top: (_insideRect.top / _cropRect.height) * 345 + 8,
                      width: (_insideRect.width / _cropRect.width) * 245 - 12,
                      height: (_insideRect.height / _cropRect.height) * 345 - 16,
                      child: Center(
                        child: SingleChildScrollView(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: List.generate(entries.length, (idx) {
                              final item = entries[idx];
                              final hovered = _hoverIndex == idx;
                              final fg = hovered
                                  ? _white
                                  : (item.isBack ? _cyan : (item.textColor ?? _white));

                              return MouseRegion(
                                cursor: SystemMouseCursors.click,
                                onEnter: (_) => setState(() => _hoverIndex = idx),
                                onExit: (_) {
                                  if (_hoverIndex == idx) {
                                    setState(() => _hoverIndex = -1);
                                  }
                                },
                                child: GestureDetector(
                                  behavior: HitTestBehavior.opaque,
                                  onTap: item.onTap,
                                  child: Container(
                                    height: 24,
                                    margin: const EdgeInsets.symmetric(vertical: 1),
                                    padding: const EdgeInsets.symmetric(horizontal: 5),
                                    decoration: hovered
                                        ? BoxDecoration(
                                            color: _pink.withValues(alpha: 0.48),
                                            border: const Border(
                                              left: BorderSide(color: _cyan, width: 2.5),
                                            ),
                                          )
                                        : null,
                                    child: Row(
                                      children: [
                                        // Indicador izquierdo: Back `‹`, Checkbox `[✓]`, o vacío
                                        SizedBox(
                                          width: 16,
                                          child: item.isBack
                                              ? const Text(
                                                  '‹',
                                                  style: TextStyle(
                                                    fontFamily: 'ShareTechMono',
                                                    color: _cyan,
                                                    fontSize: 14,
                                                    fontWeight: FontWeight.bold,
                                                  ),
                                                )
                                              : item.checked != null
                                                  ? Container(
                                                      width: 10,
                                                      height: 10,
                                                      decoration: BoxDecoration(
                                                        color: item.checked!
                                                            ? _mint
                                                            : Colors.transparent,
                                                        border: Border.all(
                                                          color: item.checked!
                                                              ? _mint
                                                              : (hovered ? _white : _dim),
                                                          width: 1.3,
                                                        ),
                                                      ),
                                                    )
                                                  : null,
                                        ),
                                        Expanded(
                                          child: Text(
                                            item.label,
                                            maxLines: 1,
                                            overflow: TextOverflow.ellipsis,
                                            style: TextStyle(
                                              fontFamily: 'ShareTechMono',
                                              color: fg,
                                              fontSize: 12.5,
                                              fontWeight: hovered
                                                  ? FontWeight.bold
                                                  : FontWeight.w500,
                                              letterSpacing: 0.3,
                                            ),
                                          ),
                                        ),
                                        if (item.isSubmenu)
                                          Text(
                                            '›',
                                            style: TextStyle(
                                              fontFamily: 'ShareTechMono',
                                              color: hovered ? _cyan : _pink,
                                              fontSize: 14,
                                              fontWeight: FontWeight.bold,
                                            ),
                                          ),
                                      ],
                                    ),
                                  ),
                                ),
                              );
                            }),
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _DoorFramePainter extends CustomPainter {
  final ui.Image? image;
  final Rect cropRect;
  final Rect insideRect;
  final double tearProgress;

  _DoorFramePainter({
    required this.image,
    required this.cropRect,
    required this.insideRect,
    required this.tearProgress,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (image != null) {
      canvas.drawImageRect(
        image!,
        cropRect,
        Offset.zero & size,
        Paint()..filterQuality = FilterQuality.medium,
      );
    } else {
      // Fallback neón mientras cargan los PNG de la puerta
      final r = Rect.fromLTWH(size.width * 0.18, size.height * 0.08, size.width * 0.64, size.height * 0.84);
      canvas.drawRect(r, Paint()..color = const Color(0xEB110A1E));
      canvas.drawRect(
        r,
        Paint()
          ..color = const Color(0xFFFF1E6E)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.0,
      );
    }

    // Glitch de cambio de página (`doormenu.py` `_tear`)
    if (tearProgress > 0.0) {
      final rng = math.Random();
      final sx = size.width / cropRect.width;
      final sy = size.height / cropRect.height;
      final inside = Rect.fromLTWH(
        insideRect.left * sx,
        insideRect.top * sy,
        insideRect.width * sx,
        insideRect.height * sy,
      );
      const shreds = [
        Color(0xFFFF1E6E),
        Color(0xFF78FAFF),
        Color(0xFF34F5A0),
        Color(0xFFFFFFFF),
      ];
      for (int i = 0; i < 6; i++) {
        final col = shreds[rng.nextInt(shreds.length)].withValues(alpha: 0.55 * tearProgress);
        final y = inside.top + rng.nextDouble() * inside.height;
        final w = (0.25 + rng.nextDouble() * 0.65) * inside.width;
        final x = inside.left + rng.nextDouble() * (inside.width - w);
        canvas.drawRect(Rect.fromLTWH(x, y, w, 2.5), Paint()..color = col);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _DoorFramePainter oldDelegate) {
    return oldDelegate.image != image || oldDelegate.tearProgress != tearProgress;
  }
}

