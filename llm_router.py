"""
Módulo de Enrutador LLM (Router Pattern) utilizando la librería oficial de Ollama.
Conecta con modelos ligeros locales (Qwen 2.5:3b / Llama 3.2) para clasificar la intención
y generar respuestas concisas optimizadas para sintetizadores de voz (TTS).
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
import httpx
import ollama
from ollama import AsyncClient

try:
    from config import LLMConfig, llm_config
except ImportError:
    from dataclasses import dataclass
    @dataclass
    class LLMConfig:
        host: str = "http://localhost:11434"
        model: str = "qwen2.5:3b"
        temperature: float = 0.6
        max_tokens: int = 250
        system_prompt: str = "Eres Claret, un asistente conciso y amigable."
    llm_config = LLMConfig()

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("LLMRouter")


class LLMRouter:
    """
    Enrutador cognitivo inicial y cerebro conversacional.
    Evalúa el input del usuario para decidir si es una conversación directa
    o si debe delegarse a un sub-agente especializado (sistema, código, búsqueda).
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or llm_config
        self.client = AsyncClient(host=self.config.host)
        # Memoria conversacional de turnos recientes (máximo 10 mensajes)
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history_turns = 10

    def _clean_json_string(self, text: str) -> str:
        """Extrae el bloque JSON de la respuesta del modelo si viene envuelto en markdown."""
        text = text.strip()
        # Buscar bloque ```json ... ```
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            return json_match.group(1).strip()
        # Buscar primer { y último }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start:end + 1].strip()
        return text

    async def check_connection(self) -> bool:
        """Verifica si el servidor de Ollama está accesible y si el modelo está disponible."""
        try:
            models_response = await self.client.list()
            # La respuesta de ollama.list() contiene una lista de modelos
            available_models = [m.model for m in models_response.models] if hasattr(models_response, 'models') else []
            logger.info(f"Ollama conectado en {self.config.host}. Modelos disponibles: {available_models}")

            # Comprobar si el modelo objetivo o una variante con etiqueta (:latest) existe
            target = self.config.model.split(":")[0]
            matched = any(target in m for m in available_models)
            if not matched and available_models:
                logger.warning(
                    f"El modelo '{self.config.model}' no parece estar en Ollama. "
                    f"Ejecuta en tu terminal: 'ollama pull {self.config.model}'"
                )
            return True
        except (httpx.ConnectError, ConnectionRefusedError):
            logger.error(
                f"No se pudo conectar a Ollama en {self.config.host}. "
                "Asegúrate de que la aplicación Ollama esté abierta o ejecuta 'ollama serve'."
            )
            return False
        except Exception as e:
            logger.warning(f"Error al verificar estado de Ollama: {e}")
            return False

    async def route_and_respond(self, user_text: str) -> Dict[str, Any]:
        """
        Envía el texto del usuario a Ollama, mantiene el historial y retorna
        la ruta clasificada ('chat', 'system', 'agent_search', 'agent_code')
        junto con el texto para ser hablado por el TTS.
        """
        if not user_text.strip():
            return {
                "route": "none",
                "spoken_response": "",
                "action": None,
                "raw": ""
            }

        # Preparar mensajes incluyendo el prompt del sistema y el historial
        messages = [{"role": "system", "content": self.config.system_prompt}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_text})

        try:
            response = await self.client.chat(
                model=self.config.model,
                messages=messages,
                options={
                    "temperature": self.config.temperature,
                    "num_predict": self.config.max_tokens,
                }
            )

            raw_response = response.message.content.strip()
            logger.debug(f"Respuesta bruta de Ollama: {raw_response}")

            # Intentar parsear el JSON estructurado
            cleaned_json = self._clean_json_string(raw_response)
            try:
                parsed = json.loads(cleaned_json)
                route = parsed.get("route", "chat")
                spoken = parsed.get("spoken_response", raw_response)
                action = parsed.get("action", None)
            except json.JSONDecodeError:
                # Si el modelo respondió en texto libre en lugar de JSON, usarlo directamente
                logger.warning("El modelo no retornó JSON estricto; usando respuesta directa en modo chat.")
                route = "chat"
                spoken = raw_response
                action = None

            # Actualizar memoria conversacional para turnos siguientes
            self._update_history(user_text, spoken)

            return {
                "route": route,
                "spoken_response": spoken,
                "action": action,
                "raw": raw_response
            }

        except (httpx.ConnectError, ConnectionRefusedError):
            fallback_msg = "No puedo conectarme con Ollama. Por favor, verifica que el servicio esté iniciado en tu equipo."
            return {
                "route": "error",
                "spoken_response": fallback_msg,
                "action": None,
                "raw": "ConnectionError"
            }
        except ollama.ResponseError as oe:
            fallback_msg = f"Error en el modelo Ollama: {oe.error}."
            logger.error(fallback_msg)
            return {
                "route": "error",
                "spoken_response": "Hubo un problema con el modelo local de Ollama.",
                "action": None,
                "raw": str(oe)
            }
        except Exception as e:
            logger.error(f"Error inesperado en LLMRouter: {e}")
            return {
                "route": "error",
                "spoken_response": "Ocurrió un error al procesar tu solicitud.",
                "action": None,
                "raw": str(e)
            }

    def _update_history(self, user_msg: str, assistant_msg: str) -> None:
        """Mantiene una ventana deslizante de memoria para no saturar el contexto."""
        self.conversation_history.append({"role": "user", "content": user_msg})
        self.conversation_history.append({"role": "assistant", "content": assistant_msg})
        if len(self.conversation_history) > (self.max_history_turns * 2):
            self.conversation_history = self.conversation_history[-(self.max_history_turns * 2):]

    def reset_history(self) -> None:
        """Reinicia la memoria de la conversación actual."""
        self.conversation_history.clear()
        logger.info("Historial de conversación reiniciado.")


if __name__ == "__main__":
    import asyncio

    async def test_router():
        print("Iniciando prueba unitaria de LLMRouter...")
        router = LLMRouter()
        is_ok = await router.check_connection()
        print(f"Conexión con Ollama: {'Exitosa' if is_ok else 'Fallida'}")

        pregunta = "Hola, ¿cómo estás hoy y qué hora es aproximadamente?"
        print(f"\nPreguntando: '{pregunta}'")
        res = await router.route_and_respond(pregunta)
        print(f"Ruta clasificada: {res['route']}")
        print(f"Respuesta hablada: {res['spoken_response']}")
        print(f"Acción: {res['action']}")

    asyncio.run(test_router())
