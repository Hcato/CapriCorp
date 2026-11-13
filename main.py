"""
Orquestador Principal del Asistente Claret (Core Loop).
Integra AudioListener (STT), LLMRouter (Ollama) y VoiceSynthesizer (TTS)
en un flujo interactivo asíncrono, modular y de baja latencia.
"""

import asyncio
import logging
import signal
import sys
from typing import Optional

from config import stt_config, llm_config, tts_config
from audio_listener import AudioListener
from llm_router import LLMRouter
from voice_synth import VoiceSynthesizer

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("ClaretCore")

BANNER = r"""
============================================================
       __    ___    ____  ______ ______
      / /   /   |  / __ \/ ____//_  __/
     / /   / /| | / /_/ / __/    / /   
    / /___/ ___ |/ _, _/ /___   / /    
   /_____/_/  |_/_/ |_/_____/  /_/     
   Asistente Modular de IA para Windows 11
============================================================
"""


class ClaretAssistant:
    """
    Orquestador del Asistente Claret. Coordina el ciclo continuo:
    Micrófono -> STT -> Enrutador LLM -> TTS -> Altavoz.
    """

    def __init__(self):
        print(BANNER)
        print(">> Inicializando subsistemas del Asistente Claret...\n")

        # 1. Sintetizador de voz (TTS)
        self.synth = VoiceSynthesizer(tts_config)

        # 2. Enrutador LLM (Ollama)
        self.router = LLMRouter(llm_config)

        # 3. Captura y Transcripción de Audio (STT faster-whisper)
        self.listener = AudioListener(stt_config)

        self._running = False
        self._exit_keywords = ["salir", "apagar", "adiós", "adios", "terminar", "cerrar asistente", "apágate"]

    async def startup(self) -> None:
        """Verifica dependencias externas y emite saludo inicial."""
        # Verificar estado del servidor Ollama
        ollama_ready = await self.router.check_connection()
        if not ollama_ready:
            print("\n[AVISO IMPORTANTE]: Ollama no respondió en http://localhost:11434.")
            print(f"Asegúrate de haber iniciado Ollama y tener el modelo '{llm_config.model}' listo.")
            print("El asistente continuará, pero las consultas darán aviso de conexión.\n")

        # Mensaje de bienvenida auditivo y visual
        modo_texto = (
            f"Mantén presionada la tecla [{stt_config.push_to_talk_key.upper()}] para hablar"
            if stt_config.listen_mode == "push_to_talk"
            else "Detección continua de voz (VAD) activa"
        )

        print("-" * 60)
        print(f"• STT: faster-whisper ('{stt_config.model_name}') en {stt_config.device.upper()}")
        print(f"• LLM: Ollama ('{llm_config.model}')")
        print(f"• TTS: edge-tts ('{tts_config.voice}')")
        print(f"• Modo de entrada: {modo_texto}")
        print("• Para salir: Di 'adiós', 'salir' o presiona Ctrl+C en esta consola.")
        print("-" * 60 + "\n")

        await self.synth.speak("Asistente Claret en línea y listo. ¿En qué te puedo ayudar?")

    async def run(self) -> None:
        """Bucle principal de interacción continua (Core Loop)."""
        await self.startup()
        self._running = True

        while self._running:
            try:
                # 1. Captura de audio y transcripción (ejecutado en hilo separado para no bloquear async loop)
                user_text = await asyncio.to_thread(self.listener.listen_and_transcribe)

                if not user_text or not user_text.strip():
                    await asyncio.sleep(0.1)
                    continue

                print(f"\n[Usuario]: {user_text}")

                # 2. Verificación de comando de apagado por voz
                clean_lower = user_text.lower().strip()
                if any(exit_word in clean_lower for exit_word in self._exit_keywords):
                    despedida = "Hasta pronto. Que tengas un excelente día."
                    print(f"[Claret]: {despedida}")
                    await self.synth.speak(despedida)
                    self._running = False
                    break

                # 3. Enrutamiento y Generación Cognitiva con Ollama
                print("[Claret pensando y enrutando...]", end="\r", flush=True)
                route_result = await self.router.route_and_respond(user_text)

                route = route_result.get("route", "chat")
                spoken_response = route_result.get("spoken_response", "")
                action = route_result.get("action")

                # 4. Mostrar información de enrutamiento (Router Pattern)
                print(f"[Enrutador] -> Ruta asignada: [{route.upper()}]")
                if action:
                    print(f"[Acción Detectada]: {action}")

                # 5. Reproducción de la respuesta de voz
                if spoken_response:
                    print(f"[Claret]: {spoken_response}")
                    await self.synth.speak(spoken_response)
                else:
                    print("[Claret]: (Sin respuesta generada)")

            except (KeyboardInterrupt, asyncio.CancelledError):
                print("\nInterrupción recibida. Deteniendo asistente...")
                self._running = False
                break
            except Exception as e:
                logger.error(f"Error imprevisto en el bucle principal: {e}", exc_info=True)
                await asyncio.sleep(1.0)

        self.shutdown()

    def shutdown(self) -> None:
        """Cierra recursos de forma limpia."""
        print("\n>> Cerrando subsistemas de audio y liberando memoria...")
        self.synth.close()
        print(">> Asistente Claret finalizado.")


def main():
    """Punto de entrada con gestión de eventos y señales."""
    assistant = ClaretAssistant()

    # Manejar cierre por Ctrl+C
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(assistant.run())
    except KeyboardInterrupt:
        print("\nCierre manual detectado.")
    finally:
        assistant.shutdown()
        loop.close()


if __name__ == "__main__":
    main()
