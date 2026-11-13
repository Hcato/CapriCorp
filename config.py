"""
Módulo de Configuración Centralizada para el Asistente Claret.
Define parámetros de audio, modelos STT/LLM/TTS y comportamientos del enrutador.
"""

from dataclasses import dataclass
import os

@dataclass
class STTConfig:
    # 'base' o 'small' recomendados para latencia mínima en RTX 4050
    model_name: str = "base"
    # 'cuda' para aprovechar los 6 GB VRAM de la RTX 4050; fallback a 'cpu' si no hay CUDA
    device: str = "cuda"
    # 'float16' en GPU Turing/Ampere/Ada o 'int8_float16' para conservar VRAM
    compute_type: str = "float16"
    language: str = "es"
    sample_rate: int = 16000
    # Umbral de silencio para VAD (Voice Activity Detection)
    silence_threshold: float = 0.015
    # Segundos continuos de silencio para considerar que el usuario dejó de hablar
    silence_limit_seconds: float = 1.2
    # Modo de escucha: 'push_to_talk' o 'vad' (detección continua por voz)
    listen_mode: str = "push_to_talk"
    # Tecla para Push-to-Talk (espacio, f8, alt_r, etc.)
    push_to_talk_key: str = "space"


@dataclass
class LLMConfig:
    host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    # 'qwen2.5:3b' o 'llama3.2'
    model: str = "qwen2.5:3b"
    temperature: float = 0.6
    # Contexto máximo en tokens para respuestas concisas y rápidas
    max_tokens: int = 250
    system_prompt: str = (
        "Eres Claret, un asistente de IA conversacional y enrutador de tareas para Windows 11. "
        "Tu objetivo es ser conciso, natural y amigable, ya que tus respuestas serán leídas en voz alta por un sintetizador de voz (TTS). "
        "REGLAS CRÍTICAS: "
        "1. Responde SIEMPRE en español de forma directa y conversacional (máximo 2 o 3 oraciones). "
        "2. NUNCA uses viñetas, listas numeradas, bloques de código ni formato markdown como asteriscos (**) en respuestas orales directas. "
        "3. Clasifica la intención del usuario entre las siguientes rutas: "
        "- 'chat': conversación casual, preguntas cotidianas o aclaraciones. "
        "- 'system': órdenes del sistema operativo (abrir programas, volumen, brillo, capturas). "
        "- 'agent_search': peticiones que requieren buscar información en la web o consultar fuentes externas. "
        "- 'agent_code': peticiones complejas de programación o scripts. "
        "Devuelve tu salida estrictamente en formato JSON con la siguiente estructura: "
        '{"route": "chat"|"system"|"agent_search"|"agent_code", "spoken_response": "Texto para ser hablado", "action": null o "descripción_accion"}'
    )


@dataclass
class TTSConfig:
    # Voces de alta calidad y naturales en español con edge-tts:
    # 'es-ES-AlvaroNeural' (España, masculino)
    # 'es-ES-ElviraNeural' (España, femenino)
    # 'es-MX-DaliaNeural' (México, femenino)
    # 'es-MX-JorgeNeural' (México, masculino)
    voice: str = "es-ES-AlvaroNeural"
    rate: str = "+0%"
    pitch: str = "+0Hz"
    # Frecuencia de muestreo estándar para pygame
    playback_frequency: int = 24000


# Instancias globales por defecto
stt_config = STTConfig()
llm_config = LLMConfig()
tts_config = TTSConfig()
