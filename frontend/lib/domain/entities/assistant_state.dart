/// Enum que define los estados de la máquina de estados del asistente Capri.
enum AssistantState {
  idle,
  listening,
  thinking,
  teleporting,
  speaking,
  sleeping,
  sitting,
  victory,
  peek,
  point,
  intro;

  /// Parsea de forma segura un string proveniente del backend (ej. JSON payload)
  static AssistantState fromString(String? value) {
    if (value == null) return AssistantState.idle;
    final normalized = value.trim().toLowerCase();
    switch (normalized) {
      case 'idle':
      case 'reposo':
      case 'stand':
        return AssistantState.idle;
      case 'listening':
      case 'listen':
      case 'escuchando':
        return AssistantState.listening;
      case 'thinking':
      case 'think':
      case 'pensando':
      case 'razonando':
        return AssistantState.thinking;
      case 'teleporting':
      case 'teleport':
      case 'teletransporte':
      case 'warp':
        return AssistantState.teleporting;
      case 'speaking':
      case 'speak':
      case 'talking':
      case 'talk':
      case 'hablando':
        return AssistantState.speaking;
      case 'sleeping':
      case 'sleep':
      case 'durmiendo':
        return AssistantState.sleeping;
      case 'sitting':
      case 'sit':
      case 'sentada':
        return AssistantState.sitting;
      case 'victory':
      case 'done':
      case 'victoria':
        return AssistantState.victory;
      case 'peek':
      case 'espiar':
        return AssistantState.peek;
      case 'point':
      case 'apuntar':
      case 'señalar':
        return AssistantState.point;
      case 'intro':
      case 'saludo':
        return AssistantState.intro;
      default:
        return AssistantState.idle;
    }
  }

  /// Nombre amigable para mostrar en UI o menús
  String get displayName {
    switch (this) {
      case AssistantState.idle:
        return 'En reposo (Stand)';
      case AssistantState.listening:
        return 'Escuchando';
      case AssistantState.thinking:
        return 'Pensando';
      case AssistantState.teleporting:
        return 'Teletransporte';
      case AssistantState.speaking:
        return 'Hablando';
      case AssistantState.sleeping:
        return 'Durmiendo';
      case AssistantState.sitting:
        return 'Sentada (Sit)';
      case AssistantState.victory:
        return 'Victoria (Done)';
      case AssistantState.peek:
        return 'Espiando (Peek)';
      case AssistantState.point:
        return 'Apuntando (Point)';
      case AssistantState.intro:
        return 'Intro (Grab)';
    }
  }

  /// Indica si la animación por defecto de este estado es en bucle
  bool get isLooping {
    switch (this) {
      case AssistantState.teleporting:
      case AssistantState.victory:
      case AssistantState.intro:
        return false;
      default:
        return true;
    }
  }
}
