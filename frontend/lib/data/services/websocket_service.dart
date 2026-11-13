import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../../core/constants/app_constants.dart';
import '../models/assistant_event.dart';

enum WsConnectionStatus {
  disconnected,
  connecting,
  connected,
}

/// Servicio WebSocket cliente para comunicarse bidireccionalmente con el Backend de Python.
class WebSocketService {
  final String serverUrl;
  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  Timer? _reconnectTimer;

  bool _isDisposed = false;
  WsConnectionStatus _status = WsConnectionStatus.disconnected;

  final _eventController = StreamController<AssistantEvent>.broadcast();
  final _statusController = StreamController<WsConnectionStatus>.broadcast();

  Stream<AssistantEvent> get onEvent => _eventController.stream;
  Stream<WsConnectionStatus> get onStatusChange => _statusController.stream;
  WsConnectionStatus get status => _status;

  WebSocketService({String? url}) : serverUrl = url ?? AppConstants.defaultWsUrl;

  /// Inicia la conexión con el servidor WebSocket.
  void connect() {
    if (_isDisposed) return;
    if (_status == WsConnectionStatus.connected || _status == WsConnectionStatus.connecting) return;

    _updateStatus(WsConnectionStatus.connecting);

    try {
      final uri = Uri.parse(serverUrl);
      _channel = WebSocketChannel.connect(uri);

      _subscription = _channel!.stream.listen(
        (data) {
          if (_status != WsConnectionStatus.connected) {
            _updateStatus(WsConnectionStatus.connected);
          }
          _handleIncomingMessage(data.toString());
        },
        onError: (error) {
          if (kDebugMode) {
            print('[WebSocketService] Error en socket: $error');
          }
          _handleDisconnect();
        },
        onDone: () {
          if (kDebugMode) {
            print('[WebSocketService] Conexión cerrada por el servidor.');
          }
          _handleDisconnect();
        },
        cancelOnError: true,
      );
    } catch (e) {
      if (kDebugMode) {
        print('[WebSocketService] Excepción al conectar: $e');
      }
      _handleDisconnect();
    }
  }

  void _handleIncomingMessage(String raw) {
    if (kDebugMode) {
      final preview = raw.length > 260 ? '${raw.substring(0, 260)}... (${raw.length} chars)' : raw;
      print('[WebSocketService] <- Recibido: $preview');
    }
    final event = AssistantEvent.fromJsonString(raw);
    _eventController.add(event);
  }

  void _handleDisconnect() {
    _subscription?.cancel();
    _subscription = null;
    _channel = null;

    _updateStatus(WsConnectionStatus.disconnected);

    if (!_isDisposed) {
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(AppConstants.wsReconnectDelay, () {
      if (!_isDisposed && _status == WsConnectionStatus.disconnected) {
        if (kDebugMode) {
          print('[WebSocketService] Reintentando conexión con $serverUrl...');
        }
        connect();
      }
    });
  }

  void _updateStatus(WsConnectionStatus newStatus) {
    _status = newStatus;
    _statusController.add(_status);
  }

  /// Envía un evento serializado en JSON al backend de Python.
  void sendEvent(AssistantEvent event) {
    if (_status == WsConnectionStatus.connected && _channel != null) {
      final payload = event.toJsonString();
      if (kDebugMode) {
        print('[WebSocketService] -> Enviando: $payload');
      }
      _channel!.sink.add(payload);
    } else {
      if (kDebugMode) {
        print('[WebSocketService] Imposible enviar evento, socket desconectado.');
      }
    }
  }

  /// Cierra todas las conexiones y libera recursos.
  void dispose() {
    _isDisposed = true;
    _reconnectTimer?.cancel();
    _subscription?.cancel();
    _channel?.sink.close();
    _eventController.close();
    _statusController.close();
  }
}
