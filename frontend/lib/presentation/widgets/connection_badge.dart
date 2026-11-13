import 'package:flutter/material.dart';
import '../../data/services/websocket_service.dart';

/// Indicador discreto del estado de enlace WebSocket con el backend de Python.
class ConnectionBadge extends StatelessWidget {
  final WsConnectionStatus status;
  final VoidCallback? onRetry;

  const ConnectionBadge({
    super.key,
    required this.status,
    this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    Color color;
    String tooltip;

    switch (status) {
      case WsConnectionStatus.connected:
        color = const Color(0xFF00FF88);
        tooltip = 'Backend Conectado (ws://127.0.0.1:8765)';
        break;
      case WsConnectionStatus.connecting:
        color = const Color(0xFFFFB703);
        tooltip = 'Conectando al Backend...';
        break;
      case WsConnectionStatus.disconnected:
        color = const Color(0xFFFF0055);
        tooltip = 'Backend Desconectado (Clic para reintentar)';
        break;
    }

    return Tooltip(
      message: tooltip,
      child: GestureDetector(
        onTap: status == WsConnectionStatus.disconnected ? onRetry : null,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
          decoration: BoxDecoration(
            color: const Color(0xDD0D0E15),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: color.withValues(alpha: 0.6), width: 1),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color: color,
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(color: color.withValues(alpha: 0.8), blurRadius: 4),
                  ],
                ),
              ),
              const SizedBox(width: 5),
              Text(
                status == WsConnectionStatus.connected
                    ? 'LINK OK'
                    : (status == WsConnectionStatus.connecting ? 'SYNC...' : 'OFFLINE'),
                style: TextStyle(
                  color: color,
                  fontSize: 8.5,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 0.8,
                  decoration: TextDecoration.none,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
