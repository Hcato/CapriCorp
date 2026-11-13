"""
Módulo de Captura de Audio y Speech-to-Text (STT) con faster-whisper.
Optimizado para baja latencia en GPU NVIDIA (CUDA) con fallback automático a CPU.
"""

import sys
import time
import logging
import threading
from typing import Optional, Tuple
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from pynput import keyboard

try:
    from config import STTConfig, stt_config
except ImportError:
    # Respaldo si se ejecuta como script individual
    from dataclasses import dataclass
    @dataclass
    class STTConfig:
        model_name: str = "base"
        device: str = "cuda"
        compute_type: str = "float16"
        language: str = "es"
        sample_rate: int = 16000
        silence_threshold: float = 0.015
        silence_limit_seconds: float = 1.2
        listen_mode: str = "push_to_talk"
        push_to_talk_key: str = "space"
    stt_config = STTConfig()

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("AudioListener")


class AudioListener:
    """
    Gestiona la captura de audio del micrófono y la transcripción ultrarrápida
    utilizando faster-whisper con aceleración CUDA.
    """

    def __init__(self, config: Optional[STTConfig] = None):
        self.config = config or stt_config
        self.sample_rate = self.config.sample_rate
        self.model: Optional[WhisperModel] = None
        self._is_recording = False
        self._recorded_chunks = []
        self._lock = threading.Lock()
        self._init_model()

    def _init_model(self) -> None:
        """Inicializa WhisperModel intentando CUDA primero y degradando a CPU si es necesario."""
        logger.info(f"Cargando faster-whisper ({self.config.model_name})...")
        try:
            if self.config.device == "cuda":
                logger.info(f"Intentando inicializar modelo en GPU con compute_type='{self.config.compute_type}'...")
                self.model = WhisperModel(
                    self.config.model_name,
                    device="cuda",
                    compute_type=self.config.compute_type
                )
                logger.info("faster-whisper cargado exitosamente en NVIDIA CUDA (GPU).")
            else:
                raise ValueError("Configurado para CPU.")
        except Exception as e:
            logger.warning(
                f"No se pudo inicializar en CUDA ({e}). "
                "Activando fallback seguro a CPU con compute_type='int8'..."
            )
            try:
                self.model = WhisperModel(
                    self.config.model_name,
                    device="cpu",
                    compute_type="int8"
                )
                logger.info("faster-whisper cargado exitosamente en CPU.")
            except Exception as cpu_error:
                logger.error(f"Error crítico cargando faster-whisper en CPU: {cpu_error}")
                raise cpu_error

    def transcribe_array(self, audio_data: np.ndarray) -> str:
        """
        Transcribe directamente un array de NumPy (float32, 16kHz) en memoria
        sin requerir I/O de archivos temporales en disco.
        """
        if self.model is None or audio_data is None or len(audio_data) == 0:
            return ""

        # Asegurar formato float32 mono
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)

        start_t = time.perf_counter()
        try:
            # vad_filter filtra pausas previas y posteriores para máxima precisión
            segments, info = self.model.transcribe(
                audio_data,
                beam_size=3,
                language=self.config.language,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=400)
            )

            text_segments = [segment.text.strip() for segment in segments]
            full_text = " ".join(text_segments).strip()
            elapsed = time.perf_counter() - start_t
            
            if full_text:
                logger.info(f"Transcripción ({elapsed:.2f}s): \"{full_text}\"")
            return full_text

        except Exception as e:
            logger.error(f"Error durante la transcripción de audio: {e}")
            return ""

    def record_push_to_talk(self, trigger_key: Optional[str] = None) -> Optional[np.ndarray]:
        """
        Modo Push-to-Talk (PTT): Graba mientras se mantiene presionada una tecla.
        Por defecto utiliza la barra espaciadora ('space').
        """
        target_key_name = trigger_key or self.config.push_to_talk_key
        logger.info(f"Modo Push-to-Talk listo. Mantén presionada [{target_key_name.upper()}] para hablar...")

        audio_chunks = []
        is_pressed = threading.Event()
        stop_listener = threading.Event()

        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.debug(f"Audio stream status: {status}")
            if is_pressed.is_set():
                audio_chunks.append(indata.copy())

        def on_press(key):
            try:
                # Comprobar si coincide con la tecla objetivo
                if (hasattr(key, 'char') and key.char == target_key_name) or \
                   (hasattr(key, 'name') and key.name == target_key_name):
                    if not is_pressed.is_set():
                        is_pressed.set()
                        print("\n[Grabando audio...] Habla ahora...", flush=True)
            except Exception as e:
                logger.debug(f"Error on_press: {e}")

        def on_release(key):
            try:
                if (hasattr(key, 'char') and key.char == target_key_name) or \
                   (hasattr(key, 'name') and key.name == target_key_name):
                    if is_pressed.is_set():
                        is_pressed.clear()
                        print("[Grabación detenida. Procesando...]", flush=True)
                        stop_listener.set()
                        return False  # Detiene el listener de pynput
            except Exception as e:
                logger.debug(f"Error on_release: {e}")

        # Iniciar listener de teclado en hilo secundario
        key_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        key_listener.start()

        # Abrir stream de audio del micrófono
        with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='float32', callback=audio_callback):
            while not stop_listener.is_set():
                time.sleep(0.05)

        key_listener.join()

        if not audio_chunks:
            return None

        # Concatenar todos los fragmentos capturados
        recorded_audio = np.concatenate(audio_chunks, axis=0).flatten()
        return recorded_audio

    def record_vad(self, max_duration_sec: float = 20.0) -> Optional[np.ndarray]:
        """
        Modo VAD (Detección continua de voz):
        Detecta cuándo el usuario comienza a hablar por el nivel de energía RMS,
        y se detiene automáticamente tras 'silence_limit_seconds' de silencio.
        """
        logger.info("Modo VAD activo. Escuchando micrófono...")
        chunk_duration = 0.05  # 50 ms por bloque
        chunk_samples = int(self.sample_rate * chunk_duration)
        
        audio_buffer = []
        has_spoken = False
        silence_start_time = None
        start_time = time.time()

        with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='float32') as stream:
            while True:
                # Lectura sincrónica de bloque
                chunk, overflow = stream.read(chunk_samples)
                chunk = chunk.flatten()
                
                # Calcular energía RMS del bloque actual
                rms = np.sqrt(np.mean(chunk**2)) if len(chunk) > 0 else 0.0

                if rms > self.config.silence_threshold:
                    if not has_spoken:
                        has_spoken = True
                        print("[Voz detectada...] Escuchando...", flush=True)
                    audio_buffer.append(chunk)
                    silence_start_time = None
                elif has_spoken:
                    # El usuario ya habló pero el bloque actual es silencioso
                    audio_buffer.append(chunk)
                    if silence_start_time is None:
                        silence_start_time = time.time()
                    elif (time.time() - silence_start_time) >= self.config.silence_limit_seconds:
                        print("[Silencio detectado. Finalizando captura...]", flush=True)
                        break

                # Tiempo límite de seguridad para evitar grabaciones infinitas
                if (time.time() - start_time) > max_duration_sec:
                    if has_spoken:
                        logger.info("Límite de tiempo máximo alcanzado.")
                    break

        if not audio_buffer or not has_spoken:
            return None

        return np.concatenate(audio_buffer, axis=0)

    def listen_and_transcribe(self) -> str:
        """
        Método de conveniencia de alto nivel: captura audio según el modo configurado
        y devuelve el texto transcrito.
        """
        if self.config.listen_mode == "push_to_talk":
            audio_data = self.record_push_to_talk()
        else:
            audio_data = self.record_vad()

        if audio_data is None or len(audio_data) < (self.sample_rate * 0.4):
            # Audio demasiado corto o vacío (menos de 400ms)
            return ""

        return self.transcribe_array(audio_data)


if __name__ == "__main__":
    # Prueba individual del módulo
    print("Iniciando prueba unitaria de AudioListener...")
    listener = AudioListener()
    print("Presiona Espacio para probar la grabación Push-to-Talk:")
    result = listener.listen_and_transcribe()
    print(f"Resultado final: '{result}'")
