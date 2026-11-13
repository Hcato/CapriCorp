import 'dart:convert';
import '../../domain/entities/assistant_state.dart';

/// Modelo de evento recibido o transmitido a través del WebSocket.
class AssistantEvent {
  final String event;
  final AssistantState? state;
  final String? text;
  final String? rawData;
  final Map<String, dynamic> payload;

  AssistantEvent({
    required this.event,
    this.state,
    this.text,
    this.rawData,
    this.payload = const {},
  });

  /// Crea un objeto [AssistantEvent] a partir de un mapa JSON decodificado.
  factory AssistantEvent.fromJson(Map<String, dynamic> map, {String? rawData}) {
    final eventName = (map['event'] ?? 'unknown').toString();
    final stateStr = map['state']?.toString();
    final textContent = map['text']?.toString() ?? map['message']?.toString();

    return AssistantEvent(
      event: eventName,
      state: stateStr != null ? AssistantState.fromString(stateStr) : null,
      text: textContent,
      rawData: rawData,
      payload: map,
    );
  }

  /// Crea un objeto [AssistantEvent] a partir de una cadena JSON recibida.
  factory AssistantEvent.fromJsonString(String jsonStr) {
    try {
      final dynamic decoded = json.decode(jsonStr);
      if (decoded is Map<String, dynamic>) {
        return AssistantEvent.fromJson(decoded, rawData: jsonStr);
      }
      if (decoded is Map) {
        return AssistantEvent.fromJson(Map<String, dynamic>.from(decoded), rawData: jsonStr);
      }
      return AssistantEvent(
        event: 'parse_error',
        rawData: jsonStr,
        payload: const {'error': 'JSON root is not a Map'},
      );
    } catch (e) {
      return AssistantEvent(
        event: 'parse_error',
        rawData: jsonStr,
        payload: {'error': e.toString()},
      );
    }
  }

  /// Serializa un evento a JSON para enviarlo al backend de Python.
  String toJsonString() {
    final map = <String, dynamic>{
      'event': event,
      if (state != null) 'state': state!.name,
      if (text != null) 'text': text,
      ...payload,
    };
    return json.encode(map);
  }
}
