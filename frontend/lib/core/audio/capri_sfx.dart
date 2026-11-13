// Procedural sound synthesizer & WAV audio engine ported from Capri-cmd/capri-ai
// (capri/desk/sfx.py).
// Uses pure Dart PCM WAV synthesis + Windows winmm.dll PlaySoundW via dart:ffi
// (zero external plugin dependencies).

import 'dart:convert' show base64Decode;
import 'dart:ffi' as ffi;
import 'dart:io' show Platform;
import 'dart:math' as math;
import 'dart:typed_data';
import 'package:flutter/services.dart' show rootBundle;

typedef _LocalAllocNative = ffi.Pointer<ffi.Uint8> Function(ffi.Uint32 uFlags, ffi.IntPtr uBytes);
typedef _LocalAllocDart = ffi.Pointer<ffi.Uint8> Function(int uFlags, int uBytes);

typedef _PlaySoundNative = ffi.Int32 Function(
  ffi.Pointer<ffi.Uint8> pszSound,
  ffi.IntPtr hmod,
  ffi.Uint32 fdwSound,
);
typedef _PlaySoundDart = int Function(
  ffi.Pointer<ffi.Uint8> pszSound,
  int hmod,
  int fdwSound,
);

class CapriSfx {
  CapriSfx._();
  static final CapriSfx instance = CapriSfx._();

  static const int sampleRate = 44100;
  static const double masterVolume = 0.55;

  // Flags para PlaySoundW: SND_ASYNC (0x0001) | SND_NODEFAULT (0x0002) | SND_MEMORY (0x0004)
  static const int _sndMemoryAsync = 0x0007;
  static const int _nativeBufSize = 512 * 1024; // 512 KB para SFX cortos
  static const int _voiceBufSize = 8 * 1024 * 1024; // 8 MB dedicados para voz hablada (TTS y saludos)

  bool isMuted = false;
  bool blipsEnabled = false;
  int _blipCounter = 0;
  DateTime _lastBlipAt = DateTime.fromMillisecondsSinceEpoch(0);
  DateTime _voiceBusyUntil = DateTime.fromMillisecondsSinceEpoch(0);

  final Map<String, Uint8List> _wavCache = {};
  bool _doorWavsLoaded = false;

  _PlaySoundDart? _playSound;
  final List<ffi.Pointer<ffi.Uint8>> _sfxRingBuffers = [];
  int _sfxRingIdx = 0;
  final List<ffi.Pointer<ffi.Uint8>> _voiceRingBuffers = [];
  int _voiceRingIdx = 0;
  bool _ffiInitialized = false;

  /// Indica si Capri está hablando o riéndose con su voz real en este instante.
  bool get isVoicePlaying => DateTime.now().isBefore(_voiceBusyUntil);

  /// Tiempo restante estimado de la línea de voz actual.
  Duration get remainingVoiceDuration {
    final diff = _voiceBusyUntil.difference(DateTime.now());
    return diff.isNegative ? Duration.zero : diff;
  }

  void _ensureFfi() {
    if (_ffiInitialized) return;
    _ffiInitialized = true;
    try {
      if (!Platform.isWindows) return;
      final kernel32 = ffi.DynamicLibrary.open('kernel32.dll');
      final winmm = ffi.DynamicLibrary.open('winmm.dll');

      final localAlloc = kernel32.lookupFunction<_LocalAllocNative, _LocalAllocDart>('LocalAlloc');
      _playSound = winmm.lookupFunction<_PlaySoundNative, _PlaySoundDart>('PlaySoundW');
      // LMEM_FIXED = 0x0000: 4 buffers rotativos para SFX y 2 para Voz, evitando pisar memoria activa en winmm.dll
      for (int i = 0; i < 4; i++) {
        final ptr = localAlloc(0, _nativeBufSize);
        if (ptr != ffi.nullptr) _sfxRingBuffers.add(ptr);
      }
      for (int i = 0; i < 2; i++) {
        final ptr = localAlloc(0, _voiceBufSize);
        if (ptr != ffi.nullptr) _voiceRingBuffers.add(ptr);
      }
    } catch (_) {
      _playSound = null;
      _sfxRingBuffers.clear();
      _voiceRingBuffers.clear();
    }
  }

  /// Calcula la duración en milisegundos de un WAV PCM leyendo su cabecera RIFF.
  int _estimateWavDurationMs(Uint8List wavBytes) {
    if (wavBytes.lengthInBytes < 44) return 800;
    try {
      final bd = ByteData.sublistView(wavBytes, 0, 44);
      final byteRate = bd.getUint32(28, Endian.little);
      if (byteRate > 0) {
        final dataLen = math.max(0, wavBytes.lengthInBytes - 44);
        return ((dataLen * 1000) / byteRate).round().clamp(300, 60000);
      }
    } catch (_) {}
    // Fallback asumiendo 24kHz 16-bit mono (48000 bytes/s)
    return ((wavBytes.lengthInBytes - 44) * 1000 ~/ 48000).clamp(400, 30000);
  }

  /// Precarga los archivos WAV reales de la puerta (`assets/desk/door/sfx/`) y los saludos de voz (`assets/desk/voice/`).
  Future<void> preloadDoorSounds() async {
    if (_doorWavsLoaded) return;
    _doorWavsLoaded = true;
    for (final name in const ['door_open', 'door_close']) {
      try {
        final data = await rootBundle.load('assets/desk/door/sfx/$name.wav');
        _wavCache[name] = data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes);
      } catch (_) {}
    }
    for (final voiceName in const ['hello-morning', 'hello-late', 'hello-miss']) {
      try {
        final data = await rootBundle.load('assets/desk/voice/$voiceName.wav');
        _wavCache[voiceName] = data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes);
      } catch (_) {}
    }
  }

  /// Reproduce el saludo de voz real de Capri según la hora del día (`lachydotmcg/capri-desktop`)
  /// protegiéndolo para que ningún `pop` o `blip` lo corte a la mitad.
  void playGreetingVoice() {
    if (isMuted) return;
    final hour = DateTime.now().hour;
    final key = (hour >= 5 && hour < 14)
        ? 'hello-morning'
        : ((hour >= 22 || hour < 5) ? 'hello-late' : 'hello-miss');
    final wav = _wavCache[key];
    if (wav != null && wav.isNotEmpty) {
      playVoiceWavBytes(wav);
    } else {
      play('wake');
    }
  }

  /// Reproduce un clip WAV de voz hablada (saludo o síntesis TTS del backend) en el buffer de voz dedicado
  /// y bloquea los SFX secundarios (`blip`, `pop`) mientras dura la locución.
  Duration playVoiceWavBytes(Uint8List wavBytes) {
    if (isMuted || wavBytes.isEmpty) return Duration.zero;
    _ensureFfi();
    final playFn = _playSound;
    if (playFn == null || _voiceRingBuffers.isEmpty) return Duration.zero;
    if (wavBytes.lengthInBytes > _voiceBufSize) return Duration.zero;

    final durMs = _estimateWavDurationMs(wavBytes);
    _voiceBusyUntil = DateTime.now().add(Duration(milliseconds: durMs + 320));

    try {
      _voiceRingIdx = (_voiceRingIdx + 1) % _voiceRingBuffers.length;
      final buf = _voiceRingBuffers[_voiceRingIdx];
      final view = buf.asTypedList(wavBytes.lengthInBytes);
      view.setAll(0, wavBytes);
      playFn(buf, 0, _sndMemoryAsync);
    } catch (_) {}

    return Duration(milliseconds: durMs);
  }

  /// Decodifica un WAV en Base64 enviado por el motor de voz de Python y lo reproduce sin cortes.
  Duration playVoiceBase64(String base64Wav) {
    if (isMuted || base64Wav.isEmpty) return Duration.zero;
    try {
      final bytes = base64Decode(base64Wav);
      return playVoiceWavBytes(bytes);
    } catch (_) {
      return Duration.zero;
    }
  }

  /// Detiene cualquier audio o voz en reproducción inmediata.
  void stopAllAudio() {
    _voiceBusyUntil = DateTime.fromMillisecondsSinceEpoch(0);
    final playFn = _playSound;
    if (playFn != null) {
      try {
        playFn(ffi.nullptr, 0, 0);
      } catch (_) {}
    }
  }

  /// Reproduce un efecto por nombre (`pop`, `grab`, `throw`, `thud`, `sleep`, `wake`, `charge`, `stream`, `rebuild`, `door_open`, `door_close`).
  void play(String name, [String arg = '']) {
    if (isMuted) return;
    // No permitir que efectos de UI (`pop`, `blip`, `key`, `wake`) corten la voz hablada de Capri
    if (isVoicePlaying && name != 'door_open' && name != 'door_close') {
      return;
    }
    final key = arg.isEmpty ? name : '$name:$arg';
    final wav = _wavCache[key] ??= _buildWav(name, arg);
    if (wav.isEmpty) return;
    _playWavBytes(wav);
  }

  /// Reproduce un blip estilo RPG de forma espaciada solo cuando la voz TTS está desactivada.
  /// Se silencia automáticamente cuando Capri habla con su voz real para no saturar winmm.dll.
  void playBlip(String ch) {
    if (isMuted || !blipsEnabled || isVoicePlaying) return;
    final trimmed = ch.trim();
    if (trimmed.isEmpty) return;
    _blipCounter++;
    if (_blipCounter % 3 != 0) return;

    final now = DateTime.now();
    if (now.difference(_lastBlipAt).inMilliseconds < 140) return;
    _lastBlipAt = now;

    final letter = trimmed[0].toLowerCase();
    play('blip', letter);
  }

  void _playWavBytes(Uint8List wavBytes) {
    _ensureFfi();
    final playFn = _playSound;
    if (playFn == null || _sfxRingBuffers.isEmpty || isVoicePlaying) return;
    if (wavBytes.lengthInBytes > _nativeBufSize) return;

    try {
      _sfxRingIdx = (_sfxRingIdx + 1) % _sfxRingBuffers.length;
      final buf = _sfxRingBuffers[_sfxRingIdx];
      final view = buf.asTypedList(wavBytes.lengthInBytes);
      view.setAll(0, wavBytes);
      playFn(buf, 0, _sndMemoryAsync);
    } catch (_) {}
  }

  // ---------- Síntesis Procedural de Sonidos (`capri/desk/sfx.py`) ----------

  static const Map<String, double> _levels = {
    'boom': 0.75,
    'thud': 0.50,
    'crtoff': 0.45,
    'bloop': 0.35,
    'coin': 0.38,
    'stream': 0.35,
    'charge': 0.30,
    'wake': 0.35,
    'sleep': 0.32,
    'rebuild': 0.30,
    'blip': 0.20,
    'pop': 0.22,
    'grab': 0.25,
    'throw': 0.25,
    'tinkle': 0.16,
    'fall': 0.22,
    'tear': 0.30,
    'snore': 0.08,
    'key': 0.07,
  };

  Uint8List _buildWav(String name, String arg) {
    if (_wavCache.containsKey(name) && arg.isEmpty) {
      return _wavCache[name]!;
    }
    final samples = _synth(name, arg);
    if (samples.isEmpty) return Uint8List(0);

    double peak = 0.0;
    for (final s in samples) {
      final a = s.abs();
      if (a > peak) peak = a;
    }
    if (peak < 1e-6) peak = 1.0;

    final baseLevel = _levels[name] ?? 0.30;
    final scale = (baseLevel * masterVolume / 0.55) / peak;

    return _encodePcm16Wav(samples, scale);
  }

  Float32List _synth(String name, String arg) {
    final rng = math.Random((name.hashCode ^ arg.hashCode) & 0x7FFFFFFF);

    switch (name) {
      case 'blip':
        final ch = (arg.isEmpty ? 'a' : arg[0]).toLowerCase();
        final isVowel = 'aeiouáéíóú'.contains(ch);
        final base = isVowel ? 560.0 : 660.0;
        const semis = [0, 2, 4, 5, 7, 9, 12];
        final semi = semis[ch.codeUnitAt(0) % semis.length];
        final f = base * math.pow(2.0, semi / 12.0);
        final s1 = _note(f, 0.055, shape: 'square', attack: 0.002, release: 0.04);
        final s2 = _note(f * 2.0, 0.055, shape: 'tri', attack: 0.002, release: 0.04);
        final out = Float32List(s1.length);
        for (int i = 0; i < out.length; i++) {
          final v = s1[i] * 0.55 + s2[i] * 0.25;
          out[i] = ((v * 10.0).roundToDouble() / 10.0) * 0.6;
        }
        return out;

      case 'pop':
        final s = _sweep(500, 1300, 0.06, shape: 'sine');
        final env = _env(s.length, attack: 0.002, release: 0.04);
        for (int i = 0; i < s.length; i++) {
          s[i] *= env[i] * 0.3;
        }
        return s;

      case 'grab':
        final s = _sweep(400, 900, 0.09, shape: 'square');
        final env = _env(s.length, attack: 0.002, release: 0.06);
        for (int i = 0; i < s.length; i++) {
          s[i] *= env[i] * 0.25;
        }
        return s;

      case 'throw':
        final n = (sampleRate * 0.28).round();
        final raw = Float32List(n);
        for (int i = 0; i < n; i++) {
          raw[i] = rng.nextDouble() * 2.0 - 1.0;
        }
        final lp = _lowpass(raw, 0.3);
        for (int i = 0; i < n; i++) {
          lp[i] *= math.sin(math.pi * i / n) * 0.35;
        }
        return lp;

      case 'thud':
        final s1 = _sweep(220, 55, 0.16, shape: 'sine');
        final e1 = _env(s1.length, attack: 0.001, release: 0.14);
        for (int i = 0; i < s1.length; i++) {
          s1[i] *= e1[i];
        }
        return s1;

      case 'sleep':
        return _cat([
          _note(1047, 0.08, shape: 'tri', release: 0.06),
          _note(880, 0.08, shape: 'tri', release: 0.06),
          _note(698, 0.08, shape: 'tri', release: 0.06),
          _note(523, 0.09, shape: 'tri', release: 0.07),
        ]);

      case 'wake':
        return _cat([
          _note(523, 0.065, shape: 'square', release: 0.05),
          _note(659, 0.065, shape: 'square', release: 0.05),
          _note(784, 0.065, shape: 'square', release: 0.05),
          _note(1047, 0.065, shape: 'square', release: 0.05),
          _note(1568, 0.16, shape: 'tri', release: 0.12),
        ]);

      case 'charge':
        final s1 = _sweep(220, 1400, 0.36, shape: 'saw');
        final s2 = _sweep(440, 2800, 0.36, shape: 'sine');
        final env = _env(s1.length, attack: 0.04, release: 0.05);
        for (int i = 0; i < s1.length; i++) {
          final t = i / sampleRate;
          s1[i] = (s1[i] * 0.35 + s2[i] * 0.25) * (1.0 + 0.35 * math.sin(2 * math.pi * 18 * t)) * env[i];
        }
        return s1;

      case 'rebuild':
        return _cat([
          _note(1319, 0.05, shape: 'square', release: 0.04),
          _note(1047, 0.05, shape: 'square', release: 0.04),
          _note(1568, 0.05, shape: 'square', release: 0.04),
          _note(2093, 0.05, shape: 'square', release: 0.04),
        ]);

      case 'coin':
        return _cat([
          _note(988, 0.07, shape: 'square', release: 0.02),
          _note(1319, 0.36, shape: 'square', release: 0.32),
        ]);

      default:
        return _note(660, 0.05, shape: 'sine');
    }
  }

  static Float32List _env(int n, {double attack = 0.005, double release = 0.08}) {
    final e = Float32List(n);
    for (int i = 0; i < n; i++) {
      e[i] = 1.0;
    }
    final a = math.max(1, (sampleRate * attack).round());
    for (int i = 0; i < a && i < n; i++) {
      e[i] = i / a;
    }
    final r = math.min(n, math.max(1, (sampleRate * release).round()));
    for (int i = 0; i < r; i++) {
      final u = 1.0 - (i / r);
      e[n - r + i] *= u * u;
    }
    return e;
  }

  static Float32List _sweep(double f0, double f1, double sec, {String shape = 'sine', String curve = 'exp'}) {
    final n = math.max(1, (sampleRate * sec).round());
    final out = Float32List(n);
    double ph = 0.0;
    for (int i = 0; i < n; i++) {
      final k = i / n;
      final f = curve == 'exp' ? f0 * math.pow(f1 / f0, k) : f0 + (f1 - f0) * k;
      ph += 2.0 * math.pi * f / sampleRate;
      final double s;
      if (shape == 'square') {
        s = math.sin(ph) >= 0 ? 0.6 : -0.6;
      } else if (shape == 'tri') {
        s = (2.0 / math.pi) * math.asin(math.sin(ph));
      } else if (shape == 'saw') {
        s = 2.0 * ((ph / (2.0 * math.pi)) % 1.0) - 1.0;
      } else {
        s = math.sin(ph);
      }
      out[i] = s;
    }
    return out;
  }

  static Float32List _note(double f, double sec, {String shape = 'square', double attack = 0.003, double? release}) {
    final s = _sweep(f, f, sec, shape: shape, curve: 'lin');
    final env = _env(s.length, attack: attack, release: release ?? sec * 0.7);
    for (int i = 0; i < s.length; i++) {
      s[i] *= env[i];
    }
    return s;
  }

  static Float32List _lowpass(Float32List x, double a) {
    final y = Float32List(x.length);
    double acc = 0.0;
    for (int i = 0; i < x.length; i++) {
      acc += a * (x[i] - acc);
      y[i] = acc;
    }
    return y;
  }

  static Float32List _cat(List<Float32List> parts) {
    int total = 0;
    for (final p in parts) {
      total += p.length;
    }
    final out = Float32List(total);
    int offset = 0;
    for (final p in parts) {
      out.setRange(offset, offset + p.length, p);
      offset += p.length;
    }
    return out;
  }

  static Uint8List _encodePcm16Wav(Float32List samples, double gain) {
    final numSamples = samples.length;
    final dataBytes = numSamples * 2;
    final totalBytes = 44 + dataBytes;
    final bd = ByteData(totalBytes);

    // RIFF header
    bd.setUint8(0, 0x52); // 'R'
    bd.setUint8(1, 0x49); // 'I'
    bd.setUint8(2, 0x46); // 'F'
    bd.setUint8(3, 0x46); // 'F'
    bd.setUint32(4, 36 + dataBytes, Endian.little);
    bd.setUint8(8, 0x57); // 'W'
    bd.setUint8(9, 0x41); // 'A'
    bd.setUint8(10, 0x56); // 'V'
    bd.setUint8(11, 0x45); // 'E'

    // fmt subchunk
    bd.setUint8(12, 0x66); // 'f'
    bd.setUint8(13, 0x6D); // 'm'
    bd.setUint8(14, 0x74); // 't'
    bd.setUint8(15, 0x20); // ' '
    bd.setUint32(16, 16, Endian.little); // PCM chunk size
    bd.setUint16(20, 1, Endian.little); // AudioFormat = 1 (PCM)
    bd.setUint16(22, 1, Endian.little); // NumChannels = 1 (Mono)
    bd.setUint32(24, sampleRate, Endian.little);
    bd.setUint32(28, sampleRate * 2, Endian.little); // ByteRate
    bd.setUint16(32, 2, Endian.little); // BlockAlign
    bd.setUint16(34, 16, Endian.little); // BitsPerSample = 16

    // data subchunk
    bd.setUint8(36, 0x64); // 'd'
    bd.setUint8(37, 0x61); // 'a'
    bd.setUint8(38, 0x74); // 't'
    bd.setUint8(39, 0x61); // 'a'
    bd.setUint32(40, dataBytes, Endian.little);

    for (int i = 0; i < numSamples; i++) {
      final v = (samples[i] * gain).clamp(-1.0, 1.0);
      final pcm = (v * 32767.0).round();
      bd.setInt16(44 + i * 2, pcm, Endian.little);
    }

    return bd.buffer.asUint8List();
  }
}

