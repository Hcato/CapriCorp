"""
Módulo de Síntesis de Voz (Text-to-Speech) y Reproducción de Audio.
Utiliza 'edge-tts' para generar voces neuronales hiperrealistas con 0 consumo de VRAM
y 'pygame.mixer' para la reproducción asíncrona no bloqueante en Windows 11.
"""

import asyncio
import io
import logging
import os
import re
import tempfile
from typing import Optional
import edge_tts
import pygame

try:
    from config import TTSConfig, tts_config
except ImportError:
    from dataclasses import dataclass
    @dataclass
    class TTSConfig:
        voice: str = "es-ES-AlvaroNeural"
        rate: str = "+0%"
        pitch: str = "+0Hz"
        playback_frequency: int = 24000
    tts_config = TTSConfig()

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("VoiceSynth")


class VoiceSynthesizer:
    """
    Sintetizador de voz basado en Microsoft Edge TTS con reproducción
    fluida y sin bloqueos mediante pygame.
    """

    def __init__(self, config: Optional[TTSConfig] = None):
        self.config = config or tts_config
        self._temp_audio_file: Optional[str] = None
        self._init_audio_player()

    def _init_audio_player(self) -> None:
        """Inicializa el mezclador de sonido de pygame."""
        try:
            if not pygame.mixer.get_init():
                # Inicialización con buffer reducido para menor latencia de inicio
                pygame.mixer.init(frequency=self.config.playback_frequency, size=-16, channels=2, buffer=1024)
            logger.info("Reproductor de audio pygame inicializado correctamente.")
        except Exception as e:
            logger.error(f"Error al inicializar pygame.mixer: {e}")

    def clean_text_for_speech(self, text: str) -> str:
        """
        Limpia símbolos de markdown, URLs y caracteres especiales que suenan
        mal cuando son leídos literalmente por el sintetizador de voz.
        """
        if not text:
            return ""

        # Eliminar bloques de código ```...```
        cleaned = re.sub(r"```[\s\S]*?```", " [código omitido] ", text)
        # Eliminar código en línea `...`
        cleaned = re.sub(r"`.*?`", "", cleaned)
        # Eliminar enlaces markdown [texto](url)
        cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
        # Eliminar asteriscos de negrita/cursiva y almohadillas de títulos
        cleaned = re.sub(r"[*_#~>]", "", cleaned)
        # Eliminar URLs directas
        cleaned = re.sub(r"https?://\S+", "enlace web", cleaned)
        # Normalizar espacios en blanco repetidos
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    async def speak(self, text: str) -> None:
        """
        Genera el audio a partir del texto y lo reproduce de forma asíncrona.
        No bloquea el bucle de eventos principal durante la reproducción.
        """
        clean_text = self.clean_text_for_speech(text)
        if not clean_text:
            return

        logger.info(f"Sintetizando voz ({self.config.voice}): \"{clean_text}\"")

        # Crear archivo temporal único para almacenar el MP3 generado
        temp_fd, temp_path = tempfile.mkstemp(suffix=".mp3", prefix="claret_voice_")
        os.close(temp_fd)  # Cerramos el descriptor inmediatamente para que edge-tts pueda escribirlo

        try:
            # 1. Síntesis con Edge-TTS
            communicate = edge_tts.Communicate(
                text=clean_text,
                voice=self.config.voice,
                rate=self.config.rate,
                pitch=self.config.pitch
            )
            await communicate.save(temp_path)

            # 2. Carga y reproducción con pygame.mixer
            if not pygame.mixer.get_init():
                self._init_audio_player()

            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.play()

            # Esperar de forma asíncrona a que termine la reproducción
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.05)

        except Exception as e:
            logger.error(f"Error en la síntesis o reproducción de audio: {e}")

        finally:
            # Crucial en Windows: liberar el archivo con unload() antes de intentar borrarlo
            try:
                if pygame.mixer.get_init():
                    pygame.mixer.music.unload()
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as cleanup_error:
                logger.debug(f"Aviso de limpieza temporal: {cleanup_error}")

    def stop(self) -> None:
        """Detiene inmediatamente cualquier audio que se esté reproduciendo."""
        try:
            if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
        except Exception as e:
            logger.debug(f"Error al detener audio: {e}")

    def close(self) -> None:
        """Cierra el subsistema de audio y libera recursos."""
        self.stop()
        try:
            if pygame.mixer.get_init():
                pygame.mixer.quit()
        except Exception:
            pass


if __name__ == "__main__":
    # Prueba individual del módulo
    async def test_tts():
        print("Iniciando prueba unitaria de VoiceSynthesizer...")
        synth = VoiceSynthesizer()
        mensaje = "Hola, soy Claret. Mi sintetizador de voz neuronal está funcionando al cien por ciento."
        await synth.speak(mensaje)
        synth.close()
        print("Prueba de audio completada.")

    asyncio.run(test_tts())
