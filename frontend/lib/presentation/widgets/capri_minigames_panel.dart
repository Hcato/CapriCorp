// Cyberpunk Mini-Games Board ported from lachydotmcg/capri-desktop (app/Minis.cs).
// Includes:
// 1. Tres en Raya (Tic-Tac-Toe) — Minimax AI with 25% playful slip chance
// 2. Conecta 4 (Connect Four) — 7x6 Alpha-Beta pruning AI (depth 4)
// 3. Piedra, Papel o Tijera (Rock Paper Scissors) — Best of 3 match

import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../core/audio/capri_sfx.dart';

class CapriMiniGamesPanel extends StatefulWidget {
  final String initialGame; // 'tic_tac_toe' | 'connect_four' | 'rock_paper_scissors'
  final ValueChanged<String>? onCapriComment;
  final ValueChanged<String>? onLiveEvent;
  final VoidCallback onClose;

  const CapriMiniGamesPanel({
    super.key,
    this.initialGame = 'tic_tac_toe',
    this.onCapriComment,
    this.onLiveEvent,
    required this.onClose,
  });

  @override
  State<CapriMiniGamesPanel> createState() => _CapriMiniGamesPanelState();
}

class _CapriMiniGamesPanelState extends State<CapriMiniGamesPanel> {
  static const Color _bg = Color(0xF20E0B16);
  static const Color _pink = Color(0xFFFF1E6E);
  static const Color _cyan = Color(0xFF78FAFF);
  static const Color _mint = Color(0xFF34F5A0);
  static const Color _white = Color(0xFFF6F0FA);
  static const Color _dim = Color(0xFF968CA5);

  static const List<int> _c4Columns = [3, 2, 4, 1, 5, 0, 6];
  static const List<String> _rpsNames = ['PIEDRA', 'PAPEL', 'TIJERA'];
  static const List<String> _rpsIcons = ['✊', '✋', '✌️'];

  final math.Random _rng = math.Random();
  late String _kind;
  late List<int> _cells;
  bool _slip = false;
  int _result = 0; // 0 = jugando, 1 = ganas tú, 2 = gana Capri, 3 = empate
  int _rpsYou = 0;
  int _rpsHer = 0;
  int _yourHand = -1;
  int _herHand = -1;

  int _scoreYou = 0;
  int _scoreHer = 0;
  int _scoreDraws = 0;
  String _statusLine = 'Tu turno, choom.';

  @override
  void initState() {
    super.initState();
    _kind = widget.initialGame;
    _resetBoard();
  }

  @override
  void didUpdateWidget(covariant CapriMiniGamesPanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.initialGame != widget.initialGame) {
      _kind = widget.initialGame;
      _resetBoard();
    }
  }

  void _switchGame(String newKind) {
    CapriSfx.instance.play('key');
    setState(() {
      _kind = newKind;
      _resetBoard();
    });
  }

  void _resetBoard() {
    _cells = List<int>.filled(_kind == 'connect_four' ? 42 : 9, 0);
    _result = 0;
    _rpsYou = 0;
    _rpsHer = 0;
    _yourHand = -1;
    _herHand = -1;
    _slip = _rng.nextInt(4) == 0;
    _statusLine = _kind == 'rock_paper_scissors'
        ? 'Elige Piedra, Papel o Tijera (al mejor de 3)'
        : 'Tu turno, choom. Tú eres Cian (X), Capri es Rosa (O).';
  }

  void _handleMove(int move) {
    if (_result != 0) {
      CapriSfx.instance.play('key');
      setState(_resetBoard);
      return;
    }

    if (_kind == 'rock_paper_scissors') {
      if (move < 0 || move > 2) return;
      CapriSfx.instance.play('pop');
      setState(() {
        _yourHand = move;
        _herHand = _rng.nextInt(3);
        final won = _handResult(_yourHand, _herHand);
        if (won == 1) _rpsYou++;
        if (won == 2) _rpsHer++;
        _statusLine =
            'Tú: ${_rpsNames[_yourHand]} vs Capri: ${_rpsNames[_herHand]} -> ${won == 0 ? "Empate" : won == 1 ? "¡Punto tuyo!" : "¡Punto mío!"}';
        if (_rpsYou == 3 || _rpsHer == 3) {
          _endRound(_rpsYou == 3 ? 1 : 2);
        }
      });
      return;
    }

    final int square = _kind == 'connect_four' ? _landing(_cells, move) : move;
    if (square < 0 || square >= _cells.length || _cells[square] != 0) {
      return;
    }

    CapriSfx.instance.play('key');
    setState(() {
      _cells[square] = 1;
      int state = _outcome(_cells, _kind == 'connect_four');
      if (state != 0) {
        _endRound(state);
        return;
      }

      int reply;
      if (_kind == 'tic_tac_toe') {
        final best = _ticMove(_cells, false);
        reply = _ticMove(_cells, _slip);
        if (best >= 0 && reply >= 0) {
          _cells[best] = 2;
          final bestVal = _ticValue(_cells, 1);
          _cells[best] = 0;
          _cells[reply] = 2;
          if (_ticValue(_cells, 1) < bestVal) _slip = false;
        }
      } else {
        final col = _fourMove(_cells);
        reply = _landing(_cells, col);
        if (reply >= 0) {
          _cells[reply] = 2;
        }
      }

      state = _outcome(_cells, _kind == 'connect_four');
      if (state != 0) {
        _endRound(state);
      } else {
        _statusLine = 'Capri jugó. ¡Te toca, choom!';
      }
    });
  }

  void _endRound(int res) {
    _result = res;
    final gameTitle = _kind == 'connect_four'
        ? 'Conecta 4'
        : (_kind == 'rock_paper_scissors' ? 'Piedra, Papel o Tijera' : 'Tres en Raya');
    if (res == 1) {
      _scoreYou++;
      _statusLine = '¡Ganaste esta ronda! Toca para la revancha.';
      CapriSfx.instance.play('coin');
      widget.onCapriComment?.call('¡Oye! Tuviste suerte esta vez, choom. Pido la revancha.');
      widget.onLiveEvent?.call(
        'El usuario acaba de ganarte una partida de $gameTitle (Marcador: Usuario $_scoreYou - Capri $_scoreHer).',
      );
    } else if (res == 2) {
      _scoreHer++;
      _statusLine = '¡Capri gana! Toca para otra partida.';
      CapriSfx.instance.play('charge');
      widget.onCapriComment?.call('¡Jaque mate digital, gonk! Mi biochip nunca falla.');
      widget.onLiveEvent?.call(
        'Acabas de ganarle al usuario una partida de $gameTitle (Marcador: Usuario $_scoreYou - Capri $_scoreHer). Presume con cariño.',
      );
    } else {
      _scoreDraws++;
      _statusLine = 'Empate técnico. Toca para desempatar.';
      widget.onCapriComment?.call('Empate. Nada mal para un humano de carne y hueso.');
      widget.onLiveEvent?.call(
        'Empataron una partida de $gameTitle (Marcador: Usuario $_scoreYou - Capri $_scoreHer).',
      );
    }
  }

  // ── Algoritmos de IA (`app/Minis.cs`) ─────────────────────────────

  static int _handResult(int you, int her) => you == her ? 0 : ((you + 2) % 3 == her ? 1 : 2);

  static int _landing(List<int> board, int col) {
    if (col < 0 || col > 6) return -1;
    for (int row = 5; row >= 0; row--) {
      if (board[row * 7 + col] == 0) return row * 7 + col;
    }
    return -1;
  }

  static int _outcome(List<int> board, bool four) {
    final width = four ? 7 : 3;
    final height = four ? 6 : 3;
    final run = four ? 4 : 3;
    const dx = [1, 0, 1, -1];
    const dy = [0, 1, 1, 1];
    bool full = true;
    for (int at = 0; at < board.length; at++) {
      if (board[at] == 0) {
        full = false;
        continue;
      }
      for (int way = 0; way < 4; way++) {
        final x = (at % width) + dx[way] * (run - 1);
        final y = (at ~/ width) + dy[way] * (run - 1);
        if (x < 0 || x >= width || y < 0 || y >= height) continue;
        int along = 1;
        while (along < run && board[at + along * (dx[way] + width * dy[way])] == board[at]) {
          along++;
        }
        if (along == run) return board[at];
      }
    }
    return full ? 3 : 0;
  }

  int _ticMove(List<int> board, bool allowWrong) {
    int best = -100;
    final good = <int>[];
    final bad = <int>[];
    for (int pick = 0; pick < 9; pick++) {
      if (board[pick] != 0) continue;
      board[pick] = 2;
      final val = _ticValue(board, 1);
      board[pick] = 0;
      if (val > best) {
        bad.addAll(good);
        good.clear();
        best = val;
      }
      if (val == best) {
        good.add(pick);
      } else {
        bad.add(pick);
      }
    }
    final choices = (allowWrong && bad.isNotEmpty) ? bad : good;
    return choices.isEmpty ? -1 : choices[_rng.nextInt(choices.length)];
  }

  static int _ticValue(List<int> board, int turn) {
    final state = _outcome(board, false);
    if (state != 0) return state == 2 ? 1 : (state == 1 ? -1 : 0);
    int best = turn == 2 ? -2 : 2;
    for (int sq = 0; sq < 9; sq++) {
      if (board[sq] != 0) continue;
      board[sq] = turn;
      final val = _ticValue(board, 3 - turn);
      board[sq] = 0;
      best = turn == 2 ? math.max(best, val) : math.min(best, val);
    }
    return best;
  }

  int _fourMove(List<int> board) {
    int best = -999999;
    final picks = <int>[];
    for (final col in _c4Columns) {
      final at = _landing(board, col);
      if (at < 0) continue;
      board[at] = 2;
      final val = _fourValue(board, 4, 1, -100000, 100000);
      board[at] = 0;
      if (val > best) {
        best = val;
        picks.clear();
      }
      if (val == best) picks.add(col);
    }
    return picks.isEmpty ? -1 : picks[_rng.nextInt(picks.length)];
  }

  static int _fourValue(List<int> board, int depth, int turn, int alpha, int beta) {
    final state = _outcome(board, true);
    if (state != 0) return state == 2 ? 10000 + depth : (state == 1 ? -10000 - depth : 0);
    if (depth == 0) return _fourEstimate(board);
    int best = turn == 2 ? -100000 : 100000;
    int a = alpha;
    int b = beta;
    for (final col in _c4Columns) {
      final at = _landing(board, col);
      if (at < 0) continue;
      board[at] = turn;
      final val = _fourValue(board, depth - 1, 3 - turn, a, b);
      board[at] = 0;
      best = turn == 2 ? math.max(best, val) : math.min(best, val);
      if (turn == 2) {
        a = math.max(a, best);
      } else {
        b = math.min(b, best);
      }
      if (a >= b) break;
    }
    return best;
  }

  static int _fourEstimate(List<int> board) {
    int score = 0;
    for (int row = 0; row < 6; row++) {
      final mid = board[row * 7 + 3];
      if (mid == 2) score += 4;
      if (mid == 1) score -= 4;
    }
    return score;
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
      child: Container(
        padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
        decoration: BoxDecoration(
          color: _bg,
          border: Border.all(color: _pink, width: 1.5),
          boxShadow: [
            BoxShadow(
              color: _pink.withValues(alpha: 0.32),
              blurRadius: 12,
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // 1. Cabecera: Selector de juego + Cerrar
            Row(
              children: [
                _GameTabBtn(
                  label: 'GATO',
                  active: _kind == 'tic_tac_toe',
                  onTap: () => _switchGame('tic_tac_toe'),
                ),
                const SizedBox(width: 4),
                _GameTabBtn(
                  label: 'CONECTA 4',
                  active: _kind == 'connect_four',
                  onTap: () => _switchGame('connect_four'),
                ),
                const SizedBox(width: 4),
                _GameTabBtn(
                  label: 'P.P.T.',
                  active: _kind == 'rock_paper_scissors',
                  onTap: () => _switchGame('rock_paper_scissors'),
                ),
                const Spacer(),
                GestureDetector(
                  onTap: () {
                    CapriSfx.instance.play('key');
                    setState(_resetBoard);
                  },
                  child: const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 4),
                    child: Icon(Icons.refresh_rounded, color: _cyan, size: 15),
                  ),
                ),
                GestureDetector(
                  onTap: widget.onClose,
                  child: const Icon(Icons.close_rounded, color: _dim, size: 16),
                ),
              ],
            ),
            const SizedBox(height: 5),

            // 2. Marcador (`MiniScore`)
            Text(
              'TÚ $_scoreYou   •   CAPRI $_scoreHer   •   EMPATES $_scoreDraws',
              style: const TextStyle(
                fontFamily: 'ShareTechMono',
                color: _mint,
                fontSize: 10,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 5),

            // 3. Tablero según el juego seleccionado
            if (_kind == 'tic_tac_toe') _buildTicTacToeBoard(),
            if (_kind == 'connect_four') _buildConnectFourBoard(),
            if (_kind == 'rock_paper_scissors') _buildRpsBoard(),

            const SizedBox(height: 5),
            Text(
              _statusLine,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontFamily: 'ShareTechMono',
                color: _result == 1 ? _mint : (_result == 2 ? _pink : _white),
                fontSize: 10.5,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTicTacToeBoard() {
    return SizedBox(
      width: 138,
      height: 138,
      child: GridView.builder(
        physics: const NeverScrollableScrollPhysics(),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 3,
          crossAxisSpacing: 4,
          mainAxisSpacing: 4,
        ),
        itemCount: 9,
        itemBuilder: (context, idx) {
          final v = _cells[idx];
          return GestureDetector(
            onTap: () => _handleMove(idx),
            child: Container(
              decoration: BoxDecoration(
                color: const Color(0xFF1A1426),
                border: Border.all(
                  color: v == 1 ? _cyan : (v == 2 ? _pink : const Color(0x44FFFFFF)),
                  width: 1.2,
                ),
              ),
              alignment: Alignment.center,
              child: Text(
                v == 1 ? 'X' : (v == 2 ? 'O' : ''),
                style: TextStyle(
                  fontFamily: 'ShareTechMono',
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                  color: v == 1 ? _cyan : _pink,
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildConnectFourBoard() {
    return SizedBox(
      width: 196,
      height: 156,
      child: GridView.builder(
        physics: const NeverScrollableScrollPhysics(),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 7,
          crossAxisSpacing: 3,
          mainAxisSpacing: 3,
        ),
        itemCount: 42,
        itemBuilder: (context, idx) {
          final v = _cells[idx];
          final col = idx % 7;
          return GestureDetector(
            onTap: () => _handleMove(col),
            child: Container(
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: v == 1 ? _cyan : (v == 2 ? _pink : const Color(0xFF1A1426)),
                border: Border.all(
                  color: v == 1 ? _cyan : (v == 2 ? _pink : const Color(0x38FFFFFF)),
                  width: 1.0,
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildRpsBoard() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          'Ronda actual: TÚ $_rpsYou  -  $_rpsHer CAPRI',
          style: const TextStyle(
            fontFamily: 'ShareTechMono',
            color: _cyan,
            fontSize: 11,
          ),
        ),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: List.generate(3, (idx) {
            final selected = _yourHand == idx;
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 5),
              child: GestureDetector(
                onTap: () => _handleMove(idx),
                child: Container(
                  width: 68,
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  decoration: BoxDecoration(
                    color: selected ? _pink.withValues(alpha: 0.35) : const Color(0xFF1A1426),
                    border: Border.all(color: selected ? _cyan : _pink, width: 1.3),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(_rpsIcons[idx], style: const TextStyle(fontSize: 20)),
                      const SizedBox(height: 3),
                      Text(
                        _rpsNames[idx],
                        style: const TextStyle(
                          fontFamily: 'ShareTechMono',
                          color: _white,
                          fontSize: 10,
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
      ],
    );
  }
}

class _GameTabBtn extends StatelessWidget {
  final String label;
  final bool active;
  final VoidCallback onTap;

  const _GameTabBtn({
    required this.label,
    required this.active,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
        decoration: BoxDecoration(
          color: active ? const Color(0xFFFF1E6E) : const Color(0xFF1C1628),
          border: Border.all(
            color: active ? const Color(0xFF78FAFF) : const Color(0x44FFFFFF),
            width: 1.0,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontFamily: 'ShareTechMono',
            color: active ? Colors.white : const Color(0xFF968CA5),
            fontSize: 10,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }
}

