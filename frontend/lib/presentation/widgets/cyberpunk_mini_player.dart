// Cyberpunk Mini Music Player ported from lachydotmcg/capri-desktop (app/Player.cs MiniPlayer).
// Displays the currently playing song/video from Windows (Spotify, YouTube, VLC, etc.),
// animated equalizer bars, seek bar, and media controls (Previous, Play/Pause, Next, Heart, Volume).

import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../core/audio/capri_sfx.dart';

class MediaTuneState {
  final String title;
  final String artist;
  final String app;
  final bool playing;
  final bool liked;
  final double position;
  final double length;

  const MediaTuneState({
    this.title = '',
    this.artist = '',
    this.app = '',
    this.playing = false,
    this.liked = false,
    this.position = 0.0,
    this.length = 210.0,
  });

  bool get hasTrack => title.trim().isNotEmpty;

  factory MediaTuneState.fromMap(Map<String, dynamic> map) {
    return MediaTuneState(
      title: (map['title'] as String?) ?? '',
      artist: (map['artist'] as String?) ?? '',
      app: (map['app'] as String?) ?? '',
      playing: (map['playing'] as bool?) ?? false,
      liked: (map['liked'] as bool?) ?? false,
      position: ((map['position'] as num?) ?? 0.0).toDouble(),
      length: ((map['length'] as num?) ?? 210.0).toDouble(),
    );
  }
}

class CyberpunkMiniPlayer extends StatelessWidget {
  final MediaTuneState tune;
  final void Function(String action, [String arg]) onCommand;
  final VoidCallback onClose;

  const CyberpunkMiniPlayer({
    super.key,
    required this.tune,
    required this.onCommand,
    required this.onClose,
  });

  static const Color _bg = Color(0xEE0D0A14);
  static const Color _pink = Color(0xFFFF1E6E);
  static const Color _cyan = Color(0xFF78FAFF);
  static const Color _mint = Color(0xFF34F5A0);
  static const Color _white = Color(0xFFF6F0FA);
  static const Color _dim = Color(0xFF968CA5);

  String _fmtSec(double s) {
    final total = math.max(0, s.round());
    final m = (total ~/ 60).toString().padLeft(2, '0');
    final sec = (total % 60).toString().padLeft(2, '0');
    return '$m:$sec';
  }

  @override
  Widget build(BuildContext context) {
    final title = tune.hasTrack ? tune.title : 'SIN REPRODUCCIÓN ACTIVA';
    final artist = tune.hasTrack ? '${tune.artist} • ${tune.app.toUpperCase()}' : 'PON SPOTIFY O YOUTUBE';
    final maxLen = math.max(1.0, tune.length);
    final double progress = (tune.position / maxLen).clamp(0.0, 1.0).toDouble();

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      child: Container(
        padding: const EdgeInsets.fromLTRB(10, 7, 10, 7),
        decoration: BoxDecoration(
          color: _bg,
          border: Border.all(color: tune.playing ? _cyan : _pink, width: 1.4),
          boxShadow: [
            BoxShadow(
              color: (tune.playing ? _cyan : _pink).withValues(alpha: 0.28),
              blurRadius: 10,
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 1. Fila superior: Icono + Título/Artista + Cerrar
            Row(
              children: [
                Icon(
                  tune.playing ? Icons.graphic_eq_rounded : Icons.music_note_rounded,
                  color: tune.playing ? _mint : _pink,
                  size: 16,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontFamily: 'ShareTechMono',
                          color: _white,
                          fontSize: 11.5,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Text(
                        artist,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontFamily: 'ShareTechMono',
                          color: _cyan,
                          fontSize: 9.5,
                        ),
                      ),
                    ],
                  ),
                ),
                _MiniPlayerBtn(
                  icon: Icons.close_rounded,
                  tooltip: 'Ocultar reproductor',
                  color: _dim,
                  onTap: () {
                    CapriSfx.instance.play('key');
                    onClose();
                  },
                ),
              ],
            ),
            const SizedBox(height: 5),

            // 2. Barra de progreso / Seek interactiva (`PlayerPart.Seek`)
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTapDown: (details) {
                final box = context.findRenderObject() as RenderBox?;
                if (box != null && box.size.width > 24) {
                  final double ratio =
                      (details.localPosition.dx / (box.size.width - 24)).clamp(0.0, 1.0).toDouble();
                  final targetSec = (ratio * maxLen).toStringAsFixed(1);
                  CapriSfx.instance.play('key');
                  onCommand('seek', targetSec);
                }
              },
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Column(
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(1),
                      child: LinearProgressIndicator(
                        value: progress,
                        minHeight: 4,
                        backgroundColor: const Color(0xFF282034),
                        valueColor: AlwaysStoppedAnimation<Color>(tune.playing ? _pink : _dim),
                      ),
                    ),
                    const SizedBox(height: 2),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          _fmtSec(tune.position),
                          style: const TextStyle(
                            fontFamily: 'ShareTechMono',
                            color: _dim,
                            fontSize: 9,
                          ),
                        ),
                        Text(
                          _fmtSec(tune.length),
                          style: const TextStyle(
                            fontFamily: 'ShareTechMono',
                            color: _dim,
                            fontSize: 9,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),

            // 3. Controles: Prev | Play/Pause | Next | Like | Vol- | Vol+
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                _MiniPlayerBtn(
                  icon: Icons.skip_previous_rounded,
                  tooltip: 'Anterior',
                  onTap: () {
                    CapriSfx.instance.play('key');
                    onCommand('previous');
                  },
                ),
                _MiniPlayerBtn(
                  icon: tune.playing ? Icons.pause_circle_filled_rounded : Icons.play_circle_fill_rounded,
                  tooltip: tune.playing ? 'Pausar' : 'Reproducir',
                  color: tune.playing ? _cyan : _pink,
                  size: 20,
                  onTap: () {
                    CapriSfx.instance.play('key');
                    onCommand('toggle');
                  },
                ),
                _MiniPlayerBtn(
                  icon: Icons.skip_next_rounded,
                  tooltip: 'Siguiente',
                  onTap: () {
                    CapriSfx.instance.play('key');
                    onCommand('next');
                  },
                ),
                _MiniPlayerBtn(
                  icon: tune.liked ? Icons.favorite_rounded : Icons.favorite_border_rounded,
                  tooltip: 'Me gusta (Spotify)',
                  color: tune.liked ? _pink : _white,
                  onTap: () {
                    CapriSfx.instance.play('coin');
                    onCommand('like');
                  },
                ),
                _MiniPlayerBtn(
                  icon: Icons.volume_down_rounded,
                  tooltip: 'Bajar volumen',
                  color: _dim,
                  onTap: () {
                    CapriSfx.instance.play('key');
                    onCommand('vol_down');
                  },
                ),
                _MiniPlayerBtn(
                  icon: Icons.volume_up_rounded,
                  tooltip: 'Subir volumen',
                  color: _dim,
                  onTap: () {
                    CapriSfx.instance.play('key');
                    onCommand('vol_up');
                  },
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _MiniPlayerBtn extends StatefulWidget {
  final IconData icon;
  final String tooltip;
  final Color color;
  final double size;
  final VoidCallback onTap;

  const _MiniPlayerBtn({
    required this.icon,
    required this.tooltip,
    required this.onTap,
    this.color = const Color(0xFFF6F0FA),
    this.size = 16,
  });

  @override
  State<_MiniPlayerBtn> createState() => _MiniPlayerBtnState();
}

class _MiniPlayerBtnState extends State<_MiniPlayerBtn> {
  bool _hover = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hover = true),
      onExit: (_) => setState(() => _hover = false),
      child: Tooltip(
        message: widget.tooltip,
        child: GestureDetector(
          onTap: widget.onTap,
          child: Container(
            padding: const EdgeInsets.all(3),
            decoration: BoxDecoration(
              color: _hover ? const Color(0x38FF1E6E) : Colors.transparent,
              borderRadius: BorderRadius.circular(3),
            ),
            child: Icon(
              widget.icon,
              size: widget.size,
              color: _hover ? const Color(0xFF78FAFF) : widget.color,
            ),
          ),
        ),
      ),
    );
  }
}

