// Videocall-style chamfered chat box & speech bubble ported from Capri-cmd/capri-ai
// (capri/desk/bubble.py) combined with the expression portraits of mochiiwuff/capri-desktop.

import 'dart:async';
import 'package:flutter/material.dart';
import '../../core/audio/capri_sfx.dart';
import '../../core/constants/sprite_registry.dart';
import '../../domain/entities/assistant_state.dart';

class SpeechBubble extends StatefulWidget {
  final String? text;
  final String? userText;
  final AssistantState state;
  final bool isChatOpen;
  final bool isMiniMode;
  final bool isConnected;
  final bool isListeningMic;
  final bool isContinuousCall;
  final DateTime? callStartedAt;
  final VoidCallback? onDismiss;
  final VoidCallback? onToggleMini;
  final VoidCallback? onOpenChat;
  final VoidCallback? onToggleMic;
  final VoidCallback? onToggleContinuousCall;
  final ValueChanged<String>? onSendMessage;

  const SpeechBubble({
    super.key,
    this.text,
    this.userText,
    this.state = AssistantState.speaking,
    this.isChatOpen = false,
    this.isMiniMode = false,
    this.isConnected = false,
    this.isListeningMic = false,
    this.isContinuousCall = false,
    this.callStartedAt,
    this.onDismiss,
    this.onToggleMini,
    this.onOpenChat,
    this.onToggleMic,
    this.onToggleContinuousCall,
    this.onSendMessage,
  });

  @override
  State<SpeechBubble> createState() => _SpeechBubbleState();
}

class _SpeechBubbleState extends State<SpeechBubble> {
  static const Color _panelBg = Color(0xEC110E16);
  static const Color _panelHi = Color(0xEC1C1724);
  static const Color _edgeColor = Color(0x28FFFFFF);
  static const Color _pink = Color(0xFFFF2E70);
  static const Color _green = Color(0xFF2BFF9A);
  static const Color _cyan = Color(0xFF78FAFF);
  static const Color _textCol = Color(0xFFF2EEF7);
  static const Color _muted = Color(0xFF968CA5);

  final TextEditingController _inputController = TextEditingController();
  final FocusNode _focusNode = FocusNode();

  Timer? _typewriterTimer;
  Timer? _clockTimer;
  String _fullText = '';
  int _shownChars = 0;

  @override
  void initState() {
    super.initState();
    _startTypewriter(widget.text ?? '');
    _clockTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
    if (widget.isChatOpen) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _focusNode.requestFocus();
      });
    }
  }

  @override
  void didUpdateWidget(covariant SpeechBubble oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.text != widget.text) {
      _startTypewriter(widget.text ?? '');
    }
    if (!oldWidget.isChatOpen && widget.isChatOpen) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _focusNode.requestFocus();
      });
    }
  }

  void _startTypewriter(String newText) {
    _typewriterTimer?.cancel();
    _fullText = newText;
    if (_fullText.isEmpty) {
      _shownChars = 0;
      return;
    }
    _shownChars = 0;
    // 38 cps (~26 ms por carácter) como en `bubble.py`
    _typewriterTimer = Timer.periodic(const Duration(milliseconds: 26), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      if (_shownChars < _fullText.length) {
        final nextChar = _fullText[_shownChars];
        setState(() {
          _shownChars++;
        });
        CapriSfx.instance.playBlip(nextChar);
      } else {
        timer.cancel();
      }
    });
  }

  void _submitInput() {
    final val = _inputController.text.trim();
    if (val.isEmpty) return;
    _inputController.clear();
    CapriSfx.instance.play('key');
    widget.onSendMessage?.call(val);
  }

  String _formatCallDuration() {
    final start = widget.callStartedAt;
    if (start == null) return '00:00';
    final diff = DateTime.now().difference(start);
    final mins = (diff.inMinutes % 60).toString().padLeft(2, '0');
    final secs = (diff.inSeconds % 60).toString().padLeft(2, '0');
    return '$mins:$secs';
  }

  @override
  void dispose() {
    _typewriterTimer?.cancel();
    _clockTimer?.cancel();
    _inputController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final portraitAsset = SpriteRegistry.getFacePortraitAsset(widget.state);
    final visibleText = _fullText.isEmpty
        ? ''
        : _fullText.substring(0, _shownChars.clamp(0, _fullText.length));
    final signalLevel = widget.isConnected ? 1.0 : 0.5;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
      child: CustomPaint(
        painter: _ChamferPanelPainter(
          bgColor: _panelBg,
          borderColor: _edgeColor,
          accentColor: _pink,
          cut: 10.0,
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 1. Fila principal estilo Videollamada (`bubble.py`): Retrato + Cabecera + Respuesta
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Retrato vivo a la izquierda
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      color: _panelHi,
                      border: Border.all(
                        color: widget.state == AssistantState.speaking ? _green : _pink,
                        width: 1.3,
                      ),
                    ),
                    child: Image.asset(
                      portraitAsset,
                      width: 42,
                      height: 42,
                      fit: BoxFit.cover,
                      errorBuilder: (_, _, _) => const Icon(
                        Icons.bolt,
                        color: _cyan,
                        size: 20,
                      ),
                    ),
                  ),
                  const SizedBox(width: 9),

                  // Columna derecha: Cabecera de llamada + Lo que dijiste + Lo que responde Capri
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        // Barra superior: CAPRI + Medidor de señal + Timer + Botones rápidos
                        Row(
                          children: [
                            const Text(
                              'CAPRI',
                              style: TextStyle(
                                fontFamily: 'ShareTechMono',
                                color: _pink,
                                fontSize: 11.5,
                                fontWeight: FontWeight.bold,
                                letterSpacing: 1.0,
                              ),
                            ),
                            const SizedBox(width: 6),
                            _SignalBars(
                              level: signalLevel,
                              activeColor: widget.isConnected ? _green : _cyan,
                            ),
                            const SizedBox(width: 6),
                            Text(
                              _formatCallDuration(),
                              style: const TextStyle(
                                fontFamily: 'ShareTechMono',
                                color: _muted,
                                fontSize: 10,
                              ),
                            ),
                            const Spacer(),
                            // Botón de Micrófono (Hablar por voz con Groq Whisper)
                            if (widget.onToggleMic != null) ...[
                              _ChamferIconButton(
                                tooltip: widget.isListeningMic
                                    ? 'Detener y enviar voz'
                                    : 'Hablar por micrófono (Voz)',
                                icon: widget.isListeningMic
                                    ? Icons.graphic_eq_rounded
                                    : Icons.mic_rounded,
                                active: widget.isListeningMic,
                                onTap: widget.onToggleMic!,
                              ),
                              const SizedBox(width: 4),
                            ],
                            // Botón de Llamada de Voz Continua (Manos Libres)
                            if (widget.onToggleContinuousCall != null) ...[
                              _ChamferIconButton(
                                tooltip: widget.isContinuousCall
                                    ? 'Llamada continua ACTIVA (Manos libres)'
                                    : 'Activar llamada de voz continua',
                                icon: widget.isContinuousCall
                                    ? Icons.phone_in_talk_rounded
                                    : Icons.headset_mic_rounded,
                                active: widget.isContinuousCall,
                                onTap: widget.onToggleContinuousCall!,
                              ),
                              const SizedBox(width: 4),
                            ],
                            // Botón para abrir/cerrar input de texto
                            if (!widget.isChatOpen && widget.onOpenChat != null)
                              _ChamferIconButton(
                                tooltip: 'Escribir a Capri',
                                icon: Icons.chat_bubble_outline_rounded,
                                onTap: widget.onOpenChat!,
                              ),
                            if (widget.onToggleMini != null) ...[
                              const SizedBox(width: 4),
                              _ChamferIconButton(
                                tooltip: widget.isMiniMode ? 'Tamaño completo' : 'Modo Mini',
                                icon: widget.isMiniMode
                                    ? Icons.open_in_full_rounded
                                    : Icons.nightlight_round,
                                onTap: widget.onToggleMini!,
                              ),
                            ],
                            if (widget.onDismiss != null) ...[
                              const SizedBox(width: 4),
                              _ChamferIconButton(
                                tooltip: 'Cerrar',
                                icon: Icons.close_rounded,
                                onTap: widget.onDismiss!,
                              ),
                            ],
                          ],
                        ),

                        // Línea sutil con lo que dijo el usuario (`bubble.py` `self.user`)
                        if (widget.userText != null && widget.userText!.isNotEmpty) ...[
                          const SizedBox(height: 3),
                          Text(
                            '> ${widget.userText!}',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontFamily: 'ShareTechMono',
                              color: _muted,
                              fontSize: 10.5,
                            ),
                          ),
                        ],

                        // Estado en vivo de micrófono / pensamiento / texto revelado
                        if (widget.isListeningMic) ...[
                          const SizedBox(height: 4),
                          const Text(
                            '🎤 Escuchando tu voz... habla ahora (pausa o pulsa 🎤 para enviar)',
                            style: TextStyle(
                              fontFamily: 'ShareTechMono',
                              color: _green,
                              fontSize: 11.2,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ] else if (widget.state == AssistantState.thinking) ...[
                          const SizedBox(height: 4),
                          const Text(
                            'pensando...',
                            style: TextStyle(
                              fontFamily: 'ShareTechMono',
                              color: _cyan,
                              fontSize: 11.5,
                            ),
                          ),
                        ] else if (visibleText.isNotEmpty) ...[
                          const SizedBox(height: 4),
                          GestureDetector(
                            onTap: () {
                              if (_shownChars < _fullText.length) {
                                // Si aún está escribiendo, revelar todo de golpe
                                setState(() {
                                  _shownChars = _fullText.length;
                                });
                              } else {
                                widget.onOpenChat?.call();
                              }
                            },
                            child: Text(
                              visibleText,
                              maxLines: 4,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                color: _textCol,
                                fontSize: 12.2,
                                height: 1.25,
                                fontWeight: FontWeight.w500,
                                decoration: TextDecoration.none,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
              ),

              // 2. Caja de entrada de texto integrada (`bubble.py` `QLineEdit` + `icon_send`)
              if (widget.isChatOpen) ...[
                const SizedBox(height: 7),
                Container(
                  height: 28,
                  padding: const EdgeInsets.only(left: 8, right: 3),
                  decoration: BoxDecoration(
                    color: _panelHi,
                    border: Border.all(color: _pink.withValues(alpha: 0.65), width: 1.0),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _inputController,
                          focusNode: _focusNode,
                          onSubmitted: (_) => _submitInput(),
                          style: const TextStyle(
                            fontFamily: 'ShareTechMono',
                            color: _textCol,
                            fontSize: 12,
                          ),
                          decoration: const InputDecoration(
                            isDense: true,
                            border: InputBorder.none,
                            hintText: 'Háblale a Capri, choom...',
                            hintStyle: TextStyle(
                              fontFamily: 'ShareTechMono',
                              color: _muted,
                              fontSize: 11.5,
                            ),
                            contentPadding: EdgeInsets.zero,
                          ),
                        ),
                      ),
                      if (widget.onToggleMic != null) ...[
                        _ChamferIconButton(
                          tooltip: widget.isListeningMic
                              ? 'Detener grabación'
                              : 'Hablar por micrófono',
                          icon: widget.isListeningMic
                              ? Icons.graphic_eq_rounded
                              : Icons.mic_rounded,
                          active: widget.isListeningMic,
                          onTap: widget.onToggleMic!,
                        ),
                        const SizedBox(width: 4),
                      ],
                      _ChamferIconButton(
                        tooltip: 'Enviar',
                        icon: Icons.send_rounded,
                        onTap: _submitInput,
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Medidor de 4 barras de señal (`bubble.py` `icon_signal`).
class _SignalBars extends StatelessWidget {
  final double level;
  final Color activeColor;

  const _SignalBars({
    required this.level,
    required this.activeColor,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 13,
      height: 10,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: List.generate(4, (i) {
          final h = 10.0 * (0.35 + 0.65 * i / 3.0);
          final lit = level * 4.0 > i + 0.2;
          return Container(
            width: 2.2,
            height: h,
            color: lit ? activeColor : const Color(0x30FFFFFF),
          );
        }),
      ),
    );
  }
}

/// Botón cuadrado con esquinas recortadas (`bubble.py` `IconButton`).
class _ChamferIconButton extends StatefulWidget {
  final String tooltip;
  final IconData icon;
  final VoidCallback onTap;
  final bool active;

  const _ChamferIconButton({
    required this.tooltip,
    required this.icon,
    required this.onTap,
    this.active = false,
  });

  @override
  State<_ChamferIconButton> createState() => _ChamferIconButtonState();
}

class _ChamferIconButtonState extends State<_ChamferIconButton> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final highlighted = _hovered || widget.active;
    return Tooltip(
      message: widget.tooltip,
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        onEnter: (_) => setState(() => _hovered = true),
        onExit: (_) => setState(() => _hovered = false),
        child: GestureDetector(
          onTap: widget.onTap,
          child: Container(
            width: 19,
            height: 19,
            decoration: BoxDecoration(
              color: widget.active
                  ? const Color(0xFF2BFF9A)
                  : (_hovered ? const Color(0xFFFF2E70) : const Color(0xFF262030)),
              borderRadius: const BorderRadius.only(
                topRight: Radius.circular(3),
                bottomLeft: Radius.circular(3),
              ),
            ),
            child: Icon(
              widget.icon,
              size: 12,
              color: widget.active
                  ? const Color(0xFF110E16)
                  : (highlighted ? Colors.white : const Color(0xFF968CA5)),
            ),
          ),
        ),
      ),
    );
  }
}

/// Pinta el panel mate con esquinas recortadas (`chamfer` en `bubble.py`) y acento lateral rosa.
class _ChamferPanelPainter extends CustomPainter {
  final Color bgColor;
  final Color borderColor;
  final Color accentColor;
  final double cut;

  _ChamferPanelPainter({
    required this.bgColor,
    required this.borderColor,
    required this.accentColor,
    required this.cut,
  });

  Path _chamferPath(Rect r, double c) {
    return Path()
      ..moveTo(r.left + c, r.top)
      ..lineTo(r.right, r.top)
      ..lineTo(r.right, r.bottom - c)
      ..lineTo(r.right - c, r.bottom)
      ..lineTo(r.left, r.bottom)
      ..lineTo(r.left, r.top + c)
      ..close();
  }

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    final path = _chamferPath(rect, cut);

    canvas.drawPath(path, Paint()..color = bgColor);
    canvas.drawPath(
      path,
      Paint()
        ..color = borderColor
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.1,
    );

    // Línea de acento rosa en el chaflán superior izquierdo y borde superior
    final accentPath = Path()
      ..moveTo(rect.left, rect.top + cut)
      ..lineTo(rect.left + cut, rect.top)
      ..lineTo(rect.left + cut + 42, rect.top);
    canvas.drawPath(
      accentPath,
      Paint()
        ..color = accentColor
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.0,
    );
  }

  @override
  bool shouldRepaint(covariant _ChamferPanelPainter oldDelegate) => false;
}
