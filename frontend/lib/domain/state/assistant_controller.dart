import 'dart:async';
import 'dart:math' as math;
import 'dart:ui' show Offset;
import 'package:flutter/foundation.dart';
import 'package:window_manager/window_manager.dart';
import '../../core/audio/capri_sfx.dart';
import '../../core/constants/sprite_registry.dart';
import '../../data/models/assistant_event.dart';
import '../../data/services/websocket_service.dart';
import '../../presentation/animation/capri_desk_sprites.dart';
import '../../presentation/widgets/capri_brain_panel.dart';
import '../../presentation/widgets/cyberpunk_mini_player.dart';
import '../entities/assistant_state.dart';

/// Elemento de la cola de diálogo y animación para evitar que los mensajes se entrelacen.
class _QueuedSpeechItem {
  final String text;
  final AssistantState targetState;
  final String? userEcho;
  final String? audioB64;
  final String priority;

  const _QueuedSpeechItem({
    required this.text,
    required this.targetState,
    this.userEcho,
    this.audioB64,
    this.priority = 'normal',
  });
}

/// Controlador central del estado del asistente (Máquina de Estados + Skins + Modo Mini +
/// Reproductor Musical + Minijuegos + Piloto de Juegos + Head Pats + Chat).
class AssistantController extends ChangeNotifier {
  final WebSocketService _wsService;
  final math.Random _rng = math.Random();

  AssistantState _currentState = AssistantState.idle;
  CapriVisualSkin _currentSkin = CapriVisualSkin.shaderRig;
  CapriPosture _currentPosture = CapriPosture.standing;
  bool _isMiniMode = false;
  bool _isDragging = false;
  bool _isChatOpen = false;
  bool _isDoorMenuOpen = false;

  // Estado Multimedia y Baile (`Player.cs` + `Capri.cs`)
  MediaTuneState _currentTune = const MediaTuneState();
  bool _isMiniPlayerOpen = false;
  bool _manualDancing = false;

  // Estado de Minijuegos y Piloto Automático (`Minis.cs` + `Play.cs` + `GameSense.cs`)
  bool _isMiniGameOpen = false;
  String _activeMiniGame = 'tic_tac_toe';
  bool _isGameAutopilotActive = false;
  bool _isGameSenseEnabled = false;

  // Estado del Cerebro Conversacional IA (`Brain.cs` + `Setup.cs`) y Voz (`Voice.cs` + `Talk.cs`)
  BrainConfigState _brainStatus = const BrainConfigState();
  bool _isBrainPanelOpen = false;
  bool _isListeningMic = false;
  bool _isContinuousVoiceCall = false;
  bool _isTtsEnabled = true;

  // Nuevas capacidades (Lookout.cs, Reminders.cs, Clones.cs)
  List<Map<String, dynamic>> _activeWatches = [];
  List<Map<String, dynamic>> _pendingReminders = [];
  List<Map<String, dynamic>> _activeClones = [];
  bool _isHologramEnabled = false;

  List<Map<String, dynamic>> get activeWatches => _activeWatches;
  List<Map<String, dynamic>> get pendingReminders => _pendingReminders;
  List<Map<String, dynamic>> get activeClones => _activeClones;
  bool get isHologramEnabled => _isHologramEnabled;

  WsConnectionStatus _wsStatus = WsConnectionStatus.disconnected;
  bool _isMuted = false;
  String? _currentSpeechText;
  String? _lastUserMessage;
  final DateTime callStartedAt = DateTime.now();
  Timer? _speechBubbleTimer;
  DateTime _speechBusyUntil = DateTime.fromMillisecondsSinceEpoch(0);
  DateTime _lastHeadPatAt = DateTime.fromMillisecondsSinceEpoch(0);
  final List<_QueuedSpeechItem> _speechQueue = [];

  StreamSubscription? _eventSub;
  StreamSubscription? _statusSub;

  AssistantState get currentState => _currentState;
  CapriVisualSkin get currentSkin => _currentSkin;
  CapriPosture get currentPosture => _currentPosture;
  bool get isMiniMode => _isMiniMode;
  bool get isDragging => _isDragging;
  bool get isChatOpen => _isChatOpen;
  bool get isDoorMenuOpen => _isDoorMenuOpen;

  MediaTuneState get currentTune => _currentTune;
  bool get isMiniPlayerOpen => _isMiniPlayerOpen;
  bool get isDancing => _manualDancing || _currentTune.playing;

  bool get isMiniGameOpen => _isMiniGameOpen;
  String get activeMiniGame => _activeMiniGame;
  bool get isGameAutopilotActive => _isGameAutopilotActive;
  bool get isGameSenseEnabled => _isGameSenseEnabled;

  BrainConfigState get brainStatus => _brainStatus;
  bool get isBrainPanelOpen => _isBrainPanelOpen;
  bool get isListeningMic => _isListeningMic;
  bool get isContinuousVoiceCall => _isContinuousVoiceCall;
  bool get isTtsEnabled => _isTtsEnabled;

  WsConnectionStatus get wsStatus => _wsStatus;
  bool get isMuted => _isMuted;
  String? get currentSpeechText => _currentSpeechText;
  String? get lastUserMessage => _lastUserMessage;
  bool get isSpeaking => _currentState == AssistantState.speaking;

  static const List<String> _offlineReplies = [
    'Te escucho fuerte y claro, choom. Arranca el cerebro en Python si quieres que jaquee la red.',
    '¿Aburrido? Abre mi puerta con clic derecho y jugamos Conecta 4 o Tres en Raya.',
    'Todavía me estoy acomodando en tu escritorio, gonk. Dame un segundo.',
    'Si Arasaka pregunta por mí, tú no has visto nada, ¿entendido?',
    '¿Qué tal va ese código, choom? Más te vale no hacer un flatline en producción.',
  ];

  static const List<String> _pokeReplies = [
    '¡Oye! Deja de picarme, choom.',
    'Pícame una vez más y te borro el caché, gonk.',
    '¡Auch! Qué pesado eres. Soy chiquita, no un botón.',
  ];

  // Frases de caricias (`Head Pats` en `Capri.cs` líneas 1757-1762)
  static const List<String> _headPatReplies = [
    'Je. Vale, te lo permito, choom.',
    'Caricias registradas. Moral del sistema +12%.',
    '¿Caricias en mi cromo? Qué atrevido, choom.',
    'Vale, eso se siente bien. No se lo cuentes a nadie.',
    'Cuidado con el pelo, me tomó tres parches dejarlo así.',
    'Si empiezo a ronronear en código binario, es tu culpa.',
    'Diez de diez en caricias. Mis ventiladores acaban de encenderse.',
  ];

  AssistantController({WebSocketService? wsService})
      : _wsService = wsService ?? WebSocketService() {
    _init();
  }

  void _init() {
    CapriSfx.instance.preloadDoorSounds().then((_) {
      // Saludo de voz real al arrancar (`hello-morning` / `hello-late` / `hello-miss`)
      Future.delayed(const Duration(milliseconds: 600), () {
        CapriSfx.instance.playGreetingVoice();
      });
    });

    _statusSub = _wsService.onStatusChange.listen((status) {
      _wsStatus = status;
      notifyListeners();
    });

    _eventSub = _wsService.onEvent.listen(_handleEvent);

    // Iniciar conexión WebSocket
    _wsService.connect();
  }

  void _handleEvent(AssistantEvent event) {
    switch (event.event) {
      case 'change_state':
        if (event.state != null) {
          changeState(event.state!, notifyBackend: false, force: true);
        }
        break;

      case 'say':
      case 'speak':
        if (event.text != null && event.text!.isNotEmpty) {
          final userEcho = event.payload['user_text']?.toString();
          final audioB64 = event.payload['audio_b64']?.toString();
          final priority = (event.payload['priority'] ?? 'normal').toString();
          final targetState = (event.state != null &&
                  event.state != AssistantState.thinking &&
                  event.state != AssistantState.listening &&
                  event.state != AssistantState.idle)
              ? event.state!
              : AssistantState.speaking;

          _enqueueOrDisplaySpeech(
            _QueuedSpeechItem(
              text: event.text!,
              targetState: targetState,
              userEcho: userEcho,
              audioB64: audioB64,
              priority: priority,
            ),
          );
        }
        break;

      case 'voice_audio':
        final audioB64 = event.payload['audio_b64']?.toString();
        if (audioB64 != null &&
            audioB64.isNotEmpty &&
            _isTtsEnabled &&
            _currentState != AssistantState.listening) {
          final playedDur = CapriSfx.instance.playVoiceBase64(audioB64);
          if (playedDur > Duration.zero) {
            final minVoiceDur = playedDur + const Duration(milliseconds: 900);
            final displayTxt = _currentSpeechText ?? event.text ?? '';
            if (displayTxt.isNotEmpty) {
              showSpeech(displayTxt, duration: minVoiceDur, playPop: false);
            }
            if (_currentState == AssistantState.idle) {
              changeState(AssistantState.speaking, notifyBackend: false, force: true);
            }
          }
        }
        break;

      case 'voice_listening':
        _isListeningMic = event.payload['listening'] == true;
        if (_isListeningMic) {
          changeState(AssistantState.listening, notifyBackend: false);
        }
        notifyListeners();
        break;

      case 'voice_transcript':
        final tr = event.payload['text']?.toString();
        if (tr != null && tr.isNotEmpty) {
          _lastUserMessage = tr;
          notifyListeners();
        }
        break;

      case 'voice_status':
        if (event.payload['tts_enabled'] is bool) {
          _isTtsEnabled = event.payload['tts_enabled'] as bool;
          CapriSfx.instance.blipsEnabled = !_isTtsEnabled;
        }
        if (event.payload['continuous_call'] is bool) {
          _isContinuousVoiceCall = event.payload['continuous_call'] as bool;
        }
        if (event.payload['listening'] is bool) {
          _isListeningMic = event.payload['listening'] as bool;
        }
        notifyListeners();
        break;

      case 'play_animation':
        final animName = event.payload['animation']?.toString();
        if (animName != null) {
          final state = AssistantState.fromString(animName);
          changeState(state, notifyBackend: false, force: true);
        }
        break;

      case 'mini':
        final enabled = event.payload['enabled'];
        if (enabled is bool) {
          setMiniMode(enabled, notifyBackend: false);
        } else {
          toggleMiniMode(notifyBackend: false);
        }
        break;

      case 'posture':
        final pos = (event.payload['posture'] ?? '').toString().toLowerCase();
        if (pos == 'lay' || pos == 'lying') {
          setPosture(CapriPosture.lying, notifyBackend: false);
        } else if (pos == 'perch' || pos == 'sitting') {
          setPosture(CapriPosture.perched, notifyBackend: false);
        } else {
          setPosture(CapriPosture.standing, notifyBackend: false);
        }
        break;

      case 'skin':
        final skinId = event.payload['skin']?.toString();
        setSkin(CapriVisualSkin.fromId(skinId), notifyBackend: false);
        break;

      case 'media_state':
        final rawTune = event.payload['tune'];
        if (rawTune is Map) {
          final map = Map<String, dynamic>.from(rawTune);
          final prevPlaying = _currentTune.playing;
          _currentTune = MediaTuneState.fromMap(map);
          if (_currentTune.playing && !prevPlaying) {
            _isMiniPlayerOpen = true;
          }
          notifyListeners();
        }
        break;

      case 'dance':
        final enabled = event.payload['enabled'];
        _manualDancing = enabled is bool ? enabled : !_manualDancing;
        notifyListeners();
        break;

      case 'open_minigame':
        final g = (event.payload['game'] ?? 'tic_tac_toe').toString();
        openMiniGame(g);
        break;

      case 'move_to':
        final x = (event.payload['x'] as num?)?.toDouble();
        final y = (event.payload['y'] as num?)?.toDouble();
        if (x != null && y != null) {
          CapriSfx.instance.play('charge');
          windowManager.setPosition(Offset(x, y));
        }
        break;

      case 'game_autopilot':
        _isGameAutopilotActive = event.payload['active'] == true;
        notifyListeners();
        break;

      case 'gamesense':
        _isGameSenseEnabled = event.payload['enabled'] == true;
        notifyListeners();
        break;

      case 'lookout_update':
        final rawW = event.payload['watches'];
        if (rawW is List) {
          _activeWatches = rawW.whereType<Map>().map((m) => Map<String, dynamic>.from(m)).toList();
          notifyListeners();
        }
        break;

      case 'lookout_alert':
        CapriSfx.instance.play('charge');
        break;

      case 'reminders_update':
        final rawR = event.payload['pending'];
        if (rawR is List) {
          _pendingReminders = rawR.whereType<Map>().map((m) => Map<String, dynamic>.from(m)).toList();
          notifyListeners();
        }
        break;

      case 'reminder_due':
        CapriSfx.instance.play('wake');
        break;

      case 'clones':
        final rawC = event.payload['clones'];
        if (rawC is List) {
          _activeClones = rawC.whereType<Map>().map((m) => Map<String, dynamic>.from(m)).toList();
        }
        if (event.payload['hologram'] is bool) {
          _isHologramEnabled = event.payload['hologram'] as bool;
          try {
            windowManager.setIgnoreMouseEvents(_isHologramEnabled);
          } catch (_) {}
        }
        notifyListeners();
        break;

      case 'hologram':
        if (event.payload['enabled'] is bool) {
          _isHologramEnabled = event.payload['enabled'] as bool;
          try {
            windowManager.setIgnoreMouseEvents(_isHologramEnabled);
          } catch (_) {}
          notifyListeners();
        }
        break;

      case 'brain_status':
        final rawStatus = event.payload['status'];
        if (rawStatus is Map) {
          _brainStatus = BrainConfigState.fromMap(Map<String, dynamic>.from(rawStatus));
          notifyListeners();
        }
        break;

      case 'mute':
        final muted = event.payload['muted'] == true;
        _isMuted = muted;
        CapriSfx.instance.isMuted = _isMuted;
        notifyListeners();
        break;

      default:
        if (event.state != null) {
          changeState(event.state!, notifyBackend: false);
        }
    }
  }

  /// Cambia el estado actual del asistente.
  void changeState(AssistantState newState, {bool notifyBackend = false, bool force = false}) {
    if (!force && _currentState == newState) return;

    if (newState == AssistantState.sleeping) {
      CapriSfx.instance.play('sleep');
    } else if (_currentState == AssistantState.sleeping && newState != AssistantState.sleeping) {
      CapriSfx.instance.play('wake');
    } else if (newState == AssistantState.teleporting) {
      CapriSfx.instance.play('charge');
    }

    _currentState = newState;
    notifyListeners();

    if (notifyBackend) {
      _wsService.sendEvent(AssistantEvent(
        event: 'state_changed',
        state: newState,
      ));
    }
  }

  /// Cambia la skin o motor de renderizado activo (`shaderRig`, `capriSprites`, `watcherSprites`).
  void setSkin(CapriVisualSkin skin, {bool notifyBackend = true}) {
    if (_currentSkin == skin) return;
    _currentSkin = skin;
    CapriSfx.instance.play('rebuild');
    notifyListeners();

    if (notifyBackend) {
      _wsService.sendEvent(AssistantEvent(
        event: 'skin_changed',
        payload: {'skin': skin.id},
      ));
    }
  }

  /// Cambia la postura en escritorio (`standing`, `perched`, `lying`).
  void setPosture(CapriPosture posture, {bool notifyBackend = true}) {
    _currentPosture = posture;
    if (posture == CapriPosture.perched) {
      changeState(AssistantState.sitting, notifyBackend: false);
    } else if (_currentState == AssistantState.sitting) {
      changeState(AssistantState.idle, notifyBackend: false);
    }
    notifyListeners();

    if (notifyBackend) {
      _wsService.sendEvent(AssistantEvent(
        event: 'posture_changed',
        payload: {'posture': posture.name},
      ));
    }
  }

  /// Activa o desactiva el modo Mini Chibi (`assets/desk/mini/`).
  void toggleMiniMode({bool notifyBackend = true}) {
    setMiniMode(!_isMiniMode, notifyBackend: notifyBackend);
  }

  void setMiniMode(bool value, {bool notifyBackend = true}) {
    if (_isMiniMode == value) return;
    _isMiniMode = value;
    CapriSfx.instance.play(value ? 'sleep' : 'wake');
    notifyListeners();

    if (notifyBackend) {
      _wsService.sendEvent(AssistantEvent(
        event: 'mini_changed',
        payload: {'enabled': _isMiniMode},
      ));
    }
  }

  /// Alterna el Cyberpunk Mini Player (`Player.cs`).
  void toggleMiniPlayer() {
    _isMiniPlayerOpen = !_isMiniPlayerOpen;
    CapriSfx.instance.play('pop');
    notifyListeners();
  }

  void closeMiniPlayer() {
    _isMiniPlayerOpen = false;
    notifyListeners();
  }

  /// Alterna el baile al ritmo de la música (`perch_music.png` / `dance.png`).
  void toggleDancing() {
    _manualDancing = !_manualDancing;
    CapriSfx.instance.play('pop');
    notifyListeners();
  }

  /// Envía un comando multimedia (`play`, `pause`, `toggle`, `next`, `previous`, `like`, `vol_up`, `vol_down`, `seek`).
  void sendMediaCommand(String action, [String arg = '']) {
    if (_wsStatus == WsConnectionStatus.connected) {
      _wsService.sendEvent(AssistantEvent(
        event: 'media_command',
        payload: {'action': action, 'arg': arg},
      ));
    } else {
      // Simulación local si el backend está offline
      if (action == 'toggle' || action == 'play' || action == 'pause') {
        final nextPlay = action == 'play' ? true : (action == 'pause' ? false : !_currentTune.playing);
        _currentTune = MediaTuneState(
          title: _currentTune.hasTrack ? _currentTune.title : 'I Really Want to Stay at Your House',
          artist: _currentTune.hasTrack ? _currentTune.artist : 'Rosa Walton • Night City Radio',
          app: _currentTune.hasTrack ? _currentTune.app : 'CyberDeck',
          playing: nextPlay,
          liked: _currentTune.liked,
          position: _currentTune.position,
          length: _currentTune.length,
        );
        notifyListeners();
      } else if (action == 'like') {
        _currentTune = MediaTuneState(
          title: _currentTune.title,
          artist: _currentTune.artist,
          app: _currentTune.app,
          playing: _currentTune.playing,
          liked: !_currentTune.liked,
          position: _currentTune.position,
          length: _currentTune.length,
        );
        notifyListeners();
      }
    }
  }

  /// Abre el tablero de un minijuego (`tic_tac_toe`, `connect_four`, `rock_paper_scissors`).
  void openMiniGame([String gameKind = 'tic_tac_toe']) {
    _activeMiniGame = gameKind;
    _isMiniGameOpen = true;
    CapriSfx.instance.play('pop');
    notifyListeners();
  }

  void closeMiniGame() {
    _isMiniGameOpen = false;
    notifyListeners();
  }

  /// Pide al backend buscar una ventana abierta (`Ledges.cs`) y sentar a Capri en su borde superior.
  void requestPerchOnWindow() {
    setPosture(CapriPosture.perched, notifyBackend: true);
    if (_wsStatus == WsConnectionStatus.connected) {
      _wsService.sendEvent(AssistantEvent(event: 'perch_window'));
    } else {
      showSpeech('Me senté aquí mismo, choom. Conecta el backend para saltar entre tus ventanas abiertas.');
    }
  }

  /// Inicia o detiene el piloto automático en un videojuego (`Play.cs`).
  void triggerGameAutopilot(String mode) {
    if (_wsStatus == WsConnectionStatus.connected) {
      _wsService.sendEvent(AssistantEvent(
        event: 'game_autopilot',
        payload: {'mode': mode},
      ));
    } else {
      showSpeech('Necesito el servidor Python activo para enviar teclas y ratón a tu juego, choom.');
    }
  }

  /// Activa o desactiva GameSense (`GameSense.cs`).
  void toggleGameSense() {
    if (_wsStatus == WsConnectionStatus.connected) {
      _wsService.sendEvent(AssistantEvent(event: 'gamesense_toggle'));
    } else {
      _isGameSenseEnabled = !_isGameSenseEnabled;
      showSpeech('GameSense requiere el servidor Python conectado para analizar la pantalla.');
      notifyListeners();
    }
  }

  /// Abre o cierra el panel de configuración del Cerebro IA (`CapriBrainPanel`).
  void toggleBrainPanel() {
    _isBrainPanelOpen = !_isBrainPanelOpen;
    if (_isBrainPanelOpen) {
      _isMiniGameOpen = false;
      _isChatOpen = false;
      if (_wsStatus == WsConnectionStatus.connected) {
        _wsService.sendEvent(AssistantEvent(event: 'get_brain_status'));
      }
    }
    CapriSfx.instance.play('pop');
    notifyListeners();
  }

  void closeBrainPanel() {
    if (!_isBrainPanelOpen) return;
    _isBrainPanelOpen = false;
    notifyListeners();
  }

  /// Guarda la configuración del Cerebro IA en el backend (`configure_brain`).
  void saveBrainConfig({
    required String provider,
    String? apiKey,
    required String model,
    required String userName,
    required bool followUpsEnabled,
    required bool proactiveGlances,
  }) {
    _isBrainPanelOpen = false;
    notifyListeners();
    if (_wsStatus == WsConnectionStatus.connected) {
      final payload = <String, dynamic>{
        'provider': provider,
        'model': model,
        'user_name': userName,
        'follow_ups_enabled': followUpsEnabled,
        'proactive_glances': proactiveGlances,
      };
      if (apiKey != null && apiKey.isNotEmpty) {
        payload['api_key'] = apiKey;
      }
      _wsService.sendEvent(AssistantEvent(
        event: 'configure_brain',
        payload: payload,
      ));
    } else {
      showSpeech('Arranca backend_test_server.py para activar el enlace neuronal en la nube o con Ollama.');
    }
  }

  /// Pide a Capri que capture y comente la pantalla actual con visión real (`screen_glance`).
  void requestScreenGlance([String focus = '']) {
    _isBrainPanelOpen = false;
    notifyListeners();
    if (_wsStatus == WsConnectionStatus.connected) {
      _wsService.sendEvent(AssistantEvent(
        event: 'screen_glance',
        payload: {'focus': focus},
      ));
    } else {
      showSpeech('Conecta el backend en Python para que pueda ver tu pantalla en tiempo real, choom.');
    }
  }

  /// Envía un evento en vivo de minijuego al Cerebro IA para que Capri comente la partida (`Commentary.cs`).
  void notifyMiniGameEvent(String detail) {
    if (_wsStatus == WsConnectionStatus.connected) {
      _wsService.sendEvent(AssistantEvent(
        event: 'minigame_event',
        payload: {'detail': detail},
      ));
    }
  }

  /// Dispara la reacción de caricias (`Head Pats` en `Capri.cs`) cuando frotas el cursor sobre su cabeza.
  void onHeadPatted() {
    final now = DateTime.now();
    // Evitar interrumpir a Capri si está pensando, escuchando, hablando por voz o en enfriamiento
    if (_currentState == AssistantState.thinking ||
        _currentState == AssistantState.listening ||
        CapriSfx.instance.isVoicePlaying ||
        now.difference(_lastHeadPatAt).inMilliseconds < 3500) {
      return;
    }
    _lastHeadPatAt = now;
    CapriSfx.instance.play('coin');
    final line = _headPatReplies[_rng.nextInt(_headPatReplies.length)];
    _enqueueOrDisplaySpeech(
      _QueuedSpeechItem(
        text: line,
        targetState: AssistantState.victory,
        priority: 'low',
      ),
    );
  }

  /// Notifica el inicio o fin del arrastre del personaje (`dangle.png`).
  void setDragging(bool dragging) {
    if (_isDragging == dragging) return;
    _isDragging = dragging;
    CapriSfx.instance.play(dragging ? 'grab' : 'thud');
    notifyListeners();
  }

  /// Abre o cierra el menú de la puerta Cyberpunk (`assets/desk/door/`).
  void setDoorMenuOpen(bool open) {
    if (_isDoorMenuOpen == open) return;
    _isDoorMenuOpen = open;
    notifyListeners();
  }

  /// Abre la caja de chat estilo videollamada (`bubble.py`).
  void openChatBox() {
    _isChatOpen = true;
    _speechBubbleTimer?.cancel();
    CapriSfx.instance.play('pop');
    notifyListeners();
  }

  /// Cierra la caja de chat y oculta el bocadillo.
  void closeChatBox() {
    _isChatOpen = false;
    dismissSpeech();
  }

  /// Dispara la respuesta de enfado cuando el usuario pica 3 veces a Mini Capri.
  void onMiniPoked() {
    if (_currentState == AssistantState.thinking ||
        _currentState == AssistantState.listening ||
        CapriSfx.instance.isVoicePlaying) {
      return;
    }
    final line = _pokeReplies[_rng.nextInt(_pokeReplies.length)];
    _enqueueOrDisplaySpeech(
      _QueuedSpeechItem(
        text: line,
        targetState: AssistantState.speaking,
        priority: 'low',
      ),
    );
  }

  /// Envía un mensaje escrito por el usuario al backend (o responde localmente si está desconectado).
  void sendUserMessage(String rawText) {
    final text = rawText.trim();
    if (text.isEmpty) return;

    _speechBubbleTimer?.cancel();
    _speechQueue.clear();
    _speechBusyUntil = DateTime.fromMillisecondsSinceEpoch(0);
    _currentSpeechText = null;
    _lastUserMessage = text;
    _isChatOpen = false;
    changeState(AssistantState.thinking, notifyBackend: false, force: true);
    notifyListeners();

    if (_wsStatus == WsConnectionStatus.connected) {
      _wsService.sendEvent(AssistantEvent(
        event: 'user_message',
        text: text,
        payload: {'text': text},
      ));
      return;
    }

    // Fallback inteligente local cuando el servidor Python no está conectado
    Future.delayed(const Duration(milliseconds: 380), () {
      final lower = text.toLowerCase();
      if (lower.contains('mini') || lower.contains('pequeña') || lower.contains('chibi')) {
        setMiniMode(true, notifyBackend: false);
        showSpeech('Modo mini activado. Chiquita pero peligrosa, choom.');
      } else if (lower.contains('grande') || lower.contains('normal')) {
        setMiniMode(false, notifyBackend: false);
        showSpeech('De vuelta a tamaño completo. ¡Preem!');
      } else if (lower.contains('conecta 4') || lower.contains('connect')) {
        openMiniGame('connect_four');
        showSpeech('¡Vamos a jugar Conecta 4, choom!');
      } else if (lower.contains('tres en raya') || lower.contains('gato') || lower.contains('tic')) {
        openMiniGame('tic_tac_toe');
        showSpeech('¡Acepto el reto de Tres en Raya!');
      } else if (lower.contains('piedra') || lower.contains('tijera')) {
        openMiniGame('rock_paper_scissors');
        showSpeech('¡Piedra, Papel o Tijera al mejor de 3!');
      } else if (lower.contains('baila') || lower.contains('música') || lower.contains('musica')) {
        _manualDancing = true;
        _isMiniPlayerOpen = true;
        showSpeech('¡Subiendo el ritmo! Mira cómo me muevo con este beat.');
      } else if (lower.contains('acuéstate') || lower.contains('túmbate') || lower.contains('lie down')) {
        setPosture(CapriPosture.lying, notifyBackend: false);
        showSpeech('Qué cómoda está tu barra de tareas, choom.');
      } else if (lower.contains('siéntate') || lower.contains('sit')) {
        setPosture(CapriPosture.perched, notifyBackend: false);
        showSpeech('Esta ventana es mía ahora.');
      } else if (lower.contains('duerme') || lower.contains('sleep')) {
        changeState(AssistantState.sleeping, notifyBackend: false, force: true);
        showSpeech('Buenas noches, gonk. No hagas un flatline sin mí.');
        return;
      } else if (lower.contains('teletrans') || lower.contains('zap')) {
        changeState(AssistantState.teleporting, notifyBackend: false, force: true);
        return;
      } else {
        final reply = _offlineReplies[_rng.nextInt(_offlineReplies.length)];
        showSpeech(reply);
      }
      changeState(AssistantState.speaking, notifyBackend: false);
    });
  }

  /// Notificado cuando una animación de un solo disparo (ej. Teleporting) finaliza su ciclo.
  void onAnimationCompleted() {
    final config = SpriteRegistry.getConfig(_currentState);
    if (!config.loop && config.nextStateOnComplete != null) {
      changeState(config.nextStateOnComplete!, notifyBackend: true);
    }
  }

  /// Inicia o detiene la escucha por micrófono (`voice_listen_toggle` -> Groq Whisper STT).
  void toggleVoiceListen() {
    if (_wsStatus != WsConnectionStatus.connected) {
      showSpeech('Conecta backend_test_server.py para hablarme por micrófono con Groq Whisper, choom.');
      return;
    }
    // Si Capri estaba hablando, detener su audio para escuchar inmediatamente al usuario
    if (CapriSfx.instance.isVoicePlaying) {
      CapriSfx.instance.stopAllAudio();
    }
    _wsService.sendEvent(AssistantEvent(event: 'voice_listen_toggle'));
  }

  /// Activa o desactiva el modo Llamada de Voz Continua Manos Libres (`Talk.cs`).
  void toggleContinuousVoiceCall() {
    if (_wsStatus != WsConnectionStatus.connected) {
      showSpeech('Conecta el servidor Python para iniciar una llamada de voz continua.');
      return;
    }
    _isContinuousVoiceCall = !_isContinuousVoiceCall;
    if (!_isContinuousVoiceCall && CapriSfx.instance.isVoicePlaying) {
      CapriSfx.instance.stopAllAudio();
    }
    notifyListeners();
    _wsService.sendEvent(AssistantEvent(
      event: 'voice_call_toggle',
      payload: {'enabled': _isContinuousVoiceCall},
    ));
  }

  /// Activa o desactiva la síntesis de voz hablada de Capri (`TTS`).
  void toggleTtsVoice() {
    _isTtsEnabled = !_isTtsEnabled;
    CapriSfx.instance.blipsEnabled = !_isTtsEnabled;
    if (!_isTtsEnabled) {
      CapriSfx.instance.stopAllAudio();
    }
    notifyListeners();
    if (_wsStatus == WsConnectionStatus.connected) {
      _wsService.sendEvent(AssistantEvent(
        event: 'voice_tts_toggle',
        payload: {'enabled': _isTtsEnabled},
      ));
    }
  }

  void _enqueueOrDisplaySpeech(_QueuedSpeechItem item) {
    final now = DateTime.now();
    final isCurrentlyBusy = _currentSpeechText != null &&
        _currentState != AssistantState.thinking &&
        _currentState != AssistantState.listening &&
        (now.isBefore(_speechBusyUntil) || CapriSfx.instance.isVoicePlaying);

    if (item.priority == 'high' || !isCurrentlyBusy) {
      if (item.priority == 'high') {
        _speechQueue.removeWhere((q) => q.priority == 'low');
      }
      _playSpeechItem(item);
      return;
    }

    // Si es de baja prioridad y ya hay mensajes esperando, descartarlo para no saturar
    if (item.priority == 'low' && _speechQueue.isNotEmpty) {
      return;
    }
    if (_speechQueue.any((q) => q.text == item.text)) {
      return;
    }
    if (_speechQueue.length < 3) {
      _speechQueue.add(item);
    }
  }

  void _playSpeechItem(_QueuedSpeechItem item) {
    if (item.userEcho != null && item.userEcho!.isNotEmpty) {
      _lastUserMessage = item.userEcho;
    }
    Duration? minVoiceDur;
    final hasInlineAudio = item.audioB64 != null && item.audioB64!.isNotEmpty && _isTtsEnabled;
    if (hasInlineAudio) {
      final playedDur = CapriSfx.instance.playVoiceBase64(item.audioB64!);
      if (playedDur > Duration.zero) {
        minVoiceDur = playedDur + const Duration(milliseconds: 900);
      }
    }
    changeState(item.targetState, notifyBackend: false, force: true);
    showSpeech(item.text, duration: minVoiceDur, playPop: !hasInlineAudio);
  }

  /// Muestra un bocadillo de diálogo flotante y programa su cierre o paso al siguiente mensaje en cola.
  void showSpeech(String text, {Duration? duration, bool playPop = true}) {
    _speechBubbleTimer?.cancel();
    final isNewText = _currentSpeechText != text;
    _currentSpeechText = text;
    if (playPop && isNewText && !CapriSfx.instance.isVoicePlaying) {
      CapriSfx.instance.play('pop');
    }
    notifyListeners();

    final textTimeMs = (2800 + text.length * 68).clamp(3800, 14000);
    final voiceRemMs = CapriSfx.instance.remainingVoiceDuration.inMilliseconds + 800;
    final reqMs = duration?.inMilliseconds ?? 0;
    final finalMs = math.max(textTimeMs, math.max(voiceRemMs, reqMs));
    _speechBusyUntil = DateTime.now().add(Duration(milliseconds: (finalMs * 0.75).round()));

    _speechBubbleTimer = Timer(Duration(milliseconds: finalMs), () {
      if (_speechQueue.isNotEmpty && !_isChatOpen) {
        final nextItem = _speechQueue.removeAt(0);
        _playSpeechItem(nextItem);
        return;
      }
      if (!_isChatOpen) {
        _currentSpeechText = null;
        if (_currentState == AssistantState.speaking ||
            _currentState == AssistantState.victory ||
            _currentState == AssistantState.point) {
          changeState(
            _currentPosture == CapriPosture.perched ? AssistantState.sitting : AssistantState.idle,
            notifyBackend: false,
          );
        } else {
          notifyListeners();
        }
      }
    });
  }

  /// Cierra manualmente el bocadillo de diálogo y limpia la cola pendiente.
  void dismissSpeech() {
    _speechBubbleTimer?.cancel();
    _speechQueue.clear();
    _speechBusyUntil = DateTime.fromMillisecondsSinceEpoch(0);
    if (_currentSpeechText != null || _isChatOpen) {
      _currentSpeechText = null;
      _isChatOpen = false;
      if (_currentState == AssistantState.speaking) {
        changeState(
          _currentPosture == CapriPosture.perched ? AssistantState.sitting : AssistantState.idle,
          notifyBackend: false,
        );
      } else {
        notifyListeners();
      }
    }
  }

  /// Alterna el estado de silencio (Mute) y notifica al backend.
  void toggleMute() {
    _isMuted = !_isMuted;
    CapriSfx.instance.isMuted = _isMuted;
    if (!_isMuted) {
      CapriSfx.instance.play('key');
    }
    notifyListeners();

    _wsService.sendEvent(AssistantEvent(
      event: 'mute_toggle',
      payload: {'muted': _isMuted},
    ));
  }

  /// Fuerza un intento de reconexión manual al WebSocket.
  void reconnectWebSocket() {
    _wsService.connect();
  }

  // --- Nuevas funciones (Lookout, Reminders, Clones, Hologram) ---

  void addLookoutWatch(String text, {bool repeat = false}) {
    CapriSfx.instance.play('charge');
    _wsService.sendEvent(AssistantEvent(
      event: 'lookout_watch',
      payload: {'text': text, 'repeat': repeat},
    ));
  }

  void stopLookoutWatch(String search) {
    CapriSfx.instance.play('blip');
    _wsService.sendEvent(AssistantEvent(
      event: 'lookout_stop',
      payload: {'search': search},
    ));
  }

  void addDatedReminder(String text) {
    CapriSfx.instance.play('charge');
    _wsService.sendEvent(AssistantEvent(
      event: 'reminder_add',
      payload: {'text': text},
    ));
  }

  void cancelDatedReminder(String search) {
    CapriSfx.instance.play('blip');
    _wsService.sendEvent(AssistantEvent(
      event: 'reminder_cancel',
      payload: {'search': search},
    ));
  }

  void spawnClones([int count = 3]) {
    CapriSfx.instance.play('charge');
    _wsService.sendEvent(AssistantEvent(
      event: 'clones_spawn',
      payload: {'count': count, 'skin': _currentSkin.id},
    ));
  }

  void clearClones() {
    CapriSfx.instance.play('pop');
    _wsService.sendEvent(AssistantEvent(
      event: 'clones_clear',
      payload: const {},
    ));
  }

  void toggleHologram() {
    CapriSfx.instance.play('blip');
    _wsService.sendEvent(AssistantEvent(
      event: 'hologram_toggle',
      payload: {'enabled': !_isHologramEnabled},
    ));
  }

  @override
  void dispose() {
    _speechBubbleTimer?.cancel();
    _eventSub?.cancel();
    _statusSub?.cancel();
    _wsService.dispose();
    super.dispose();
  }
}
