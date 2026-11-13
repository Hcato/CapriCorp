import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:window_manager/window_manager.dart';
import '../../core/constants/app_constants.dart';
import '../../domain/entities/assistant_state.dart';
import '../../domain/state/assistant_controller.dart';
import '../animation/sprite_animation_view.dart';
import '../widgets/capri_brain_panel.dart';
import '../widgets/capri_minigames_panel.dart';
import '../widgets/connection_badge.dart';
import '../widgets/cyberpunk_mini_player.dart';
import '../widgets/speech_bubble.dart';
import 'door_context_menu.dart';

/// Overlay interactivo principal de Capri sobre Windows 11.
/// Integra:
/// - Rig GLSL + Sprites de 60 FPS (`perch_music`, `perch_talk`, `laydown`, `dance`, `walk`) + Skin `Watcher` + Modo Mini Chibi,
/// - Detector de caricias (`Head Pats`) al frotar el cursor sobre su cabeza,
/// - Puerta Cyberpunk de menú contextual (`assets/desk/door/`),
/// - Burbuja estilo Videollamada (`bubble.py`),
/// - Cyberpunk Mini Music Player (`Player.cs`),
/// - Tablero de Minijuegos (`Minis.cs`: Tres en Raya, Conecta 4, Piedra Papel o Tijera).
class CharacterOverlay extends StatefulWidget {
  final AssistantController controller;

  const CharacterOverlay({
    super.key,
    required this.controller,
  });

  @override
  State<CharacterOverlay> createState() => _CharacterOverlayState();
}

class _CharacterOverlayState extends State<CharacterOverlay> {
  final GlobalKey<SpriteAnimationViewState> _animKey = GlobalKey<SpriteAnimationViewState>();

  AssistantController get controller => widget.controller;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final showBubble = controller.currentSpeechText != null ||
            controller.isChatOpen ||
            controller.isListeningMic ||
            controller.currentState == AssistantState.thinking ||
            controller.currentState == AssistantState.listening;

        return Focus(
          autofocus: true,
          onKeyEvent: (_, KeyEvent event) {
            if (event is KeyDownEvent && event.logicalKey == LogicalKeyboardKey.escape) {
              if (controller.activeClones.isNotEmpty) {
                controller.clearClones();
                return KeyEventResult.handled;
              }
            }
            return KeyEventResult.ignored;
          },
          child: Scaffold(
            backgroundColor: Colors.transparent,
            body: Stack(
              clipBehavior: Clip.none,
              children: [
                // Clones Swarm Overlay (Desktop Goose Capri - Clones.cs)
                if (controller.activeClones.isNotEmpty)
                  Positioned(
                    top: 4,
                    right: 8,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                      decoration: BoxDecoration(
                        color: const Color(0xDD110E18),
                        border: Border.all(color: const Color(0xFFFF1E6E), width: 1.0),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Text('👯 ', style: TextStyle(fontSize: 11)),
                          Text(
                            'CLONES x${controller.activeClones.length} (Pulsa Esc)',
                            style: const TextStyle(
                              color: Color(0xFF78FAFF),
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 0.5,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),

                if (controller.isHologramEnabled)
                  Positioned(
                    top: 24,
                    right: 8,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: const Color(0xCC003844),
                        border: Border.all(color: const Color(0xFF78FAFF), width: 1.0),
                      ),
                      child: const Text(
                        'HOLOGRAMA ACTIVO',
                        style: TextStyle(
                          color: Color(0xFF78FAFF),
                          fontSize: 9,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ),
                  ),

                // 1. Área interactiva del personaje con soporte Drag & Drop (`dangle.png`),
              //    Head Pats al mover el cursor sobre su cabeza, Clic para hablar y Clic Derecho (Puerta Cyberpunk)
              Align(
                alignment: const Alignment(0.0, 0.35),
                child: MouseRegion(
                  cursor: SystemMouseCursors.grab,
                  child: GestureDetector(
                    behavior: HitTestBehavior.translucent,
                    onTap: () {
                      if (controller.isMiniMode) {
                        final annoyed = _animKey.currentState?.registerMiniTap() ?? false;
                        if (!annoyed) {
                          controller.openChatBox();
                        }
                      } else {
                        controller.openChatBox();
                      }
                    },
                    onDoubleTap: () {
                      if (controller.isMiniMode) {
                        controller.setMiniMode(false);
                      } else {
                        controller.changeState(
                          AssistantState.teleporting,
                          notifyBackend: true,
                          force: true,
                        );
                      }
                    },
                    onPanStart: (_) async {
                      controller.setDragging(true);
                      try {
                        await windowManager.startDragging();
                      } finally {
                        controller.setDragging(false);
                      }
                    },
                    onPanEnd: (_) => controller.setDragging(false),
                    onPanCancel: () => controller.setDragging(false),
                    onSecondaryTapDown: (_) {
                      controller.setDoorMenuOpen(true);
                    },
                    child: SpriteAnimationView(
                      key: _animKey,
                      state: controller.currentState,
                      skin: controller.currentSkin,
                      posture: controller.currentPosture,
                      isMiniMode: controller.isMiniMode,
                      isDragging: controller.isDragging,
                      isDancing: controller.isDancing,
                      width: AppConstants.spriteDisplaySize.width,
                      height: AppConstants.spriteDisplaySize.height,
                      onComplete: controller.onAnimationCompleted,
                      onMiniPoked: controller.onMiniPoked,
                      onHeadPatted: controller.onHeadPatted,
                    ),
                  ),
                ),
              ),

              // 2. Bocadillo estilo Videollamada con Input de Texto y Talking Blips (`bubble.py`)
              if (showBubble && !controller.isMiniGameOpen && !controller.isBrainPanelOpen)
                Positioned(
                  top: 6,
                  left: 6,
                  right: 6,
                  child: SpeechBubble(
                    text: controller.currentSpeechText,
                    userText: controller.lastUserMessage,
                    state: controller.currentState,
                    isChatOpen: controller.isChatOpen,
                    isMiniMode: controller.isMiniMode,
                    isConnected: controller.wsStatus.name == 'connected',
                    isListeningMic: controller.isListeningMic,
                    isContinuousCall: controller.isContinuousVoiceCall,
                    callStartedAt: controller.callStartedAt,
                    onDismiss: controller.closeChatBox,
                    onToggleMini: controller.toggleMiniMode,
                    onOpenChat: controller.openChatBox,
                    onToggleMic: controller.toggleVoiceListen,
                    onToggleContinuousCall: controller.toggleContinuousVoiceCall,
                    onSendMessage: controller.sendUserMessage,
                  ),
                ),

              // 3. Tablero de Minijuegos Cyberpunk (`Minis.cs`: Gato, Conecta 4, Piedra Papel o Tijera)
              if (controller.isMiniGameOpen)
                Positioned(
                  top: 6,
                  left: 4,
                  right: 4,
                  child: CapriMiniGamesPanel(
                    initialGame: controller.activeMiniGame,
                    onCapriComment: controller.showSpeech,
                    onLiveEvent: controller.notifyMiniGameEvent,
                    onClose: controller.closeMiniGame,
                  ),
                ),

              // 3b. Panel Mainframe de Configuración del Cerebro IA (`Setup.cs` + `Brain.cs`)
              if (controller.isBrainPanelOpen)
                Positioned(
                  top: 6,
                  left: 4,
                  right: 4,
                  child: CapriBrainPanel(
                    status: controller.brainStatus,
                    onSave: controller.saveBrainConfig,
                    onGlanceScreen: controller.requestScreenGlance,
                    onClose: controller.closeBrainPanel,
                  ),
                ),

              // 4. Cyberpunk Mini Music Player (`Player.cs`)
              if (controller.isMiniPlayerOpen)
                Positioned(
                  bottom: 26,
                  left: 4,
                  right: 4,
                  child: CyberpunkMiniPlayer(
                    tune: controller.currentTune,
                    onCommand: controller.sendMediaCommand,
                    onClose: controller.closeMiniPlayer,
                  ),
                ),

              // 5. Puerta Cyberpunk de Menú Contextual (`assets/desk/door/` + `doormenu.py`)
              if (controller.isDoorMenuOpen)
                Positioned.fill(
                  child: CyberpunkDoorMenu(
                    controller: controller,
                    onClosed: () => controller.setDoorMenuOpen(false),
                  ),
                ),

              // 6. Accesos rápidos inferiores (Micrófono Voz / Cerebro IA / Música / Minijuegos) + Indicador WebSocket
              Positioned(
                bottom: 5,
                left: 10,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _QuickHudChip(
                      icon: controller.isListeningMic
                          ? Icons.graphic_eq_rounded
                          : Icons.mic_rounded,
                      tooltip: controller.isListeningMic
                          ? 'Escuchando tu voz... (Clic para enviar)'
                          : 'Hablar por Voz con Capri (Groq Whisper)',
                      active: controller.isListeningMic || controller.isContinuousVoiceCall,
                      onTap: controller.toggleVoiceListen,
                    ),
                    const SizedBox(width: 5),
                    _QuickHudChip(
                      icon: Icons.psychology_alt_rounded,
                      tooltip: 'Cerebro IA (${controller.brainStatus.activeLabel})',
                      active: controller.isBrainPanelOpen || controller.brainStatus.isLiveBrainActive,
                      onTap: controller.toggleBrainPanel,
                    ),
                    const SizedBox(width: 5),
                    _QuickHudChip(
                      icon: Icons.music_note_rounded,
                      tooltip: 'Mini Player / Baile',
                      active: controller.isMiniPlayerOpen || controller.isDancing,
                      onTap: controller.toggleMiniPlayer,
                    ),
                    const SizedBox(width: 5),
                    _QuickHudChip(
                      icon: Icons.sports_esports_rounded,
                      tooltip: 'Minijuegos con Capri',
                      active: controller.isMiniGameOpen,
                      onTap: () {
                        if (controller.isMiniGameOpen) {
                          controller.closeMiniGame();
                        } else {
                          controller.openMiniGame(controller.activeMiniGame);
                        }
                      },
                    ),
                  ],
                ),
              ),

              Positioned(
                bottom: 6,
                right: 10,
                child: ConnectionBadge(
                  status: controller.wsStatus,
                  onRetry: controller.reconnectWebSocket,
                ),
              ),
            ],
          ),
        ),
      );
      },
    );
  }
}

class _QuickHudChip extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final bool active;
  final VoidCallback onTap;

  const _QuickHudChip({
    required this.icon,
    required this.tooltip,
    required this.active,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          width: 22,
          height: 20,
          decoration: BoxDecoration(
            color: active ? const Color(0xD8FF1E6E) : const Color(0xB8110E18),
            border: Border.all(
              color: active ? const Color(0xFF78FAFF) : const Color(0x55FFFFFF),
              width: 1.0,
            ),
          ),
          alignment: Alignment.center,
          child: Icon(
            icon,
            size: 13,
            color: active ? Colors.white : const Color(0xFF78FAFF),
          ),
        ),
      ),
    );
  }
}
