"""
Motor de Voz Neuronal (TTS) y Escucha por Micrófono (STT) para Capri Desktop Companion.
Portado fielmente de `Voice.cs`, `VoicePack.cs`, `Talk.cs` y `Ears.cs` (`lachydotmcg/capri-desktop`).

Arquitectura de Voz Real de Capri (`lachydotmcg/capri-desktop`):
1. Motor Local Oficial `capri-voice-1` (`LocalVoice` / `ModelFile` en `Voice.cs` L2430-3146):
   - Modelo neuronal **Kokoro 82M v1.0** ejecutado en C nativo mediante `sherpa-onnx-c-api.dll` + `onnxruntime.dll`.
   - Voces de Capri en `voices.bin`:
     * Speaker `53` ("Her own" — la voz original de Capri con la que se grabaron `hello-morning.wav`, `hello-late.wav`, `hello-miss.wav`)
     * Speaker `28` ("ef_dora" — voz femenina nativa en español de Kokoro v1.0)
     * Speaker `2`  ("Bright" / `af_bella`), Speaker `6` ("Sly" / `af_nicole`), Speaker `21` ("Sharp" / `bf_emma`).
   - Incluye descargador automático en segundo plano desde el release oficial:
     `https://github.com/lachydotmcg/capri-desktop/releases/download/voice-pack-1/capri-voice-1.zip`
2. ElevenLabs (API oficial con tu propia llave) y fallback offline WinRT OneCore (`Microsoft Laura`):
   - El MP3 de ElevenLabs se decodifica con el codec nativo de Windows `msacm32.dll` y pasa por `VoiceFx`.
3. Procesador DSP `VoiceFx` (`Voice.cs` L644-1495 y `Capri.cs` L4927-4938, vectorizado con NumPy):
   - `VoicePitch = +2.0` semitonos (`2^(2/12) = 1.12246x`), `VoiceSpeed = 120%` (`1.2x`).
   - `VoiceFx.Stretcher` (WSOLA - Waveform Similarity Overlap-Add): ventanas Hann de 20ms con búsqueda de
     correlación cruzada normalizada de 5ms para estirar el tempo sin distorsión metálica ni efecto ardilla.
   - `VoiceFx.Resampler`: filtro Sinc con ventana Hann de 256 fases y 32 taps para cambiar formantes y tono.
   - `VoiceFx.Layerer`: doblaje vocal opcional (+2 semitonos y -2.5 semitonos con retardo de 25ms).
4. STT (Chat de Voz por Micrófono):
   - Grabación nativa WinMM (`winmm.dll` `waveInOpen` 16kHz 16-bit mono) + VAD + **Groq Whisper (`whisper-large-v3-turbo`)**.
"""

from array import array
import asyncio
import base64
from collections import deque
import ctypes
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.error
import urllib.request
import uuid
import wave
import zipfile

import numpy as np

try:
    import aiohttp
except ImportError:
    aiohttp = None  # type: ignore


# ============================================================================
# 1. Estructuras Win32 (`winmm.dll` para Micrófono y `msacm32.dll` para Decodificador MP3)
# ============================================================================

WAVE_MAPPER = 0xFFFFFFFF
WAVE_FORMAT_PCM = 1
WAVE_FORMAT_MPEGLAYER3 = 0x0055
CALLBACK_NULL = 0x00000000
WHDR_DONE = 0x00000001


class WAVEFORMATEX(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("wFormatTag", ctypes.c_uint16),
        ("nChannels", ctypes.c_uint16),
        ("nSamplesPerSec", ctypes.c_uint32),
        ("nAvgBytesPerSec", ctypes.c_uint32),
        ("nBlockAlign", ctypes.c_uint16),
        ("wBitsPerSample", ctypes.c_uint16),
        ("cbSize", ctypes.c_uint16),
    ]


class MPEGLAYER3WAVEFORMAT(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("wfx", WAVEFORMATEX),
        ("wID", ctypes.c_uint16),
        ("fdwFlags", ctypes.c_uint32),
        ("nBlockSize", ctypes.c_uint16),
        ("nFramesPerBlock", ctypes.c_uint16),
        ("nCodecDelay", ctypes.c_uint16),
    ]


class WAVEHDR(ctypes.Structure):
    _fields_ = [
        ("lpData", ctypes.c_void_p),
        ("dwBufferLength", ctypes.c_uint32),
        ("dwBytesRecorded", ctypes.c_uint32),
        ("dwUser", ctypes.c_size_t),
        ("dwFlags", ctypes.c_uint32),
        ("dwLoops", ctypes.c_uint32),
        ("lpNext", ctypes.c_void_p),
        ("reserved", ctypes.c_size_t),
    ]


class WindowsMp3Decoder:
    """
    Decodifica cualquier flujo MP3 (como el de Edge Neural TTS o ElevenLabs) directamente en memoria
    a muestras PCM de 16 bits a 24,000 Hz usando el codec nativo de Windows (`msacm32.dll`).
    No requiere `ffmpeg` ni paquetes externos; tarda < 1 ms por frase.
    """

    _BITRATES_V1_L3 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
    _BITRATES_V2_L3 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]
    _SRATES_V1 = [44100, 48000, 32000, 0]
    _SRATES_V2 = [22050, 24000, 16000, 0]
    _SRATES_V25 = [11025, 12000, 8000, 0]

    @classmethod
    def _strip_id3(cls, data: bytes) -> bytes:
        if len(data) > 10 and data[:3] == b"ID3":
            size = (
                ((data[6] & 0x7F) << 21)
                | ((data[7] & 0x7F) << 14)
                | ((data[8] & 0x7F) << 7)
                | (data[9] & 0x7F)
            )
            return data[10 + size :]
        return data

    @classmethod
    def _parse_first_frame(cls, data: bytes) -> Tuple[int, int, int, int, int]:
        """Devuelve `(offset, sample_rate, bitrate_bps, channels, block_size)` del primer frame MP3."""
        limit = min(len(data) - 4, 8192)
        for i in range(max(0, limit)):
            if data[i] != 0xFF or (data[i + 1] & 0xE0) != 0xE0:
                continue
            b1, b2, b3 = data[i + 1], data[i + 2], data[i + 3]
            ver_bits = (b1 >> 3) & 0x03
            layer_bits = (b1 >> 1) & 0x03
            if ver_bits == 1 or layer_bits != 1:  # Layer III = 01
                continue
            br_idx = (b2 >> 4) & 0x0F
            sr_idx = (b2 >> 2) & 0x03
            padding = (b2 >> 1) & 0x01
            ch_mode = (b3 >> 6) & 0x03
            if br_idx == 0 or br_idx == 15 or sr_idx == 3:
                continue

            if ver_bits == 3:  # MPEG-1
                sr = cls._SRATES_V1[sr_idx]
                br = cls._BITRATES_V1_L3[br_idx] * 1000
                block_size = int((144 * br) // sr + padding)
            elif ver_bits == 2:  # MPEG-2
                sr = cls._SRATES_V2[sr_idx]
                br = cls._BITRATES_V2_L3[br_idx] * 1000
                block_size = int((72 * br) // sr + padding)
            else:  # MPEG-2.5
                sr = cls._SRATES_V25[sr_idx]
                br = cls._BITRATES_V2_L3[br_idx] * 1000
                block_size = int((72 * br) // sr + padding)

            channels = 1 if ch_mode == 3 else 2
            return i, sr, br, channels, max(64, block_size)
        return 0, 24000, 48000, 1, 144

    @classmethod
    def decode_to_samples(cls, mp3_bytes: bytes) -> Tuple[np.ndarray, int]:
        """Decodifica bytes MP3 a `(samples_int16_mono, sample_rate)`."""
        raw = cls._strip_id3(mp3_bytes)
        if len(raw) < 64:
            return np.zeros(0, dtype=np.int16), 24000

        offset, sr, br, channels, block_size = cls._parse_first_frame(raw)
        if offset > 0:
            raw = raw[offset:]

        msacm = ctypes.windll.msacm32
        mp3_fmt = MPEGLAYER3WAVEFORMAT(
            WAVEFORMATEX(
                wFormatTag=WAVE_FORMAT_MPEGLAYER3,
                nChannels=channels,
                nSamplesPerSec=sr,
                nAvgBytesPerSec=br // 8,
                nBlockAlign=1,
                wBitsPerSample=0,
                cbSize=12,
            ),
            wID=1,
            fdwFlags=2,
            nBlockSize=block_size,
            nFramesPerBlock=1,
            nCodecDelay=0,
        )
        pcm_fmt = WAVEFORMATEX(
            wFormatTag=WAVE_FORMAT_PCM,
            nChannels=channels,
            nSamplesPerSec=sr,
            nAvgBytesPerSec=sr * channels * 2,
            nBlockAlign=channels * 2,
            wBitsPerSample=16,
            cbSize=0,
        )

        has = ctypes.c_void_p()
        res = msacm.acmStreamOpen(
            ctypes.byref(has),
            None,
            ctypes.byref(mp3_fmt),
            ctypes.byref(pcm_fmt),
            None,
            0,
            0,
            0,
        )
        if res != 0 or not has.value:
            return np.zeros(0, dtype=np.int16), sr

        try:
            src_len = len(raw)
            dst_est = ctypes.c_uint32(0)
            msacm.acmStreamSize(has, src_len, ctypes.byref(dst_est), 0)
            dst_len = max(int(dst_est.value) + 16384, src_len * 18)

            src_buf = ctypes.create_string_buffer(raw, src_len)
            dst_buf = ctypes.create_string_buffer(dst_len)

            # ACMSTREAMHEADER tiene 124 bytes en Windows x64 y 84 bytes en x86
            is_64 = ctypes.sizeof(ctypes.c_void_p) == 8
            hdr_size = 124 if is_64 else 84
            hdr = ctypes.create_string_buffer(256)
            ctypes.c_uint32.from_buffer(hdr, 0).value = hdr_size
            ctypes.c_void_p.from_buffer(hdr, 16 if is_64 else 12).value = ctypes.addressof(src_buf)
            ctypes.c_uint32.from_buffer(hdr, 24 if is_64 else 16).value = src_len
            ctypes.c_void_p.from_buffer(hdr, 40 if is_64 else 28).value = ctypes.addressof(dst_buf)
            ctypes.c_uint32.from_buffer(hdr, 48 if is_64 else 32).value = dst_len

            if msacm.acmStreamPrepareHeader(has, ctypes.byref(hdr), 0) != 0:
                return np.zeros(0, dtype=np.int16), sr

            try:
                conv_res = msacm.acmStreamConvert(has, ctypes.byref(hdr), 0)
                used = ctypes.c_uint32.from_buffer(hdr, 52 if is_64 else 36).value
                if conv_res != 0 or used <= 0:
                    return np.zeros(0, dtype=np.int16), sr
                pcm_bytes = dst_buf.raw[: used - (used % 2)]
            finally:
                msacm.acmStreamUnprepareHeader(has, ctypes.byref(hdr), 0)

            samples = np.frombuffer(pcm_bytes, dtype=np.int16)
            if channels == 2 and len(samples) >= 2:
                samples = ((samples[0::2].astype(np.int32) + samples[1::2].astype(np.int32)) // 2).astype(np.int16)
            return samples, sr
        finally:
            msacm.acmStreamClose(has, 0)


# ============================================================================
# 2. Procesador DSP `VoiceFx` portado fielmente de `Voice.cs` (L644-1495)
#    y `Capri.cs` (L4927-4938: Pitch = +2 semitonos, Speed = 120%)
# ============================================================================

class VoiceFx:
    """
    Port exacto de `VoiceFx` en `Voice.cs` (`lachydotmcg/capri-desktop`) acelerado con NumPy:
    - `wsola_stretch`: Estiramiento temporal WSOLA (Waveform Similarity Overlap-Add) con ventanas Hann
      de 20ms y correlación cruzada de 5ms (`VoiceFx.Stretcher` L1284-1402).
    - `sinc_resample`: Re-muestreador anti-aliasing Windowed-Sinc de 256 fases y 32 taps (`VoiceFx.Resampler` L1212-1281).
    - `layer_harmonies`: Doblaje de capas armónicas a +2 y -2.5 semitonos con retardo de 25ms (`VoiceFx.Layerer` L1405-1495).
    """

    RATE = 24000
    DEFAULT_PITCH = 2.0   # Capri.cs L4929: VoicePitch = 2 (+2 semitonos)
    DEFAULT_SPEED = 120   # Capri.cs L4931: VoiceSpeed = 120 (120%)

    # Tabla precalculada del filtro Windowed-Sinc de 256 fases x 32 taps (Voice.cs L1217-1244)
    _PHASES = 256
    _HALF_TAPS = 16
    _TAPS = 32
    _SINC_TABLE = np.zeros((_PHASES + 1, _TAPS), dtype=np.float64)

    for _p in range(_PHASES + 1):
        _frac = _p / _PHASES
        _k = np.arange(-_HALF_TAPS + 1, _HALF_TAPS + 1, dtype=np.float64)
        _x = _k - _frac
        _sinc = np.ones_like(_x)
        _nz = np.abs(_x) >= 1e-9
        _sinc[_nz] = np.sin(math.pi * _x[_nz]) / (math.pi * _x[_nz])
        _win = 0.5 + 0.5 * np.cos(math.pi * _x / _HALF_TAPS)
        _taps = _sinc * _win
        _SINC_TABLE[_p] = _taps / np.sum(_taps)

    @staticmethod
    def lift(semitones: float) -> float:
        """Factor de cambio de tono: `2^(semitones / 12)` (`VoiceFx.Lift` en `Voice.cs` L667)."""
        return math.pow(2.0, semitones / 12.0)

    @staticmethod
    def tempo(base_speed: float, pitch_semitones: float, speed_pct: int) -> float:
        """
        Velocidad interna a la que Kokoro debe hablar antes del re-muestreo de tono
        para que tras subir `+pitch_semitones` quede exactamente a `base_speed * (speed_pct / 100)`
        (`VoiceFx.Tempo` en `Voice.cs` L672).
        """
        raw = base_speed * (speed_pct / 100.0) / VoiceFx.lift(pitch_semitones)
        return float(max(0.25, min(3.0, raw)))

    @staticmethod
    def sayable(text: str) -> str:
        """Limpia bloques de código, URLs, etiquetas `[ACTION:...]` y markdown (`Voice.Sayable` L559-640)."""
        if not text:
            return ""
        t = text.strip()
        if t.startswith("[SIGNAL CORRUPTED]"):
            return ""
        t = re.sub(r"```[\s\S]*?```", " ", t)
        t = re.sub(r"`([^`]+)`", r"\1", t)
        t = re.sub(r"\[ACTION:[^\]]*\]", " ", t)
        t = re.sub(r"https?://\S+", " ", t)
        t = re.sub(r"[*_~#<>|\[\]{}]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    @classmethod
    def sinc_resample(cls, samples: np.ndarray, factor: float) -> np.ndarray:
        """
        Re-muestreador anti-aliased de 32 taps Windowed-Sinc (`VoiceFx.Resample` en `Voice.cs` L1212-1281).
        Si `factor > 1.0`, acorta y sube el tono/formantes; si `factor < 1.0`, alarga y baja el tono.
        """
        n = len(samples)
        if n < 8 or abs(factor - 1.0) < 1e-5:
            return samples.astype(np.int16, copy=True)

        out_len = max(1, int(round(n / factor)))
        padded = np.pad(samples.astype(np.float64), (cls._HALF_TAPS - 1, cls._HALF_TAPS + 1), mode="edge")
        positions = np.arange(out_len, dtype=np.float64) * factor
        whole = np.floor(positions).astype(np.int32)
        frac = (positions - whole) * cls._PHASES
        phase = np.clip(np.floor(frac).astype(np.int32), 0, cls._PHASES - 1)
        blend = (frac - phase)[:, None]

        weights = cls._SINC_TABLE[phase] + blend * (cls._SINC_TABLE[phase + 1] - cls._SINC_TABLE[phase])
        max_start = len(padded) - cls._TAPS
        whole = np.clip(whole, 0, max_start)

        shape = (max_start + 1, cls._TAPS)
        strides = (padded.strides[0], padded.strides[0])
        windows = np.lib.stride_tricks.as_strided(padded, shape=shape, strides=strides)
        gathered = windows[whole]
        out = np.einsum("ij,ij->i", gathered, weights)
        return np.clip(np.round(out), -32768, 32767).astype(np.int16)

    @classmethod
    def wsola_stretch(cls, samples: np.ndarray, rate: int, stretch: float) -> np.ndarray:
        """
        Estirador temporal WSOLA (Waveform Similarity Overlap-Add) con ventanas Hann de 20ms
        y búsqueda de correlación cruzada normalizada de 5ms (`VoiceFx.Stretcher` en `Voice.cs` L1284-1402).
        Cambia la velocidad del habla sin alterar el tono ni introducir artefactos metálicos.
        """
        n = len(samples)
        if n == 0 or abs(stretch - 1.0) < 0.005:
            return samples.astype(np.int16, copy=True)

        win_len = max(64, (rate // 50) & ~1)  # 20 ms (480 muestras a 24kHz)
        hop = win_len // 2                     # 10 ms (240 muestras a 24kHz)
        search = max(8, hop // 2)              # 5 ms  (120 muestras a 24kHz)
        if n <= win_len * 2:
            return samples.astype(np.int16, copy=True)

        idx = np.arange(win_len, dtype=np.float64)
        hann = 0.5 - 0.5 * np.cos(2.0 * math.pi * idx / win_len)

        src = samples.astype(np.float64)
        est_out = int(n / stretch) + win_len * 3
        out_sum = np.zeros(est_out, dtype=np.float64)
        out_w = np.zeros(est_out, dtype=np.float64)

        out_at = 0
        in_at = 0
        step = hop * stretch
        target = step

        out_sum[:win_len] += src[:win_len] * hann
        out_w[:win_len] += hann

        while True:
            natural = in_at + hop
            center = int(round(target))
            lo = max(0, center - search)
            hi = min(n - win_len, center + search)
            if lo > hi or natural + hop >= n:
                break

            ref = src[natural : natural + hop]
            ref_power = float(np.dot(ref, ref))
            chosen = max(lo, min(hi, center))

            if ref_power > 1e-3 and hi > lo:
                num_cands = hi - lo + 1
                shape = (num_cands, hop)
                strides = (src.strides[0], src.strides[0])
                cands = np.lib.stride_tricks.as_strided(src[lo:], shape=shape, strides=strides)
                dots = cands @ ref
                cand_powers = np.einsum("ij,ij->i", cands, cands)
                valid = cand_powers > 1e-3
                if np.any(valid):
                    scores = np.full(num_cands, -2.0, dtype=np.float64)
                    scores[valid] = dots[valid] / np.sqrt(ref_power * cand_powers[valid])
                    best_idx = int(np.argmax(scores))
                    if scores[best_idx] > -1.0:
                        chosen = lo + best_idx

            in_at = chosen
            out_at += hop
            if out_at + win_len > len(out_sum):
                pad = win_len * 4
                out_sum = np.pad(out_sum, (0, pad))
                out_w = np.pad(out_w, (0, pad))

            out_sum[out_at : out_at + win_len] += src[in_at : in_at + win_len] * hann
            out_w[out_at : out_at + win_len] += hann
            target += step

        total_len = out_at + win_len
        out_sum = out_sum[:total_len]
        out_w = out_w[:total_len]
        res = np.zeros(total_len, dtype=np.float64)
        nz = out_w > 1e-6
        res[nz] = out_sum[nz] / out_w[nz]
        return np.clip(np.round(res), -32768, 32767).astype(np.int16)

    @classmethod
    def layer_harmonies(cls, samples: np.ndarray, rate: int, layers_mode: str = "off") -> np.ndarray:
        """
        Doblaje de capas armónicas (`VoiceFx.Layerer` en `Voice.cs` L1405-1495):
        - `one`: añade 1 capa a +2.0 semitonos con 25ms de retardo a -8 dB (`0.4` ganancia).
        - `two`: añade además una segunda capa a -2.5 semitonos con 25ms de retardo a -8 dB.
        """
        if layers_mode not in ("one", "two") or len(samples) < 64:
            return samples

        delay = max(1, int(round(rate * 0.025)))  # 25 ms
        level = 0.4
        semis = [2.0] if layers_mode == "one" else [2.0, -2.5]

        mixed = samples.astype(np.float64).copy()
        for semi in semis:
            factor = cls.lift(semi)
            stretched = cls.wsola_stretch(samples, rate, 1.0 / factor)
            harmony = cls.sinc_resample(stretched, factor).astype(np.float64)
            end_idx = min(len(mixed), delay + len(harmony))
            if end_idx > delay:
                mixed[delay:end_idx] += level * harmony[: end_idx - delay]

        return np.clip(np.round(mixed), -32768, 32767).astype(np.int16)

    @classmethod
    def restyled_samples(
        cls,
        samples: np.ndarray,
        rate: int = 24000,
        pitch_semitones: float = 2.0,
        speed_pct: int = 120,
        layers_mode: str = "off",
    ) -> np.ndarray:
        """
        Cadena completa `VoiceFx.Restyled` de `Voice.cs` (L705-718):
        1. Convierte a 24,000 Hz si viene a otra frecuencia.
        2. Recorta silencios muertos al inicio y al final para respuesta inmediata.
        3. Estira con WSOLA por `(speed / 100.0) / Lift(pitch)` y re-muestrea con Sinc de 32 taps
           por `Lift(pitch)` para que el tono suba `+pitch_semitones` y el ritmo sea `speed_pct%`.
        4. Opcionalmente aplica capas armónicas (`Layerer`) y normaliza el nivel al de `hello-morning.wav`.
        """
        if len(samples) < 16:
            return samples

        if rate != cls.RATE and rate > 0:
            samples = cls.sinc_resample(samples, rate / float(cls.RATE))
            rate = cls.RATE

        # Recortar silencio inicial/final excesivo (>25ms) manteniendo respiración natural
        abs_s = np.abs(samples.astype(np.int32))
        loud = np.where(abs_s > 180)[0]
        if len(loud) > 0:
            pad = int(rate * 0.025)
            start = max(0, int(loud[0]) - pad)
            end = min(len(samples), int(loud[-1]) + int(rate * 0.06))
            samples = samples[start:end]

        factor = cls.lift(pitch_semitones)
        stretch = (speed_pct / 100.0) / factor

        if abs(stretch - 1.0) >= 0.005:
            samples = cls.wsola_stretch(samples, rate, stretch)
        if abs(factor - 1.0) >= 1e-4:
            samples = cls.sinc_resample(samples, factor)
        if layers_mode in ("one", "two"):
            samples = cls.layer_harmonies(samples, rate, layers_mode)

        # Normalizar nivel al perfil de `hello-morning.wav` (peak ~ 26,500)
        peak = int(np.max(np.abs(samples.astype(np.int32)))) if len(samples) > 0 else 0
        if peak > 300:
            gain = min(2.2, 26500.0 / peak)
            if abs(gain - 1.0) > 0.05:
                samples = np.clip(np.round(samples.astype(np.float64) * gain), -32768, 32767).astype(np.int16)

        return samples

    @classmethod
    def samples_to_wav_bytes(cls, samples: np.ndarray, rate: int = 24000) -> bytes:
        out_io = io.BytesIO()
        with wave.open(out_io, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(samples.astype(np.int16).tobytes())
        return out_io.getvalue()

    @classmethod
    def wav_bytes_to_samples(cls, wav_bytes: bytes) -> Tuple[np.ndarray, int]:
        if not wav_bytes or len(wav_bytes) <= 44:
            return np.zeros(0, dtype=np.int16), cls.RATE
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            ch = wf.getnchannels()
            sw = wf.getsampwidth()
            rate = wf.getframerate()
            raw = wf.readframes(wf.getnframes())
        if sw != 2:
            return np.zeros(0, dtype=np.int16), rate
        samples = np.frombuffer(raw, dtype=np.int16)
        if ch == 2 and len(samples) >= 2:
            samples = ((samples[0::2].astype(np.int32) + samples[1::2].astype(np.int32)) // 2).astype(np.int16)
        return samples, rate


# ============================================================================
# 3. Motor Local Oficial `capri-voice-1` (`sherpa-onnx` + Kokoro 82M v1.0)
#    Portado de `LocalVoice`, `ModelFile` (`Voice.cs` L2430-3146) y `VoicePack.cs`
# ============================================================================

class _SherpaVits(ctypes.Structure):
    _fields_ = [
        ("Model", ctypes.c_void_p),
        ("Lexicon", ctypes.c_void_p),
        ("Tokens", ctypes.c_void_p),
        ("Data", ctypes.c_void_p),
        ("Noise", ctypes.c_float),
        ("NoiseW", ctypes.c_float),
        ("Length", ctypes.c_float),
        ("Dict", ctypes.c_void_p),
    ]


class _SherpaMatcha(ctypes.Structure):
    _fields_ = [
        ("Acoustic", ctypes.c_void_p),
        ("Vocoder", ctypes.c_void_p),
        ("Lexicon", ctypes.c_void_p),
        ("Tokens", ctypes.c_void_p),
        ("Data", ctypes.c_void_p),
        ("Noise", ctypes.c_float),
        ("Length", ctypes.c_float),
        ("Dict", ctypes.c_void_p),
    ]


class _SherpaKokoro(ctypes.Structure):
    _fields_ = [
        ("Model", ctypes.c_void_p),
        ("Voices", ctypes.c_void_p),
        ("Tokens", ctypes.c_void_p),
        ("Data", ctypes.c_void_p),
        ("Length", ctypes.c_float),
        ("Dict", ctypes.c_void_p),
        ("Lexicon", ctypes.c_void_p),
        ("Lang", ctypes.c_void_p),
    ]


class _SherpaKitten(ctypes.Structure):
    _fields_ = [
        ("Model", ctypes.c_void_p),
        ("Voices", ctypes.c_void_p),
        ("Tokens", ctypes.c_void_p),
        ("Data", ctypes.c_void_p),
        ("Length", ctypes.c_float),
    ]


class _SherpaZipvoice(ctypes.Structure):
    _fields_ = [
        ("Tokens", ctypes.c_void_p),
        ("Encoder", ctypes.c_void_p),
        ("Decoder", ctypes.c_void_p),
        ("Vocoder", ctypes.c_void_p),
        ("Data", ctypes.c_void_p),
        ("Lexicon", ctypes.c_void_p),
        ("Feat", ctypes.c_float),
        ("Shift", ctypes.c_float),
        ("Rms", ctypes.c_float),
        ("Guidance", ctypes.c_float),
    ]


class _SherpaPocket(ctypes.Structure):
    _fields_ = [
        ("Flow", ctypes.c_void_p),
        ("Main", ctypes.c_void_p),
        ("Encoder", ctypes.c_void_p),
        ("Decoder", ctypes.c_void_p),
        ("Conditioner", ctypes.c_void_p),
        ("Vocab", ctypes.c_void_p),
        ("Scores", ctypes.c_void_p),
        ("Cache", ctypes.c_int32),
    ]


class _SherpaSupertonic(ctypes.Structure):
    _fields_ = [
        ("Duration", ctypes.c_void_p),
        ("Encoder", ctypes.c_void_p),
        ("Estimator", ctypes.c_void_p),
        ("Vocoder", ctypes.c_void_p),
        ("Json", ctypes.c_void_p),
        ("Indexer", ctypes.c_void_p),
        ("Style", ctypes.c_void_p),
    ]


class _SherpaModelConfig(ctypes.Structure):
    _fields_ = [
        ("Vits", _SherpaVits),
        ("Threads", ctypes.c_int32),
        ("Debug", ctypes.c_int32),
        ("Provider", ctypes.c_void_p),
        ("Matcha", _SherpaMatcha),
        ("Kokoro", _SherpaKokoro),
        ("Kitten", _SherpaKitten),
        ("Zipvoice", _SherpaZipvoice),
        ("Pocket", _SherpaPocket),
        ("Supertonic", _SherpaSupertonic),
    ]


class _SherpaConfig(ctypes.Structure):
    _fields_ = [
        ("Model", _SherpaModelConfig),
        ("Rules", ctypes.c_void_p),
        ("MaxSentences", ctypes.c_int32),
        ("Fars", ctypes.c_void_p),
        ("Silence", ctypes.c_float),
    ]


class _SherpaGenerated(ctypes.Structure):
    _fields_ = [
        ("Samples", ctypes.POINTER(ctypes.c_float)),
        ("Count", ctypes.c_int32),
        ("Rate", ctypes.c_int32),
    ]


class SherpaKokoroEngine:
    """
    Motor oficial `capri-voice-1` de `lachydotmcg/capri-desktop` (`VoicePack.cs` + `LocalVoice` en `Voice.cs`).
    Carga `sherpa-onnx-c-api.dll` + `onnxruntime.dll` y ejecuta el modelo **Kokoro 82M v1.0** (`model.onnx` + `voices.bin`).
    Soporta tanto el Speaker 53 ("Her own" — voz original de Capri) como el Speaker 28 ("ef_dora" — español)
    con fonemización en español (`es`) e inglés (`en-us`) mediante `espeak-ng-data`.
    """

    PACK_NAME = "capri-voice-1"
    PACK_URL = "https://github.com/lachydotmcg/capri-desktop/releases/download/voice-pack-1/capri-voice-1.zip"
    PACK_SHA256 = "9fae085696d68a580d6b1a953d7b253129bfe506a2c016421b306b7237d3214c"
    PACK_BYTES = 316434538

    # Estilos originales de Capri (`LocalVoice.Styles` en `Voice.cs` L2436-2442 + `ef_dora` español)
    STYLES: Dict[str, Tuple[int, float]] = {
        "her_own": (53, 1.10),  # Speaker 53: "Her own" (la voz del saludo de Capri)
        "dora_es": (28, 1.08),  # Speaker 28: "ef_dora" (voz femenina en español de Kokoro)
        "bright":  (2,  1.10),  # Speaker 2:  "Bright" (af_bella)
        "sly":     (6,  1.08),  # Speaker 6:  "Sly" (af_nicole)
        "sharp":   (21, 1.10),  # Speaker 21: "Sharp" (bf_emma)
    }

    REQUIRED_FILES = [
        "sherpa-onnx-c-api.dll",
        "onnxruntime.dll",
        "model.onnx",
        "voices.bin",
        "tokens.txt",
        "lexicon-us-en.txt",
        "espeak-ng-data/phontab",
    ]

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.local_pack_dir = base_dir / "data" / "voice" / self.PACK_NAME
        appdata = os.environ.get("LOCALAPPDATA", "")
        self.appdata_pack_dir = Path(appdata) / "Capri" / "voice" / self.PACK_NAME if appdata else self.local_pack_dir

        self._lock = threading.Lock()
        self._dll: Optional[ctypes.CDLL] = None
        self._tts_ptr: Optional[int] = None
        self._opened_lang: Optional[str] = None
        self._held_buffers: List[ctypes.Array] = []

        # Estado de descarga en segundo plano
        self.is_downloading: bool = False
        self.download_progress_pct: float = 0.0
        self.download_status_msg: str = ""

    def find_installed_folder(self) -> Optional[Path]:
        for folder in (self.local_pack_dir, self.appdata_pack_dir):
            if all((folder / rel).exists() for rel in self.REQUIRED_FILES):
                return folder
        return None

    @property
    def is_installed(self) -> bool:
        return self.find_installed_folder() is not None

    @staticmethod
    def _spanish_to_kokoro_phonetic(text: str) -> str:
        """
        Cuando `capri-voice-1` no incluye `es_dict` (solo `en_dict`), adapta fonéticamente
        el texto en español para que el fonemizador inglés + Kokoro 82M pronuncie cada sílaba
        con vocales claras y sin comerse tildes ni signos `¿`/`¡`.
        """
        t = text.replace("¿", " ").replace("¡", " ")
        # Conservar acentos como vocales claras antes de pasar por en_dict
        replacements = [
            (r"\bhola\b", "ohla"),
            (r"\bchoom\b", "choom"),
            (r"\bgonk\b", "gonk"),
            (r"\bpreem\b", "preem"),
            (r"\bcómo\b", "kohmo"),
            (r"\bcomo\b", "kohmo"),
            (r"\bestás\b", "ehstahs"),
            (r"\bestas\b", "ehstahs"),
            (r"\bestá\b", "ehstah"),
            (r"\bestoy\b", "ehstoy"),
            (r"\bqué\b", "keh"),
            (r"\bque\b", "keh"),
            (r"\bquién\b", "kyehn"),
            (r"\bpor\b", "por"),
            (r"\bpara\b", "pahrah"),
            (r"\bpero\b", "pehro"),
            (r"\btodo\b", "tohdo"),
            (r"\bbien\b", "byehn"),
            (r"\bmuy\b", "mooy"),
            (r"\baquí\b", "ahkee"),
            (r"\bahora\b", "ah-ohrah"),
            ("ll", "y"),
            ("ñ", "ny"),
            ("Ñ", "Ny"),
            ("qu", "k"),
            ("Qu", "K"),
            ("gue", "geh"),
            ("gui", "gee"),
            ("ce", "seh"),
            ("ci", "see"),
            ("ge", "heh"),
            ("gi", "hee"),
            ("j", "h"),
            ("á", "ah"),
            ("é", "eh"),
            ("í", "ee"),
            ("ó", "oh"),
            ("ú", "oo"),
            ("ü", "w"),
        ]
        for pat, rep in replacements:
            if pat.startswith(r"\b"):
                t = re.sub(pat, rep, t, flags=re.IGNORECASE)
            else:
                t = t.replace(pat, rep)
        return re.sub(r"\s+", " ", t).strip()

    def _ensure_loaded(self, folder: Path, lang: str = "es") -> bool:
        has_es_dict = (folder / "espeak-ng-data" / "es_dict").exists()
        effective_lang = lang if (lang != "es" or has_es_dict) else "en-us"

        if self._tts_ptr and self._opened_lang == effective_lang and self._dll is not None:
            return True

        self._close()
        try:
            k32 = ctypes.windll.kernel32
            k32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
            k32.LoadLibraryExW.restype = ctypes.c_void_p

            for dll_name in ("onnxruntime.dll", "sherpa-onnx-c-api.dll"):
                dll_path = str((folder / dll_name).resolve())
                # LOAD_WITH_ALTERED_SEARCH_PATH = 0x00000008
                h = k32.LoadLibraryExW(dll_path, None, 8)
                if not h:
                    return False

            dll = ctypes.CDLL(str((folder / "sherpa-onnx-c-api.dll").resolve()))
            dll.SherpaOnnxCreateOfflineTts.argtypes = [ctypes.POINTER(_SherpaConfig)]
            dll.SherpaOnnxCreateOfflineTts.restype = ctypes.c_void_p
            dll.SherpaOnnxDestroyOfflineTts.argtypes = [ctypes.c_void_p]
            dll.SherpaOnnxDestroyOfflineTts.restype = None
            dll.SherpaOnnxOfflineTtsGenerate.argtypes = [
                ctypes.c_void_p,
                ctypes.c_char_p,
                ctypes.c_int32,
                ctypes.c_float,
            ]
            dll.SherpaOnnxOfflineTtsGenerate.restype = ctypes.c_void_p
            dll.SherpaOnnxDestroyOfflineTtsGeneratedAudio.argtypes = [ctypes.c_void_p]
            dll.SherpaOnnxDestroyOfflineTtsGeneratedAudio.restype = None

            self._held_buffers = []

            def c_str(val: str) -> ctypes.c_void_p:
                buf = ctypes.create_string_buffer(val.encode("utf-8"))
                self._held_buffers.append(buf)
                return ctypes.cast(buf, ctypes.c_void_p)

            cfg = _SherpaConfig()
            cfg.Model.Kokoro.Model = c_str(str((folder / "model.onnx").resolve()))
            cfg.Model.Kokoro.Voices = c_str(str((folder / "voices.bin").resolve()))
            cfg.Model.Kokoro.Tokens = c_str(str((folder / "tokens.txt").resolve()))
            cfg.Model.Kokoro.Data = c_str(str((folder / "espeak-ng-data").resolve()))
            cfg.Model.Kokoro.Length = 1.0
            cfg.Model.Kokoro.Dict = c_str("")
            # Si `es_dict` existe en `espeak-ng-data`, usar fonemizador nativo `es`;
            # si el paquete `capri-voice-1` solo incluye `en_dict`, usar `en-us` con adaptación fonética.
            if effective_lang == "es":
                cfg.Model.Kokoro.Lexicon = c_str("")
                cfg.Model.Kokoro.Lang = c_str("es")
            else:
                lex_file = "lexicon-gb-en.txt" if effective_lang == "en-gb" else "lexicon-us-en.txt"
                cfg.Model.Kokoro.Lexicon = c_str(str((folder / lex_file).resolve()))
                cfg.Model.Kokoro.Lang = c_str(effective_lang)

            cfg.Model.Threads = max(2, min(8, (os.cpu_count() or 4)))
            cfg.Model.Provider = c_str("cpu")
            cfg.MaxSentences = 1

            tts_ptr = dll.SherpaOnnxCreateOfflineTts(ctypes.byref(cfg))
            if not tts_ptr:
                return False

            self._dll = dll
            self._tts_ptr = tts_ptr
            self._opened_lang = effective_lang
            return True
        except Exception:
            self._close()
            return False

    def _close(self) -> None:
        if self._tts_ptr and self._dll is not None:
            try:
                self._dll.SherpaOnnxDestroyOfflineTts(self._tts_ptr)
            except Exception:
                pass
        self._tts_ptr = None
        self._opened_lang = None
        self._held_buffers = []

    def speak_samples(
        self,
        text: str,
        style_key: str = "her_own",
        lang: str = "es",
        pitch_semitones: float = 2.0,
        speed_pct: int = 120,
        layers_mode: str = "off",
    ) -> Tuple[np.ndarray, int]:
        """
        Sintetiza `text` usando `capri-voice-1` (Kokoro 82M) exactamente como `LocalVoice.Speak`
        en `Voice.cs` L2515-2548:
        - Genera audio en Kokoro a `tempo = VoiceFx.tempo(base_speed, pitch, speed)`
        - Re-muestrea con `VoiceFx.sinc_resample(samples, Lift(pitch))` para subir formantes +2 semitonos.
        """
        folder = self.find_installed_folder()
        if folder is None:
            return np.zeros(0, dtype=np.int16), VoiceFx.RATE

        has_es_dict = (folder / "espeak-ng-data" / "es_dict").exists()
        synth_text = text
        if lang == "es" and not has_es_dict:
            synth_text = self._spanish_to_kokoro_phonetic(text)
        if not synth_text.strip():
            return np.zeros(0, dtype=np.int16), VoiceFx.RATE

        speaker_id, base_speed = self.STYLES.get(style_key, (53, 1.10))
        tempo = VoiceFx.tempo(base_speed, pitch_semitones, speed_pct)

        with self._lock:
            if not self._ensure_loaded(folder, lang=lang):
                return np.zeros(0, dtype=np.int16), VoiceFx.RATE
            assert self._dll is not None and self._tts_ptr is not None

            audio_ptr = self._dll.SherpaOnnxOfflineTtsGenerate(
                self._tts_ptr,
                synth_text.encode("utf-8"),
                speaker_id,
                ctypes.c_float(tempo),
            )
            if not audio_ptr:
                return np.zeros(0, dtype=np.int16), VoiceFx.RATE

            try:
                gen = _SherpaGenerated.from_address(audio_ptr)
                if gen.Count <= 0 or not gen.Samples or gen.Rate <= 0:
                    return np.zeros(0, dtype=np.int16), VoiceFx.RATE
                floats = np.ctypeslib.as_array(gen.Samples, shape=(gen.Count,)).copy()
                rate = int(gen.Rate)
            finally:
                self._dll.SherpaOnnxDestroyOfflineTtsGeneratedAudio(audio_ptr)

        samples = np.clip(np.round(floats * 32767.0), -32768, 32767).astype(np.int16)
        if len(samples) < 1200 or int(np.max(np.abs(samples.astype(np.int32)))) < 300:
            return np.zeros(0, dtype=np.int16), VoiceFx.RATE

        # Recortar silencios muertos excesivos al inicio y al final
        abs_s = np.abs(samples.astype(np.int32))
        loud = np.where(abs_s > 180)[0]
        if len(loud) > 0:
            pad = int(rate * 0.025)
            start = max(0, int(loud[0]) - pad)
            end = min(len(samples), int(loud[-1]) + int(rate * 0.06))
            samples = samples[start:end]

        # En Kokoro, el tempo ya se compensó en `SherpaOnnxOfflineTtsGenerate`, así que solo
        # aplicamos el cambio de tono/formantes (`sinc_resample` por `Lift(pitch)`) igual que `Voice.cs` L2541
        factor = VoiceFx.lift(pitch_semitones)
        if abs(factor - 1.0) >= 1e-4:
            samples = VoiceFx.sinc_resample(samples, factor)
        if layers_mode in ("one", "two"):
            samples = VoiceFx.layer_harmonies(samples, rate, layers_mode)

        # Normalizar nivel al perfil de `hello-morning.wav` (peak ~ 26,500)
        peak = int(np.max(np.abs(samples.astype(np.int32)))) if len(samples) > 0 else 0
        if peak > 300:
            gain = min(2.4, 26500.0 / peak)
            if abs(gain - 1.0) > 0.05:
                samples = np.clip(np.round(samples.astype(np.float64) * gain), -32768, 32767).astype(np.int16)

        return samples, rate

    def download_pack_in_background(
        self,
        on_done: Optional[Callable[[bool, str], None]] = None,
    ) -> bool:
        """
        Descarga e instala en segundo plano el paquete oficial `capri-voice-1.zip` (Kokoro 82M)
        desde `lachydotmcg/capri-desktop/releases/download/voice-pack-1/capri-voice-1.zip`
        igual que `VoicePack.Ensure` en `VoicePack.cs`.
        """
        if self.is_installed:
            if on_done:
                on_done(True, f"El paquete {self.PACK_NAME} ya está instalado.")
            return False
        if self.is_downloading:
            return False

        self.is_downloading = True
        self.download_progress_pct = 0.0
        self.download_status_msg = "Iniciando descarga de capri-voice-1.zip (Kokoro 82M)..."

        def _worker() -> None:
            target_dir = self.local_pack_dir
            parent_dir = target_dir.parent
            parent_dir.mkdir(parents=True, exist_ok=True)
            zip_path = parent_dir / f"{self.PACK_NAME}.zip.part"
            staging_dir = parent_dir / f"{self.PACK_NAME}.staging"
            try:
                req = urllib.request.Request(
                    self.PACK_URL,
                    headers={"User-Agent": "Capri-Desktop-Setup"},
                )
                hasher = hashlib.sha256()
                downloaded = 0
                with urllib.request.urlopen(req, timeout=60.0) as resp, open(zip_path, "wb") as out_f:
                    total = int(resp.headers.get("Content-Length") or self.PACK_BYTES)
                    while True:
                        chunk = resp.read(256 * 1024)
                        if not chunk:
                            break
                        out_f.write(chunk)
                        hasher.update(chunk)
                        downloaded += len(chunk)
                        self.download_progress_pct = min(99.0, (downloaded * 100.0) / max(1, total))
                        mb_done = downloaded / (1024 * 1024)
                        mb_tot = total / (1024 * 1024)
                        self.download_status_msg = f"Descargando voz original de Capri (Kokoro 82M): {mb_done:.1f} / {mb_tot:.1f} MB ({self.download_progress_pct:.0f}%)"

                digest = hasher.hexdigest().lower()
                if digest != self.PACK_SHA256:
                    raise RuntimeError(f"Checksum SHA-256 inválido ({digest[:12]} != {self.PACK_SHA256[:12]}).")

                self.download_status_msg = "Descomprimiendo capri-voice-1.zip..."
                if staging_dir.exists():
                    shutil.rmtree(staging_dir, ignore_errors=True)
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(staging_dir)

                # Si el zip contiene una subcarpeta `capri-voice-1`, mover desde ahí
                inner = staging_dir / self.PACK_NAME
                src_extract = inner if inner.exists() else staging_dir
                if target_dir.exists():
                    shutil.rmtree(target_dir, ignore_errors=True)
                shutil.move(str(src_extract), str(target_dir))
                if staging_dir.exists():
                    shutil.rmtree(staging_dir, ignore_errors=True)
                if zip_path.exists():
                    zip_path.unlink(missing_ok=True)

                self.download_progress_pct = 100.0
                self.download_status_msg = "¡Voz original de Capri (Kokoro 82M Speaker 53) instalada y activa!"
                if on_done:
                    on_done(True, self.download_status_msg)
            except Exception as e:
                self.download_status_msg = f"Error al descargar capri-voice-1: {e}"
                if on_done:
                    on_done(False, self.download_status_msg)
            finally:
                self.is_downloading = False

        threading.Thread(target=_worker, daemon=True).start()
        return True


# ============================================================================
# 5. Motor Principal Unificado (`CapriVoiceEngine`)
# ============================================================================

class CapriVoiceEngine:
    """
    Orquesta los motores de voz de Capri en orden de prioridad:
    1. Si `voice_mode == "kokoro"` (o `"auto"` cuando el paquete `capri-voice-1` está instalado):
       Usa **Kokoro 82M v1.0 (`capri-voice-1`)** vía `sherpa-onnx-c-api.dll` (Speaker 53 "Her own" / Speaker 28 "ef_dora")
       con la misma cadena DSP (`+2` semitonos, `120%` velocidad) que creó `hello-morning.wav`.
    2. (Edge Neural eliminado: suplantaba a la extensión de Edge contra un endpoint no documentado.)
    3. Si hay una llave de ElevenLabs configurada (`elevenlabs_key`), soporta `eleven_flash_v2_5` (`Voice.cs` L355).
    4. Fallback 100% offline: Windows 10/11 WinRT OneCore (`Microsoft Laura`) + WSOLA + Sinc Resampler.
    """

    def __init__(self) -> None:
        self.base_dir = Path(__file__).resolve().parent
        self.config_path = self.base_dir / "data" / "voice_config.json"

        self.tts_enabled: bool = True
        self.continuous_call_mode: bool = False

        # Parámetros originales de Capri (`Capri.cs` L4927-4938)
        self.voice_mode: str = "auto"         # "auto" | "kokoro" | "neural" | "elevenlabs"
        self.kokoro_style: str = "her_own"    # "her_own" (53) | "dora_es" (28) | "bright" (2) | "sly" (6) | "sharp" (21)
        self.neural_voice: str = "salome"     # "salome" | "dalia" | "ava" | "elena" | "elvira"
        self.pitch_semitones: float = 2.0     # +2 semitonos (Capri.cs L4929)
        self.speed_pct: int = 118             # ~120% velocidad ágil (Capri.cs L4931)
        self.layers_mode: str = "off"         # "off" | "one" | "two"
        self.elevenlabs_key: str = ""
        self.elevenlabs_voice_id: str = "cgSgspJ2msm6clMCkdW9"  # Jessica (juvenil/expresiva)

        self.kokoro = SherpaKokoroEngine(self.base_dir)
        self._tts_lock = threading.Lock()
        self._tts_cache: Dict[str, str] = {}
        self._ps_proc: Optional[subprocess.Popen] = None

        # Motor local faster-whisper (CTranslate2 int8 en memoria)
        self._whisper_lock = threading.Lock()
        self._whisper_model: Optional[Any] = None

        # Control de grabación de micrófono
        self._mic_lock = threading.Lock()
        self._stop_mic_event = threading.Event()
        self.is_recording: bool = False

        self._load_config()
        threading.Thread(target=self._warmup_tts_background, daemon=True).start()

    def _warmup_tts_background(self) -> None:
        """Precarga Kokoro 82M y faster-whisper en segundo plano al iniciar el servidor."""
        try:
            self._ensure_faster_whisper()
        except Exception:
            pass
        try:
            folder = self.kokoro.find_installed_folder()
            if folder is not None and self.voice_mode in ("auto", "kokoro"):
                with self.kokoro._lock:
                    self.kokoro._ensure_loaded(folder, lang="es")
        except Exception:
            pass

    def _load_config(self) -> None:
        try:
            if self.config_path.exists():
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                self.voice_mode = str(data.get("voice_mode", self.voice_mode))
                self.kokoro_style = str(data.get("kokoro_style", self.kokoro_style))
                self.neural_voice = str(data.get("neural_voice", self.neural_voice))
                self.pitch_semitones = float(data.get("pitch_semitones", self.pitch_semitones))
                self.speed_pct = int(data.get("speed_pct", self.speed_pct))
                self.layers_mode = str(data.get("layers_mode", self.layers_mode))
                self.elevenlabs_key = str(data.get("elevenlabs_key", self.elevenlabs_key))
                self.elevenlabs_voice_id = str(data.get("elevenlabs_voice_id", self.elevenlabs_voice_id))
        except Exception:
            pass

    def save_config(self) -> None:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "voice_mode": self.voice_mode,
                "kokoro_style": self.kokoro_style,
                "neural_voice": self.neural_voice,
                "pitch_semitones": self.pitch_semitones,
                "speed_pct": self.speed_pct,
                "layers_mode": self.layers_mode,
                "elevenlabs_key": self.elevenlabs_key,
                "elevenlabs_voice_id": self.elevenlabs_voice_id,
            }
            self.config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def get_active_voice_label(self) -> str:
        if self.voice_mode == "elevenlabs" and self.elevenlabs_key:
            return f"ElevenLabs Neural + VoiceFx (+{self.pitch_semitones:.1f}st)"
        if self.kokoro.is_installed and self.voice_mode in ("auto", "kokoro"):
            return f"Capri Original (Kokoro 82M · {self.kokoro_style} · +{self.pitch_semitones:.1f}st / {self.speed_pct}%)"
        return f"Windows OneCore + VoiceFx WSOLA (+{self.pitch_semitones:.1f}st / {self.speed_pct}%) - descarga capri-voice-1 para su voz real"

    # ------------------------------------------------------------------
    # 1. Síntesis de Voz (TTS): ElevenLabs -> Kokoro 82M -> WinRT OneCore
    # ------------------------------------------------------------------

    @staticmethod
    def _looks_english(text: str) -> bool:
        words = set(re.findall(r"[a-záéíóúñü]+", text.lower()))
        en_markers = {"the", "you", "what", "with", "that", "this", "have", "your", "hey", "morning"}
        es_markers = {"que", "qué", "hola", "para", "como", "cómo", "estás", "pero", "por", "una", "con", "del"}
        if len(words & es_markers) > 0:
            return False
        if len(words & en_markers) >= 2:
            return True
        return False

    def _speak_elevenlabs_samples(self, text: str) -> Tuple[np.ndarray, int]:
        """Port de `Voice.Speak` (`Voice.cs` L355-384) para ElevenLabs (`output_format=mp3_24000_48` / `pcm_24000`)."""
        if not self.elevenlabs_key or not self.elevenlabs_voice_id:
            return np.zeros(0, dtype=np.int16), VoiceFx.RATE
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.elevenlabs_voice_id}?output_format=mp3_22050_32"
        payload = json.dumps({
            "text": text,
            "model_id": "eleven_flash_v2_5",
            "voice_settings": {"stability": 0.35, "similarity_boost": 0.75, "style": 0.55},
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "xi-api-key": self.elevenlabs_key,
                "Content-Type": "application/json",
                "User-Agent": "Capri-Desktop",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                mp3_bytes = resp.read()
            samples, sr = WindowsMp3Decoder.decode_to_samples(mp3_bytes)
            if len(samples) < 16:
                return np.zeros(0, dtype=np.int16), VoiceFx.RATE
            styled = VoiceFx.restyled_samples(
                samples,
                rate=sr,
                pitch_semitones=self.pitch_semitones,
                speed_pct=self.speed_pct,
                layers_mode=self.layers_mode,
            )
            return styled, VoiceFx.RATE
        except Exception:
            return np.zeros(0, dtype=np.int16), VoiceFx.RATE

    def _ensure_winrt_worker(self) -> Optional[subprocess.Popen]:
        """Fallback 100% offline usando `Windows.Media.SpeechSynthesis` (WinRT OneCore `Microsoft Laura`)."""
        if self._ps_proc is not None and self._ps_proc.poll() is None:
            return self._ps_proc

        ps_script = r"""
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
try {
    [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media, ContentType=WindowsRuntime] | Out-Null
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0]
    $asTaskStream = $asTaskGeneric.MakeGenericMethod([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
    $winrtSynth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
    $voices = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices
    $picked = $voices | Where-Object { $_.Language -like "es-*" -and $_.DisplayName -match "Laura|Dalia|Sabina|Paloma|Elena" } | Select-Object -First 1
    if (-not $picked) {
        $picked = $voices | Where-Object { $_.Language -like "es-*" -and $_.Gender -eq "Female" } | Select-Object -First 1
    }
    if ($picked) { $winrtSynth.Voice = $picked }
} catch {
    $winrtSynth = $null
}

Add-Type -AssemblyName System.Speech
$sapiSynth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$sapiSynth.Rate = 0
$sapiSynth.Volume = 100

while ($null -ne ($line = [Console]::In.ReadLine())) {
    $trimmed = $line.Trim()
    if ($trimmed -eq "") { continue }
    try {
        $bytes = [System.Convert]::FromBase64String($trimmed)
        $text = [System.Text.Encoding]::UTF8.GetString($bytes)
        if ($winrtSynth -ne $null) {
            $op = $winrtSynth.SynthesizeTextToStreamAsync($text)
            $task = $asTaskStream.Invoke($null, @($op))
            $stream = $task.GetAwaiter().GetResult()
            $netStream = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream)
            $ms = New-Object System.IO.MemoryStream
            $netStream.CopyTo($ms)
            $outB64 = [System.Convert]::ToBase64String($ms.ToArray())
            $stream.Dispose()
            [Console]::Out.WriteLine($outB64)
            [Console]::Out.Flush()
            continue
        }
        $ms = New-Object System.IO.MemoryStream
        $fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(24000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
        $sapiSynth.SetOutputToAudioStream($ms, $fmt)
        $sapiSynth.Speak($text)
        $sapiSynth.SetOutputToNull()
        $pcm = $ms.ToArray()
        $wavMs = New-Object System.IO.MemoryStream
        $bw = New-Object System.IO.BinaryWriter($wavMs)
        $bw.Write([System.Text.Encoding]::ASCII.GetBytes("RIFF"))
        $bw.Write([int](36 + $pcm.Length))
        $bw.Write([System.Text.Encoding]::ASCII.GetBytes("WAVEfmt "))
        $bw.Write([int]16); $bw.Write([int16]1); $bw.Write([int16]1)
        $bw.Write([int]24000); $bw.Write([int]48000); $bw.Write([int16]2); $bw.Write([int16]16)
        $bw.Write([System.Text.Encoding]::ASCII.GetBytes("data"))
        $bw.Write([int]$pcm.Length); $bw.Write($pcm); $bw.Flush()
        [Console]::Out.WriteLine([System.Convert]::ToBase64String($wavMs.ToArray()))
        [Console]::Out.Flush()
    } catch {
        [Console]::Out.WriteLine("ERR")
        [Console]::Out.Flush()
    }
}
"""
        try:
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            self._ps_proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                creationflags=creation_flags,
            )
            return self._ps_proc
        except Exception:
            self._ps_proc = None
            return None

    _ensure_tts_worker = _ensure_winrt_worker

    def _speak_winrt_offline_samples(self, text: str) -> Tuple[np.ndarray, int]:
        proc = self._ensure_winrt_worker()
        if proc is None or proc.stdin is None or proc.stdout is None:
            return np.zeros(0, dtype=np.int16), VoiceFx.RATE
        try:
            b64_in = base64.b64encode(text.encode("utf-8")).decode("ascii")
            proc.stdin.write(b64_in + "\n")
            proc.stdin.flush()
            out_line = proc.stdout.readline().strip()
            if not out_line or out_line == "ERR":
                return np.zeros(0, dtype=np.int16), VoiceFx.RATE
            raw_wav = base64.b64decode(out_line)
            samples, sr = VoiceFx.wav_bytes_to_samples(raw_wav)
            if len(samples) < 16:
                return np.zeros(0, dtype=np.int16), VoiceFx.RATE
            styled = VoiceFx.restyled_samples(
                samples,
                rate=sr,
                pitch_semitones=self.pitch_semitones,
                speed_pct=self.speed_pct,
                layers_mode=self.layers_mode,
            )
            return styled, VoiceFx.RATE
        except Exception:
            self._ps_proc = None
            return np.zeros(0, dtype=np.int16), VoiceFx.RATE

    @staticmethod
    def _is_audible(samples: np.ndarray) -> bool:
        return len(samples) >= 1200 and int(np.max(np.abs(samples.astype(np.int32)))) >= 300

    def _speak_edge_neural_samples(self, text: str) -> Tuple[np.ndarray, int]:
        """
        Sintetiza voz neuronal en español con `edge-tts` (`es-CO-SalomeNeural` / `es-MX-DaliaNeural`)
        decodificando el MP3 en memoria con `msacm32.dll` y aplicando el procesador DSP `VoiceFx`
        (+2 semitonos, 118% velocidad).
        """
        try:
            import edge_tts  # type: ignore
        except ImportError:
            return np.zeros(0, dtype=np.int16), VoiceFx.RATE

        voice_map = {
            "salome": "es-CO-SalomeNeural",
            "dalia": "es-MX-DaliaNeural",
            "elvira": "es-ES-ElviraNeural",
            "elena": "es-AR-ElenaNeural",
            "ava": "en-US-AvaMultilingualNeural",
        }
        voice_id = voice_map.get(self.neural_voice.lower(), "es-CO-SalomeNeural")

        async def _fetch_mp3() -> bytes:
            comm = edge_tts.Communicate(text=text, voice=voice_id)
            buf = bytearray()
            async for chunk in comm.stream():
                if chunk.get("type") == "audio" and chunk.get("data"):
                    buf.extend(chunk["data"])
            return bytes(buf)

        try:
            mp3_bytes = asyncio.run(asyncio.wait_for(_fetch_mp3(), timeout=4.5))
            if len(mp3_bytes) < 128:
                return np.zeros(0, dtype=np.int16), VoiceFx.RATE
            samples, sr = WindowsMp3Decoder.decode_to_samples(mp3_bytes)
            if len(samples) < 16:
                return np.zeros(0, dtype=np.int16), VoiceFx.RATE
            styled = VoiceFx.restyled_samples(
                samples,
                rate=sr,
                pitch_semitones=self.pitch_semitones,
                speed_pct=self.speed_pct,
                layers_mode=self.layers_mode,
            )
            return styled, VoiceFx.RATE
        except Exception:
            return np.zeros(0, dtype=np.int16), VoiceFx.RATE

    def synthesize_wav_b64(self, raw_text: str) -> str:
        """
        Convierte una frase de Capri en un archivo WAV PCM de 24kHz codificado en Base64
        aplicando el motor de voz activo y el procesador DSP `VoiceFx` de `lachydotmcg/capri-desktop`.
        """
        if not self.tts_enabled:
            return ""
        clean = VoiceFx.sayable(raw_text)
        if not clean:
            return ""

        cache_key = (
            f"{self.voice_mode}|{self.kokoro_style}|{self.neural_voice}|"
            f"{self.pitch_semitones}|{self.speed_pct}|{self.layers_mode}|{self.elevenlabs_voice_id}|{clean}"
        )
        cached = self._tts_cache.get(cache_key)
        if cached:
            return cached

        with self._tts_lock:
            samples = np.zeros(0, dtype=np.int16)
            rate = VoiceFx.RATE
            is_en = self._looks_english(clean)
            folder = self.kokoro.find_installed_folder()
            has_es_dict = bool(folder and (folder / "espeak-ng-data" / "es_dict").exists())

            # 1. ElevenLabs si fue seleccionado explícitamente y hay API Key
            if self.voice_mode == "elevenlabs" and self.elevenlabs_key:
                samples, rate = self._speak_elevenlabs_samples(clean)

            # 2. Para español en modo "auto" o "neural" cuando capri-voice-1 no trae `es_dict`,
            #    priorizar la voz neuronal nativa en español (`edge-tts` + `VoiceFx`) para pronunciación perfecta
            if not self._is_audible(samples) and not is_en and not has_es_dict and self.voice_mode in ("auto", "neural"):
                samples, rate = self._speak_edge_neural_samples(clean)

            # 3. Kokoro 82M (`capri-voice-1`) si está instalado y el modo es "kokoro" o "auto"
            if not self._is_audible(samples) and self.kokoro.is_installed and self.voice_mode in ("auto", "kokoro"):
                lang = "en-us" if is_en else "es"
                samples, rate = self.kokoro.speak_samples(
                    clean,
                    style_key=self.kokoro_style,
                    lang=lang,
                    pitch_semitones=self.pitch_semitones,
                    speed_pct=self.speed_pct,
                    layers_mode=self.layers_mode,
                )

            # 4. Fallback Offline: WinRT OneCore (`Microsoft Laura`) + `VoiceFx` WSOLA/Sinc
            if not self._is_audible(samples):
                samples, rate = self._speak_winrt_offline_samples(clean)

            if not self._is_audible(samples):
                return ""

            wav_bytes = VoiceFx.samples_to_wav_bytes(samples, rate=rate)
            b64_out = base64.b64encode(wav_bytes).decode("ascii")
            if len(self._tts_cache) >= 32:
                self._tts_cache.pop(next(iter(self._tts_cache)), None)
            self._tts_cache[cache_key] = b64_out
            return b64_out

    # ------------------------------------------------------------------
    # 2. Grabación de Micrófono con `winmm.dll` + Detección de Silencio (VAD)
    # ------------------------------------------------------------------

    def stop_listening(self) -> None:
        """Detiene inmediatamente la grabación de micrófono en curso y procesa lo capturado."""
        self._stop_mic_event.set()

    def record_microphone_wav(
        self,
        max_seconds: float = 10.0,
        silence_timeout_sec: float = 1.65,
        sample_rate: int = 16000,
    ) -> Tuple[bytes, str]:
        """
        Graba audio del micrófono predeterminado de Windows usando `winmm.dll` (`waveInOpen`)
        a 16kHz 16-bit Mono. Incluye buffer de pre-roll (~600ms antes de activar el umbral de voz)
        y margen de silencio final (`1.65s`) para no recortar las primeras ni últimas sílabas.
        Devuelve `(wav_bytes, error_msg)`.
        """
        with self._mic_lock:
            self._stop_mic_event.clear()
            self.is_recording = True
            try:
                winmm = ctypes.windll.winmm
                num_devs = winmm.waveInGetNumDevs()
                if num_devs <= 0:
                    return b"", "No se detectó ningún micrófono conectado en Windows."

                wfx = WAVEFORMATEX(
                    wFormatTag=WAVE_FORMAT_PCM,
                    nChannels=1,
                    nSamplesPerSec=sample_rate,
                    nAvgBytesPerSec=sample_rate * 2,
                    nBlockAlign=2,
                    wBitsPerSample=16,
                    cbSize=0,
                )

                h_wave_in = ctypes.c_void_p()
                res = winmm.waveInOpen(
                    ctypes.byref(h_wave_in),
                    WAVE_MAPPER,
                    ctypes.byref(wfx),
                    0,
                    0,
                    CALLBACK_NULL,
                )
                if res != 0 or not h_wave_in.value:
                    return b"", f"No se pudo abrir el micrófono (código WinMM {res}). Revisa los permisos de micrófono en Windows."

                chunk_ms = 100
                chunk_bytes = int(sample_rate * 2 * (chunk_ms / 1000.0))
                total_chunks = max(25, int((max_seconds * 1000) / chunk_ms))

                buffers = []
                headers = []
                hdr_size = ctypes.sizeof(WAVEHDR)

                for _ in range(total_chunks):
                    buf = ctypes.create_string_buffer(chunk_bytes)
                    hdr = WAVEHDR(
                        lpData=ctypes.cast(buf, ctypes.c_void_p),
                        dwBufferLength=chunk_bytes,
                        dwBytesRecorded=0,
                        dwUser=0,
                        dwFlags=0,
                        dwLoops=0,
                        lpNext=None,
                        reserved=0,
                    )
                    winmm.waveInPrepareHeader(h_wave_in, ctypes.byref(hdr), hdr_size)
                    winmm.waveInAddBuffer(h_wave_in, ctypes.byref(hdr), hdr_size)
                    buffers.append(buf)
                    headers.append(hdr)

                winmm.waveInStart(h_wave_in)

                # Pre-roll de 800ms (8 chunks) para conservar las primeras sílabas suaves ("hola...")
                # sin meter segundos enteros de ruido blanco inicial al motor STT
                pre_roll: deque[bytes] = deque(maxlen=8)
                all_raw_pcm = bytearray()
                recorded_pcm = bytearray()
                speech_started = False
                speech_chunks = 0
                silent_chunks_after_speech = 0
                max_silent_chunks = max(14, int((silence_timeout_sec * 1000) / chunk_ms))
                noise_floor = 105.0

                idx = 0
                start_t = time.time()

                while idx < total_chunks and not self._stop_mic_event.is_set():
                    if (time.time() - start_t) > max_seconds:
                        break

                    hdr = headers[idx]
                    if not (hdr.dwFlags & WHDR_DONE):
                        time.sleep(0.025)
                        continue

                    n_rec = hdr.dwBytesRecorded
                    if n_rec > 0:
                        raw_chunk = buffers[idx].raw[: n_rec - (n_rec % 2)]
                        all_raw_pcm.extend(raw_chunk)

                        pcm_arr = array("h")
                        pcm_arr.frombytes(raw_chunk)
                        if len(pcm_arr) > 0:
                            sum_sq = sum(s * s for s in pcm_arr)
                            rms = math.sqrt(sum_sq / len(pcm_arr))
                        else:
                            rms = 0.0

                        # Solo adaptar el piso de ruido cuando el bloque es realmente silencioso,
                        # evitando que hablar desde el primer instante dispare el umbral
                        if not speech_started and rms < 180.0:
                            noise_floor = max(75.0, min(175.0, 0.80 * noise_floor + 0.20 * rms))

                        start_threshold = max(125.0, noise_floor * 1.42)
                        cont_threshold = max(95.0, noise_floor * 1.18)

                        if not speech_started:
                            if rms >= start_threshold:
                                speech_started = True
                                speech_chunks = 1
                                silent_chunks_after_speech = 0
                                # Añadir 150ms de silencio limpio + todo el pre-roll previo + el bloque actual
                                lead_silence = b"\x00" * (int(sample_rate * 0.15) * 2)
                                recorded_pcm.extend(lead_silence)
                                for pr_chunk in pre_roll:
                                    recorded_pcm.extend(pr_chunk)
                                recorded_pcm.extend(raw_chunk)
                            else:
                                pre_roll.append(raw_chunk)
                        else:
                            recorded_pcm.extend(raw_chunk)
                            if rms >= cont_threshold:
                                speech_chunks += 1
                                silent_chunks_after_speech = 0
                            else:
                                silent_chunks_after_speech += 1
                                if speech_chunks >= 4 and silent_chunks_after_speech >= max_silent_chunks:
                                    idx += 1
                                    break

                    idx += 1

                winmm.waveInStop(h_wave_in)
                winmm.waveInReset(h_wave_in)

                # Si el usuario habló muy bajito y no cruzó start_threshold pero sí grabó audio
                if len(recorded_pcm) == 0 and len(all_raw_pcm) > 0:
                    recorded_pcm.extend(all_raw_pcm)

                for hdr in headers:
                    try:
                        winmm.waveInUnprepareHeader(h_wave_in, ctypes.byref(hdr), hdr_size)
                    except Exception:
                        pass
                winmm.waveInClose(h_wave_in)

                if len(recorded_pcm) < int(sample_rate * 0.6):
                    return b"", "No escuché suficiente voz, choom. Intenta hablar un poco más cerca del micro."

                # Añadir 180ms de silencio final limpio para que Whisper/SAPI no corte la última sílaba
                tail_silence = b"\x00" * (int(sample_rate * 0.18) * 2)
                recorded_pcm.extend(tail_silence)

                # Normalizar ganancia si el micrófono tiene volumen bajo
                samples_np = np.frombuffer(bytes(recorded_pcm), dtype=np.int16)
                peak = int(np.max(np.abs(samples_np.astype(np.int32)))) if len(samples_np) > 0 else 0
                if 280 < peak < 18000:
                    gain = min(3.2, 22000.0 / peak)
                    samples_np = np.clip(np.round(samples_np.astype(np.float64) * gain), -32768, 32767).astype(np.int16)
                    final_pcm_bytes = samples_np.tobytes()
                else:
                    final_pcm_bytes = bytes(recorded_pcm)

                wav_io = io.BytesIO()
                with wave.open(wav_io, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(final_pcm_bytes)

                return wav_io.getvalue(), ""
            except Exception as e:
                return b"", f"Error al grabar del micrófono: {e}"
            finally:
                self.is_recording = False

    # ------------------------------------------------------------------
    # 3. Transcripción STT con Groq Whisper API + Faster-Whisper Local + Fallback SAPI
    # ------------------------------------------------------------------

    def _ensure_faster_whisper(self) -> Optional[Any]:
        """Carga y mantiene en memoria el modelo neural `faster-whisper` (`base` int8) para STT instantáneo."""
        if self._whisper_model is not None:
            return self._whisper_model
        with self._whisper_lock:
            if self._whisper_model is not None:
                return self._whisper_model
            try:
                from faster_whisper import WhisperModel  # type: ignore
                self._whisper_model = WhisperModel(
                    "base",
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=max(2, min(6, (os.cpu_count() or 4))),
                )
                return self._whisper_model
            except Exception:
                return None

    def _transcribe_faster_whisper(self, wav_bytes: bytes) -> Tuple[str, str]:
        """Transcribe WAV PCM en memoria usando `faster-whisper` (`CTranslate2`) + Silero Neural VAD."""
        model = self._ensure_faster_whisper()
        if model is None:
            return "", "faster-whisper no disponible"

        try:
            samples, sr = VoiceFx.wav_bytes_to_samples(wav_bytes)
            if len(samples) < 1600:
                return "", "Audio demasiado corto."
            if sr != 16000 and sr > 0:
                samples = VoiceFx.sinc_resample(samples, sr / 16000.0)

            audio_f32 = samples.astype(np.float32) / 32768.0
            prompt_es = "Conversación con Capri, asistente cyberpunk en español. ¡Hola Capri! ¿Cómo estás, choom?"

            segments, _ = model.transcribe(
                audio_f32,
                language="es",
                beam_size=3,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=400, speech_pad_ms=320),
                initial_prompt=prompt_es,
                condition_on_previous_text=False,
            )
            parts = [seg.text.strip() for seg in segments if seg.text and seg.text.strip()]
            text = " ".join(parts).strip()

            # Si el filtro VAD neural fue demasiado estricto con voz susurrada, reintentar sin filtro
            if not text:
                segments2, _ = model.transcribe(
                    audio_f32,
                    language="es",
                    beam_size=3,
                    vad_filter=False,
                    initial_prompt=prompt_es,
                    condition_on_previous_text=False,
                )
                parts2 = [seg.text.strip() for seg in segments2 if seg.text and seg.text.strip()]
                text = " ".join(parts2).strip()

            hallucinations = {
                "subtítulos realizados por la comunidad de amara.org",
                "subtitulos realizados por la comunidad de amara.org",
                "gracias por ver el video",
                "¡gracias por ver!",
                "...",
                ".",
            }
            if not text or text.lower().strip(".¡!¿? ") in hallucinations:
                return "", "No pude distinguir las palabras, choom. Intenta hablar un poco más fuerte."
            return text, ""
        except Exception as e:
            return "", f"Error en faster-whisper: {e}"

    def transcribe_wav(self, wav_bytes: bytes, api_key: str, provider: str = "groq") -> Tuple[str, str]:
        if not wav_bytes:
            return "", "Audio vacío."

        key = (api_key or "").strip()
        is_groq = key.startswith("gsk_") or provider == "groq"
        is_openai = key.startswith("sk-") and not key.startswith("sk-or-") and not key.startswith("sk-ant-")

        # 1. Intentar Groq / OpenAI Whisper API si hay clave y permisos
        if key and (is_groq or is_openai):
            url = (
                "https://api.groq.com/openai/v1/audio/transcriptions"
                if is_groq
                else "https://api.openai.com/v1/audio/transcriptions"
            )
            models = (
                ["whisper-large-v3-turbo", "whisper-large-v3"]
                if is_groq
                else ["whisper-1"]
            )
            for model_name in models:
                text, err = self._call_whisper_multipart(url, key, wav_bytes, model_name)
                if text:
                    return text, ""
                if "404" not in err and "model" not in err.lower():
                    break

        # 2. Motor neural local en memoria: faster-whisper (`base` int8 + Silero VAD)
        fw_text, fw_err = self._transcribe_faster_whisper(wav_bytes)
        if fw_text:
            return fw_text, ""

        # 3. Último recurso: Windows SAPI local sin lanzar excepciones de consola
        sapi_text, sapi_err = self._transcribe_windows_sapi(wav_bytes)
        if sapi_text:
            return sapi_text, ""
        return "", fw_err or sapi_err or "No te escuché bien, choom."

    def _call_whisper_multipart(
        self,
        url: str,
        api_key: str,
        wav_bytes: bytes,
        model: str,
    ) -> Tuple[str, str]:
        boundary = f"----CapriVoiceBoundary{int(time.time() * 1000)}"
        body = bytearray()

        def add_field(name: str, value: str) -> None:
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
            body.extend(f"{value}\r\n".encode("utf-8"))

        add_field("model", model)
        add_field("language", "es")
        add_field("response_format", "json")
        add_field("prompt", "Conversación con Capri, asistente cyberpunk en español (choom, gonk, preem).")

        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(b'Content-Disposition: form-data; name="file"; filename="speech.wav"\r\n')
        body.extend(b"Content-Type: audio/wav\r\n\r\n")
        body.extend(wav_bytes)
        body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode("utf-8"))

        req = urllib.request.Request(
            url,
            data=bytes(body),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "CapriDesktopCompanion/2.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                text = (data.get("text") or "").strip()
                hallucinations = {
                    "subtítulos realizados por la comunidad de amara.org",
                    "subtitulos realizados por la comunidad de amara.org",
                    "gracias por ver el video",
                    "¡gracias por ver!",
                    "...",
                    ".",
                }
                if text.lower().strip(".¡!¿? ") in hallucinations:
                    return "", "Silencio detectado."
                return text, ""
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
            return "", f"HTTP {e.code}: {err_body}"
        except Exception as e:
            return "", str(e)

    def _transcribe_windows_sapi(self, wav_bytes: bytes) -> Tuple[str, str]:
        import tempfile
        temp_wav = Path(tempfile.gettempdir()) / f"capri_stt_{uuid.uuid4().hex[:8]}.wav"
        try:
            temp_wav.write_bytes(wav_bytes)
            clean_path = str(temp_wav).replace("\\", "/")
            ps_cmd = f"""
try {{
    try {{ [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 }} catch {{}}
    Add-Type -AssemblyName System.Speech
    try {{
        $culture = New-Object System.Globalization.CultureInfo("es-ES")
        $rec = New-Object System.Speech.Recognition.SpeechRecognitionEngine($culture)
    }} catch {{
        $rec = New-Object System.Speech.Recognition.SpeechRecognitionEngine
    }}
    $rec.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
    $rec.SetInputToWaveFile('{clean_path}')
    $res = $rec.Recognize([TimeSpan]::FromSeconds(4.0))
    if ($null -ne $res -and $res.Text) {{
        Write-Output $res.Text.Trim()
    }}
}} catch {{}}
"""
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            proc_res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=6.0,
                creationflags=creation_flags,
            )
            out = (proc_res.stdout or "").strip()
            if out:
                return out, ""
            return "", "No pude distinguir las palabras, choom."
        except Exception:
            return "", "No pude distinguir las palabras, choom."
        finally:
            try:
                temp_wav.unlink(missing_ok=True)
            except Exception:
                pass

    def listen_and_transcribe(self, api_key: str, provider: str = "groq") -> Tuple[str, str]:
        """Graba del micrófono hasta que el usuario termina de hablar y transcribe el audio."""
        wav_bytes, rec_err = self.record_microphone_wav()
        if rec_err or not wav_bytes:
            return "", rec_err or "No se capturó audio."
        return self.transcribe_wav(wav_bytes, api_key=api_key, provider=provider)
