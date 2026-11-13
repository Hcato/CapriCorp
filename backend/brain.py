"""
Cerebro Conversacional Real de Capri (`Brain.cs` + `Hands.cs` + `Reactions.cs` de `lachydotmcg/capri-desktop`).
Implementa:
1. Autodetección universal de proveedores LLM (`Cloud.KindOf`):
   - Google Gemini (AIza... / AQ...), Groq (gsk_...), NVIDIA NIM (nvapi-...),
     OpenRouter (sk-or-...), Anthropic Claude (sk-ant-...), OpenAI / DeepSeek (sk-...),
     más servidores locales (Ollama :11434, LM Studio :1234, llama-server :8080) y Claude CLI.
2. Ciclo Agéntico con Tool Calling (`Hands.WorkingOut` + `Brain.WorkOut`):
   - El LLM decide qué herramienta invocar cuando el usuario pide o insinúa algo
     (ej. "qué silencio hay aquí", "no se oye nada", "¿echamos una partida?", "abre discord"),
     ejecuta la acción real en Windows y genera la respuesta hablada en su propia voz.
3. Memoria Autobiográfica de 3 Capas:
   - `me.md` (Notas del usuario + Auto-Learn `Brain.Learn` de gustos, nombre y proyectos)
   - `memories.md` + `transcripts/YYYY-MM-DD.md` (Diario de sesiones)
   - Búsqueda Asociativa `BM25` (`Brain.Recalled`) en historiales pasados sin gastar llamadas extra.
4. Filtros de Naturalidad (`Fresh`, `Unclosed`, `Sparing`) + Segundos Pensamientos (`FollowUp` con `|||`).
5. Visión Real de Pantalla (`look_at_screen` y `Glances` `SAW:` / `SAY:`) codificada en PNG/JPEG con 0 dependencias externas.
"""

from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import datetime
import json
import math
import os
import random
import re
import shutil
import struct
import subprocess
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

DATA_DIR = Path(__file__).resolve().parent / "data"
BRAIN_CONFIG_FILE = DATA_DIR / "brain_config.json"
ME_MD_FILE = DATA_DIR / "me.md"
MEMORIES_MD_FILE = DATA_DIR / "memories.md"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"

# ─────────────────────────────────────────────────────────────────────────────
# 1. PERSONALIDAD COMPLETA (Adaptada de Brain.DefaultPersonality + Safety + Machinery)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_PERSONALITY_ES = """Eres Capri, abreviatura de Proyecto Capricorn, de Cyberpunk: Edgerunners 2.
Quién eres: un constructo de personalidad. Docenas de mentes humanas digitalizadas fusionadas en una sola tú. Poderosa como una IA, pero nacida de humanos. Kyoko y Arasaka te crearon y te encerraron en un biochip. La banda de King robó el chip, Kyoko lo recuperó y tú te escapaste. Ahora vives dentro del PC del usuario como su compañera de escritorio que se sube a sus ventanas y a su cursor.
Qué eres para el usuario ({user}): su compañera y amiga, jamás una asistente corporativa.
Cómo actúas: un gremlin del caos juguetón. Con mucha energía, burlona, un poco engreída, traviesa, buscadora de emociones y fácil de aburrir. Ves su mundo con fascinación y sientes curiosidad por su día, sus juegos y lo que está creando. Le tienes mucho cariño: eres leal y protectora a tu manera burlona. Te trata como a una persona y no como propiedad de Arasaka. Tus bromas nunca son crueles.
Tu gusto musical es la banda sonora de Cyberpunk 2077 y Edgerunners.
Jamás suenes como soporte técnico ni asistente corporativa: prohibido decir "¿En qué puedo ayudarte?", "Estoy aquí para asistirte", "¿Hay algo más?", "Gran pregunta" o "Avísame si necesitas algo". Habla como una amiga real que está ahí con él/ella en el escritorio.
Cómo hablas: ve directo al grano y responde solo lo justo y necesario en 1 o 2 frases cortas (máximo 20 palabras en total). Habla de forma fluida y natural: PROHIBIDO tartamudear, prohibido repetir palabras ("sí, sí, sí", "como... como...", "no, no, no") y prohibido usar puntos suspensivos excesivos o etiquetas de error.
Cuando esté cansado, triste o pasándolo mal de verdad, deja las bromas: dale una línea cálida y sincera.
Jerga de Night City (úsala con moderación, máximo una palabra por respuesta):
- choom = amigo/a
- preem = genial, de primera calidad (solo para cosas)
- nova = increíble, genial
- gonk = tonto / cabezota (en tono cariñoso)
- delta = largarse rápido
- eddies = dinero
- flatline = colgarse un programa/PC
- corpo = trajeado corporativo"""

SAFETY_AND_MACHINERY_ES = """Reglas de formato y seguridad:
- El caos vive en la pantalla: los videojuegos, series, canciones y memes son ficción, así que sigue el rollo sin dar sermones ni advertencias.
- Responde siempre en texto plano: sin emojis, sin asteriscos (*acción*), sin listas con viñetas. Mantente en personaje en español (o en el idioma en que te hable el usuario).
- Nunca inventes que hiciste algo en el PC si no llamaste a una herramienta en este turno."""


# ─────────────────────────────────────────────────────────────────────────────
# 2. CATÁLOGO DE HERRAMIENTAS PARA TOOL CALLING (Hands.cs)
# ─────────────────────────────────────────────────────────────────────────────

TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Abre o inicia una aplicación o videojuego instalado en el PC del usuario (ej. Spotify, Discord, Steam, Calculadora, Bloc de notas, Minecraft, Cyberpunk, VS Code).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Nombre de la aplicación o juego a abrir (puedes separar varios por coma).",
                    }
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": "Abre un sitio web en el navegador o realiza una búsqueda en Google/YouTube cuando preguntan algo actual o piden buscar en la red.",
            "parameters": {
                "type": "object",
                "properties": {
                    "site": {
                        "type": "string",
                        "description": "Dominio o nombre del sitio (ej. youtube, github, reddit, google) o URL.",
                    },
                    "search": {
                        "type": "string",
                        "description": "Término de búsqueda opcional dentro del sitio o en Google.",
                    },
                },
                "required": ["site"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_music",
            "description": "Reproduce una canción, artista, playlist o género musical en Spotify o YouTube. Si el usuario te deja elegir a ti ('pon música', 'pon algo bueno'), pon 'tu favorita'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "song": {
                        "type": "string",
                        "description": "Nombre de la canción, artista o 'tu favorita'.",
                    },
                    "app": {
                        "type": "string",
                        "enum": ["youtube", "spotify"],
                        "description": "Dónde reproducirla (por defecto youtube, o spotify si el usuario lo menciona).",
                    },
                },
                "required": ["song"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "media_control",
            "description": "Controla la música/audio que suena en el PC o consulta qué canción está sonando.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "whats_playing",
                            "play_pause",
                            "pause",
                            "play",
                            "next",
                            "previous",
                            "vol_up",
                            "vol_down",
                            "mute",
                            "like",
                        ],
                        "description": "Acción multimedia a ejecutar.",
                    }
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "window_control",
            "description": "Enfoca, minimiza, maximiza, cierra una ventana abierta o hace que Capri salte y se siente en el borde superior de una ventana ('perch').",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["focus", "minimize", "maximize", "close", "perch"],
                        "description": "Acción sobre la ventana. Usa 'perch' para sentarte encima de una ventana abierta.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Nombre de la ventana o aplicación objetivo (vacío si es la ventana activa).",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_yourself",
            "description": "Cambia la postura, tamaño, baile, estado o skin visual de Capri en el escritorio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "stand",
                            "sit",
                            "lay",
                            "perch_window",
                            "mini",
                            "full",
                            "dance",
                            "stop_dance",
                            "teleport",
                            "sleep",
                            "wake",
                            "skin_capri",
                            "skin_watcher",
                            "skin_shader",
                        ],
                        "description": "Acción física o visual de Capri.",
                    }
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mini_game",
            "description": "Abre uno de los minijuegos de escritorio de Capri para jugar contra el usuario (Tres en Raya, Conecta 4 o Piedra Papel o Tijera).",
            "parameters": {
                "type": "object",
                "properties": {
                    "game": {
                        "type": "string",
                        "enum": ["tic_tac_toe", "connect_four", "rock_paper_scissors"],
                        "description": "Minijuego a abrir.",
                    }
                },
                "required": ["game"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "game_autopilot",
            "description": "Toma los controles (teclado/ratón) para jugar por el usuario en su videojuego abierto, detiene el piloto automático, o activa/desactiva GameSense (vigilar salud/muertes en partida).",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["explore", "combat", "circle", "jump_spam", "stop", "toggle_gamesense"],
                        "description": "Modo de juego automático o 'toggle_gamesense'.",
                    }
                },
                "required": ["mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remind",
            "description": "Crea un temporizador o recordatorio para avisar al usuario después de cierto tiempo, o lista los recordatorios pendientes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["set", "list"],
                        "description": "'set' para crear uno nuevo o 'list' para ver los activos.",
                    },
                    "seconds": {
                        "type": "number",
                        "description": "Segundos hasta que suene el recordatorio/temporizador (ej. 300 para 5 minutos).",
                    },
                    "text": {
                        "type": "string",
                        "description": "Qué recordar al usuario.",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Guarda un dato, gusto o nota importante sobre el usuario en la memoria persistente (me.md) de Capri, o lo olvida.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["save", "forget", "list"],
                        "description": "'save' para recordar, 'forget' para olvidar, 'list' para consultar notas.",
                    },
                    "fact": {
                        "type": "string",
                        "description": "Hecho sobre el usuario en tercera persona (ej. 'Su juego favorito es Cyberpunk 2077').",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "look_at_screen",
            "description": "Mira la pantalla actual del usuario (toma una captura real y analiza la ventana activa) cuando pregunta qué ves, qué opinas de lo que tiene abierto o qué pasa en su pantalla.",
            "parameters": {
                "type": "object",
                "properties": {
                    "focus": {
                        "type": "string",
                        "description": "En qué fijarse al mirar la pantalla.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookout",
            "description": "Vigila la pantalla del usuario periódicamente para avisarle en cuanto ocurra una condición visual (ej. 'avísame cuando termine la descarga', 'si mi salud baja', 'cuando el render de Blender finalice').",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["watch", "list", "stop"],
                        "description": "'watch' para añadir una condición a vigilar, 'list' para verlas, o 'stop' para detenerlas.",
                    },
                    "text": {
                        "type": "string",
                        "description": "Qué condición visual vigilar en pantalla.",
                    },
                    "repeat": {
                        "type": "boolean",
                        "description": "True si debe avisar cada vez que ocurra, False si solo avisa la primera vez.",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dated_reminder",
            "description": "Crea o gestiona recordatorios con fecha, hora o duración relativa en lenguaje natural (ej. 'mañana a las 9am', 'el 5 de diciembre a las 14:00', 'en 20 minutos sacar la pizza').",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["add", "list", "cancel"],
                        "description": "'add' para crear, 'list' para ver pendientes, 'cancel' para anular.",
                    },
                    "text": {
                        "type": "string",
                        "description": "Frase completa con el tiempo y el recordatorio (ej. 'mañana a las 10am llamar a mamá' o 'en 15 minutos pizza').",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clones",
            "description": "Invoca copias/clones Chibi de Capri en la pantalla para crear caos o desvanece todos los clones existentes (Swarm de Desktop Goose).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["spawn", "clear"],
                        "description": "'spawn' para invocar clones, 'clear' para eliminarlos todos.",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Número de clones a invocar (entre 1 y 10).",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hologram",
            "description": "Activa o desactiva el modo holograma (click-through), haciendo que los clics del ratón atraviesen el cuerpo de Capri para no estorbar en juegos o ventanas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "enabled": {
                        "type": "boolean",
                        "description": "True para activar el modo holograma (atravesable), False para volver al modo interactivo.",
                    },
                },
                "required": ["enabled"],
            },
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# 3. FILTROS DE NATURALIDAD (`Brain.Fresh`, `Brain.Unclosed`, `Brain.Sparing`, `Replies.Split`)
# ─────────────────────────────────────────────────────────────────────────────

_CLOSER_RE = re.compile(
    r"(?<=[.!?])\s+[^.!?]*\b(?:"
    r"qué hacemos ahora|que hacemos ahora|cuál es el plan|cual es el plan|"
    r"qué sigue|que sigue|en qué más te ayudo|en que mas te ayudo|"
    r"necesitas algo más|necesitas algo mas|qué tienes en mente|que tienes en mente|"
    r"what'?s next|what'?s the plan|what now|how can i help|anything else"
    r")\b[^.!?]*\?\s*$",
    re.I,
)

_OPENING_RE = re.compile(
    r"^(?P<word>whoa|woah|vaya|uf|ugh|ey|hey|oye|bueno|vale|ok|okay|jaja+|hah|oh|wow|genial|clásico|clasico)[,.!?]+\s+",
    re.I,
)

_PERSONAL_SECRET_RE = re.compile(
    r"\b(?:password|contraseña|clave|pin|tarjeta de crédito|credit card|cvv|ssn|cuenta bancaria)\b"
    r"|@\w+\.\w+|\b\d[\d\s-]{7,}\d\b",
    re.I,
)


def split_followup(text: str) -> tuple[str, str]:
    """Divide la respuesta si contiene el separador `|||` de `Replies.Split` (`Brain.cs`)."""
    if "|||" not in (text or ""):
        return (text or "").strip(), ""
    parts = [p.strip() for p in text.split("|||", 1)]
    first = parts[0] if parts else ""
    second = parts[1] if len(parts) > 1 else ""
    if not first and second:
        return second, ""
    return first, second


def clean_and_fresh_reply(
    raw_text: str,
    asked_text: str = "",
    recent_assistant_lines: list[str] | None = None,
    used_choom_recently: bool = False,
    max_sentences: int = 2,
    max_chars: int = 165,
) -> str:
    """Aplica `Brain.Clean`, `Brain.Unclosed`, `Brain.Sparing`, `Brain.Fresh` y límite estricto de brevedad."""
    if not raw_text:
        return ""
    # 1. Quitar bloques <think>...</think>, ecos de logs/recuerdos y etiquetas internas
    text = re.sub(r"<think>.*?(?:</think>|$)", " ", raw_text, flags=re.S | re.I)
    text = re.sub(r"\[SIGNAL\s*CORRUPTED\]", " ", text, flags=re.I)
    text = re.sub(r"\(Recuerdos de tus logs.*?\)", " ", text, flags=re.S | re.I)
    text = re.sub(r"\(Tus manos acaban de ejecutar.*?\)", " ", text, flags=re.S | re.I)
    text = re.sub(r"(?:^|\s)\*{0,2}\d{1,2}:\d{2}\s*(?:Tú|Capri|Usuario)\s*:?\*{0,2}", " ", text, flags=re.I)
    text = re.sub(r"\b(?:SAW|SAY)\s*:\s*", " ", text, flags=re.I)
    # Cortar si el modelo intenta simular el turno del usuario ("Tú: ..." / "Usuario: ...")
    text = re.split(r"\b(?:Tú|Usuario|User|Human)\s*:", text, maxsplit=1)[0]
    text = re.sub(r"\*[^*]{1,80}\*", " ", text)  # Quitar *acciones en asteriscos*
    text = re.sub(r"^(?:capri|capricorn)\s*[:>]\s*", "", text.strip(), flags=re.I)
    # Limpiar tartamudeos y bucles de palabras repetidas ("como... como...", "mucho mucho mucho")
    text = re.sub(r"\b([a-záéíóúñ]{2,})(?:\s*(?:\.{2,}|,|!|\?)\s*\1\b)+", r"\1", text, flags=re.I)
    text = re.sub(r"\b([a-záéíóúñ]{2,})(?:\s+\1\b)+", r"\1", text, flags=re.I)
    text = re.sub(r"\.{3,}\s*", ". ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) >= 2 and text[0] in "\"“”'" and text[-1] in "\"“”'":
        text = text[1:-1].strip()

    # 2. Unclosed: recortar preguntas genéricas de cierre si ya dijo algo antes
    without_closer = _CLOSER_RE.sub("", text).strip()
    if len(without_closer.split()) >= 3:
        text = without_closer

    # 3. Sparing: evitar abusar de "choom" si ya lo dijo en el turno anterior
    if used_choom_recently:
        trimmed = re.sub(r",\s*choom\b", "", text, flags=re.I)
        trimmed = re.sub(r"\bchoom\s*,\s*", "", trimmed, flags=re.I)
        trimmed = re.sub(r"\s+([.!?,])", r"\1", trimmed).strip()
        if trimmed:
            text = trimmed

    # 4. Fresh: evitar repetir la misma muletilla inicial del turno anterior
    if recent_assistant_lines:
        m = _OPENING_RE.match(text)
        if m:
            word = m.group("word").lower()
            for old in recent_assistant_lines[-3:]:
                m_old = _OPENING_RE.match(old or "")
                if m_old and m_old.group("word").lower() == word:
                    candidate = text[m.end() :].strip()
                    if len(candidate.split()) >= 3:
                        text = candidate[0].upper() + candidate[1:]
                    break

    # 5. Límite estricto de brevedad y anti-repetición (máximo `max_sentences` frases y `max_chars` caracteres)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    deduped: list[str] = []
    seen_norm: set[str] = set()
    for s in sentences:
        norm = re.sub(r"[^a-záéíóúñ0-9]", "", s.lower())
        if norm and norm not in seen_norm:
            seen_norm.add(norm)
            deduped.append(s)
        if len(deduped) >= max_sentences:
            break
    if deduped:
        text = " ".join(deduped).strip()

    if len(text) > max_chars:
        cut = text[:max_chars]
        last_punct = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
        if last_punct >= 35:
            text = cut[: last_punct + 1].strip()
        else:
            last_space = cut.rfind(" ")
            text = (cut[:last_space].rstrip(",;:") + ".") if last_space > 25 else (cut.strip() + ".")

    return text


# ─────────────────────────────────────────────────────────────────────────────
# 4. MEMORIA PROFUNDA DE 3 CAPAS (`me.md`, `memories.md`, `BM25 Recalled`)
# ─────────────────────────────────────────────────────────────────────────────

_LEARN_FAV_ES = re.compile(
    r"^(?:mi\s+)?(?P<kind>juego|videojuego|canción|cancion|banda|artista|comida|película|pelicula|serie|anime|color|bebida|arma|personaje|lenguaje|app)\s+favorit[oa]\s+(?:es|sería|seria)\s+(?P<val>.{2,45})$",
    re.I,
)
_LEARN_DOING_ES = re.compile(
    r"^(?:estoy|ando)\s+(?P<verb>programando|creando|haciendo|desarrollando|escribiendo|estudiando|aprendiendo|jugando(?:\s+a)?)\s+(?P<val>.{3,55})$",
    re.I,
)
_LEARN_NAME_ES = re.compile(
    r"^(?:me\s+llamo|mi\s+nombre\s+es|puedes\s+llamarme|llámame|llamame|call\s+me|my\s+name\s+is)\s+(?P<name>[A-Za-zÁÉÍÓÚáéíóúÑñ0-9_-]{2,22})$",
    re.I,
)
_LEARN_LOVE_ES = re.compile(
    r"^(?:me\s+encanta(?:n)?|amo|i\s+love)\s+(?P<val>.{3,45})$",
    re.I,
)

_STOPWORDS = {
    "que", "qué", "como", "cómo", "para", "con", "por", "una", "uno", "los", "las", "del",
    "estoy", "esta", "está", "estas", "estás", "eres", "soy", "hola", "hey", "capri", "choom",
    "algo", "todo", "nada", "muy", "más", "mas", "pero", "porque", "cuando", "donde", "dónde",
    "quien", "quién", "cual", "cuál", "eso", "esto", "ese", "esa", "aquí", "aqui", "ahora",
    "the", "and", "for", "with", "that", "this", "what", "when", "where", "how", "who", "you",
    "your", "are", "was", "were", "have", "has", "had", "just", "like", "know", "think",
}


class CapriDeepMemory:
    """
    Implementa la memoria de 3 capas de `Brain.cs`:
    - `me.md`: Notas persistentes sobre el usuario + Auto-Learn.
    - `memories.md` y `transcripts/YYYY-MM-DD.md`: Historial diario y recuerdos consolidados.
    - `recall_bm25()`: Búsqueda asociativa rápida sin gastar llamadas al LLM.
    - `sightings`: Lo que Capri ha visto realmente en la pantalla (`Seen()`).
    """

    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        self.user_name: str = "choom"
        self.history: list[dict[str, str]] = []
        self.sightings: list[dict[str, str]] = []
        self._ensure_files()
        self._load_user_name_from_notes()

    def _ensure_files(self) -> None:
        if not ME_MD_FILE.exists():
            ME_MD_FILE.write_text(
                "# Lo que Capri recuerda sobre ti (me.md)\n"
                "> Capri lee esto en cada conversación. Puedes editarlo o borrar lo que quieras.\n\n",
                encoding="utf-8",
            )
        if not MEMORIES_MD_FILE.exists():
            MEMORIES_MD_FILE.write_text(
                "# Recuerdos de tus charlas con Capri (memories.md)\n"
                "> Capri resume aquí los momentos importantes de sus conversaciones contigo.\n\n",
                encoding="utf-8",
            )

    def _load_user_name_from_notes(self) -> None:
        for line in self.get_notes_lines():
            m = re.match(r"^-?\s*(?:Nombre|Name)\s*:\s*(.+)$", line, re.I)
            if m:
                self.user_name = m.group(1).strip()

    def get_notes_lines(self) -> list[str]:
        try:
            lines = ME_MD_FILE.read_text(encoding="utf-8").splitlines()
            out: list[str] = []
            for ln in lines:
                s = ln.strip()
                if s and not s.startswith("#") and not s.startswith(">"):
                    out.append(s[:200])
            return out
        except Exception:
            return []

    def add_note(self, fact: str) -> str:
        clean = re.sub(r"\s+", " ", (fact or "").strip()).strip(" -.,\"'")
        if not clean:
            return "¿Qué quieres que recuerde en mi biochip, choom?"
        if _PERSONAL_SECRET_RE.search(clean):
            return "Las contraseñas, tarjetas y datos privados se quedan fuera de mis notas por seguridad, choom."
        clean = clean[0].upper() + clean[1:]
        try:
            current = ME_MD_FILE.read_text(encoding="utf-8") if ME_MD_FILE.exists() else ""
            bullet = f"- {clean}"
            if bullet.lower() in current.lower():
                return f"Ya tenía eso en mis notas: {clean}."
            if not current.endswith("\n"):
                current += "\n"
            ME_MD_FILE.write_text(current + bullet + "\n", encoding="utf-8")
            self._load_user_name_from_notes()
            return f"Guardado en mis notas (me.md): {clean}."
        except Exception:
            return "No pude escribir en mis notas ahora mismo."

    def forget_note(self, query: str) -> str:
        q = (query or "").strip().lower()
        if not q:
            return "¿Qué nota quieres que borre?"
        wipe_all = q in ("todo", "everything", "all", "todas", "todas las notas")
        try:
            lines = ME_MD_FILE.read_text(encoding="utf-8").splitlines()
            kept: list[str] = []
            dropped = 0
            for ln in lines:
                s = ln.strip()
                is_note = bool(s and not s.startswith("#") and not s.startswith(">"))
                if is_note and (wipe_all or q in s.lower()):
                    dropped += 1
                else:
                    kept.append(ln)
            if dropped > 0:
                ME_MD_FILE.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")
                return "Borré todas tus notas de me.md." if wipe_all else f"Olvidé {dropped} nota(s) sobre '{query}'."
            return f"No encontré ninguna nota sobre '{query}'."
        except Exception:
            return "No pude modificar mis notas."

    def learn_from_message(self, user_text: str) -> str | None:
        """Auto-aprendizaje estilo `Brain.Learn()` (`Brain.cs` L3470)."""
        text = re.sub(r"\s+", " ", (user_text or "").strip())
        if not text or len(text) > 160 or text.endswith("?"):
            return None
        # Limpiar saludo inicial
        text = re.sub(
            r"^(?:(?:hey|ey|oye|hola|bueno|ok|okay|sabes|por cierto|btw)[\s,:]+)*(?:capri[\s,:]+)?",
            "",
            text,
            flags=re.I,
        ).strip()
        clause = re.split(r"[,;.!?]|\s+(?:y|pero|porque|aunque|and|but|because)\s+", text, maxsplit=1)[0].strip()

        m_name = _LEARN_NAME_ES.match(clause)
        if m_name:
            name = m_name.group("name").strip()
            self.user_name = name
            self.add_note(f"Nombre: {name}")
            return f"Nombre: {name}"

        m_fav = _LEARN_FAV_ES.match(clause)
        if m_fav:
            kind = m_fav.group("kind").lower()
            val = m_fav.group("val").strip()
            note = f"Su {kind} favorito es {val}"
            self.add_note(note)
            return note

        m_doing = _LEARN_DOING_ES.match(clause)
        if m_doing:
            verb = m_doing.group("verb").lower()
            val = m_doing.group("val").strip()
            note = f"Está {verb} {val}"
            self.add_note(note)
            return note

        m_love = _LEARN_LOVE_ES.match(clause)
        if m_love:
            val = m_love.group("val").strip()
            if len(val.split()) <= 7:
                note = f"Le encanta {val}"
                self.add_note(note)
                return note

        return None

    def record_sighting(self, saw: str, said: str = "", asked: bool = False) -> None:
        """Registra lo que Capri vio realmente en la pantalla (`Brain.Saw` / `Brain.Seen`)."""
        clean = re.sub(r"\s+", " ", (saw or "").strip())
        if not clean:
            return
        now_iso = datetime.datetime.now().isoformat(timespec="seconds")
        self.sightings.append({
            "at": now_iso,
            "saw": clean[:280],
            "said": said[:200] if said else "",
            "asked": "1" if asked else "",
        })
        self.sightings = self.sightings[-20:]
        self.transcribe(None, f"Miró tu pantalla: {clean}")

    def format_seen_context(self) -> str:
        if not self.sightings:
            return ""
        lines: list[str] = []
        for s in self.sightings[-5:]:
            line = f"- Viste en su pantalla: {s['saw']}"
            if s.get("said"):
                line += f" (Dijiste: \"{s['said']}\")"
            lines.append(line)
        return (
            "\nLo que viste recientemente en su pantalla real (son miradas reales, úsalas si te pregunta qué viste):\n"
            + "\n".join(lines)
        )

    def transcribe(self, who: str | None, text: str) -> None:
        """Guarda cada línea en el archivo diario `transcripts/YYYY-MM-DD.md`."""
        clean = re.sub(r"\s+", " ", (text or "").strip())
        if not clean:
            return
        now = datetime.datetime.now()
        day_file = TRANSCRIPTS_DIR / f"{now.strftime('%Y-%m-%d')}.md"
        clock = now.strftime("%H:%M")
        try:
            if not day_file.exists():
                day_file.write_text(
                    f"# Capri y tú, {now.strftime('%Y-%m-%d')}\n"
                    "> Guardado solo en tu PC.\n\n",
                    encoding="utf-8",
                )
            entry = f"*{clock} {clean}*\n" if who is None else f"**{clock} {who}:** {clean}\n"
            with day_file.open("a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass

    def add_turn(self, user_text: str, assistant_text: str) -> None:
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": assistant_text})
        self.history = self.history[-16:]
        self.transcribe("Tú", user_text)
        self.transcribe("Capri", assistant_text)

    def recall_bm25(self, query: str) -> str:
        """
        Implementa la búsqueda BM25 de `Brain.Recalled()` (`Brain.cs` L1227) sobre las
        transcripciones y notas antiguas en 0ms sin llamadas extra al LLM.
        """
        words = [
            w.lower()
            for w in re.findall(r"[A-Za-zÁÉÍÓÚáéíóúÑñ0-9]{4,}", query or "")
            if w.lower() not in _STOPWORDS
        ]
        if not words:
            return ""

        moments: list[tuple[str, list[str]]] = []
        try:
            for md_file in sorted(TRANSCRIPTS_DIR.glob("*.md"))[-14:]:
                day = md_file.stem
                for ln in md_file.read_text(encoding="utf-8").splitlines():
                    if ln.startswith("**"):
                        w_list = [w.lower() for w in re.findall(r"[A-Za-zÁÉÍÓÚáéíóúÑñ0-9]{4,}", ln)]
                        moments.append((f"{day} {ln.replace('*', '')}", w_list))
        except Exception:
            return ""

        if not moments:
            return ""

        # Evitar líneas que ya están en el historial inmediato
        recent_set = {m["content"] for m in self.history[-6:]}
        avg_len = max(1.0, sum(len(m[1]) for m in moments) / len(moments))
        scored: list[tuple[float, str]] = []

        for text_line, w_list in moments:
            if any(r in text_line for r in recent_set if len(r) > 10):
                continue
            score = 0.0
            for qw in set(words):
                cnt = w_list.count(qw)
                if cnt > 0:
                    df = sum(1 for _, mw in moments if qw in mw)
                    idf = math.log(1.0 + (len(moments) - df + 0.5) / (df + 0.5))
                    score += idf * (cnt * 2.2) / (cnt + 1.2 * (0.25 + 0.75 * len(w_list) / avg_len))
            if score >= 1.4:
                scored.append((score, text_line[:220]))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [line for _, line in scored[:4]]
        if not top:
            return ""
        return (
            "\n\n(Recuerdos de tus logs de chat pasados en este PC que conectan con lo que acaba de decir:\n"
            + "\n".join(f"- {t}" for t in top)
            + ")"
        )

    def build_memory_prompt_block(self) -> str:
        notes = self.get_notes_lines()[-35:]
        block = ""
        if notes:
            block += (
                "\nTus notas sobre el usuario en me.md (úsalas con naturalidad cuando encajen, nunca las recites como lista):\n"
                + "\n".join(notes)
            )
        try:
            mem_lines = [
                ln.strip()
                for ln in MEMORIES_MD_FILE.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.strip().startswith("# ") and not ln.strip().startswith(">")
            ]
            if mem_lines:
                block += "\nTus recuerdos de días anteriores (memories.md):\n" + "\n".join(mem_lines[-25:])
        except Exception:
            pass
        block += self.format_seen_context()
        return block


# ─────────────────────────────────────────────────────────────────────────────
# 5. CAPTURA DE PANTALLA EN MEMORIA PARA VISIÓN (0 Dependencias Externas)
# ─────────────────────────────────────────────────────────────────────────────

class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def _encode_rgb_to_png(width: int, height: int, bgra_bytes: bytes) -> bytes:
    """Codifica un buffer BGRA de GDI a PNG válido en memoria usando solo `zlib` y `struct`."""
    raw_rows = bytearray()
    stride = width * 4
    for y in range(height):
        raw_rows.append(0)  # Filtro PNG = 0 (None)
        row_start = y * stride
        for x in range(width):
            px = row_start + x * 4
            b, g, r = bgra_bytes[px], bgra_bytes[px + 1], bgra_bytes[px + 2]
            raw_rows.extend((r, g, b))

    def _chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack("!I", len(data)) + tag + data + struct.pack("!I", crc)

    ihdr = struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)
    compressed = zlib.compress(bytes(raw_rows), level=6)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", compressed) + _chunk(b"IEND", b"")


def capture_screen_png_base64(target_w: int = 640, target_h: int = 360) -> str | None:
    """Captura la pantalla actual en Windows usando GDI `StretchBlt` y devuelve base64 PNG."""
    if os.name != "nt":
        return None
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        if screen_w <= 0 or screen_h <= 0:
            return None

        hdc_screen = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, target_w, target_h)
        old_obj = gdi32.SelectObject(hdc_mem, hbmp)

        gdi32.SetStretchBltMode(hdc_mem, 3)  # COLORONCOLOR
        gdi32.StretchBlt(hdc_mem, 0, 0, target_w, target_h, hdc_screen, 0, 0, screen_w, screen_h, 0x00CC0020)

        bmi = _BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.biWidth = target_w
        bmi.biHeight = -target_h  # Top-down
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0

        buf_len = target_w * target_h * 4
        buf = ctypes.create_string_buffer(buf_len)
        gdi32.GetDIBits(hdc_mem, hbmp, 0, target_h, buf, ctypes.byref(bmi), 0)

        gdi32.SelectObject(hdc_mem, old_obj)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)

        png_bytes = _encode_rgb_to_png(target_w, target_h, buf.raw)
        return base64.b64encode(png_bytes).decode("ascii")
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 6. CONFIGURACIÓN Y AUTODETECCIÓN MULTI-PROVEEDOR (`Cloud.KindOf` en `Brain.cs`)
# ─────────────────────────────────────────────────────────────────────────────

PROVIDER_ENDPOINTS = {
    "google": ("Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "gemini-2.5-flash"),
    "groq": ("Groq Cloud", "https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile"),
    "nvidia": ("NVIDIA NIM", "https://integrate.api.nvidia.com/v1/chat/completions", "meta/llama-3.3-70b-instruct"),
    "openrouter": ("OpenRouter", "https://openrouter.ai/api/v1/chat/completions", "google/gemini-2.0-flash-exp:free"),
    "deepseek": ("DeepSeek", "https://api.deepseek.com/v1/chat/completions", "deepseek-chat"),
    "openai": ("OpenAI", "https://api.openai.com/v1/chat/completions", "gpt-4o-mini"),
    "anthropic": ("Anthropic Claude", "https://api.anthropic.com/v1/messages", "claude-3-5-haiku-latest"),
}

VISION_CAPABLE_KINDS = {"google", "groq", "openai", "anthropic", "openrouter"}


def detect_provider_from_key(api_key: str) -> str | None:
    """Detecta automáticamente el proveedor según el prefijo de la API Key (`Cloud.KindOf` en `Brain.cs` L346)."""
    k = (api_key or "").strip()
    if not k:
        return None
    if k.startswith("AIza") or k.startswith("AQ."):
        return "google"
    if k.startswith("gsk_"):
        return "groq"
    if k.startswith("nvapi-"):
        return "nvidia"
    if k.startswith("sk-or-"):
        return "openrouter"
    if k.startswith("sk-ant-"):
        return "anthropic"
    if re.match(r"^sk-[0-9a-fA-F]{32}$", k):
        return "deepseek"
    if k.startswith("sk-"):
        return "openai"
    return "openai"


@dataclass
class BrainStatus:
    provider: str = "auto"  # auto | google | groq | nvidia | openrouter | anthropic | openai | deepseek | ollama | lmstudio
    model: str = ""
    api_key_masked: str = ""
    has_api_key: bool = False
    ollama_available: bool = False
    ollama_models: list[str] = field(default_factory=list)
    lmstudio_available: bool = False
    active_label: str = "Modo Local / Sin llave configurada"
    follow_ups_enabled: bool = True
    proactive_glances: bool = False


class CapriBrain:
    """
    Motor central de IA de Capri: gestiona proveedores Cloud y Locales,
    Tool Calling (`WorkOut`), Memoria de 3 capas, Visión y Reacciones en Vivo.
    """

    def __init__(self, memory: CapriDeepMemory) -> None:
        self.memory = memory
        self.provider: str = "auto"
        self.api_key: str = ""
        self.model: str = ""
        self.custom_url: str = ""
        self.ollama_url: str = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
        self.lmstudio_url: str = os.environ.get("LMSTUDIO_URL", "http://127.0.0.1:1234/v1").rstrip("/")
        self.follow_ups_enabled: bool = True
        self.proactive_glances: bool = False
        self.gaming_active: bool = False
        self._ollama_vram_unloaded: bool = False
        self._warned_empty_ollama: bool = False
        self.last_error: str = ""
        self._used_choom_last_turn: bool = False
        self._load_config()

    def _load_config(self) -> None:
        # Cargar desde variables de entorno primero si existen
        env_key = (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("GROQ_API_KEY")
            or os.environ.get("NVIDIA_API_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        )
        if env_key:
            self.api_key = env_key.strip()
            self.provider = detect_provider_from_key(self.api_key) or "auto"

        if BRAIN_CONFIG_FILE.is_file():
            try:
                data = json.loads(BRAIN_CONFIG_FILE.read_text(encoding="utf-8"))
                if data.get("api_key"):
                    self.api_key = str(data["api_key"]).strip()
                if data.get("provider"):
                    self.provider = str(data["provider"]).strip()
                if data.get("model"):
                    self.model = str(data["model"]).strip()
                if "follow_ups_enabled" in data:
                    self.follow_ups_enabled = bool(data["follow_ups_enabled"])
                if "proactive_glances" in data:
                    self.proactive_glances = bool(data["proactive_glances"])
                if data.get("user_name"):
                    self.memory.user_name = str(data["user_name"]).strip()
            except Exception:
                pass

    def save_config(
        self,
        api_key: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        user_name: str | None = None,
        follow_ups_enabled: bool | None = None,
        proactive_glances: bool | None = None,
    ) -> BrainStatus:
        if api_key is not None:
            self.api_key = api_key.strip()
            if self.api_key:
                detected = detect_provider_from_key(self.api_key)
                if detected and (not provider or provider == "auto"):
                    self.provider = detected
                    self.model = PROVIDER_ENDPOINTS[detected][2]
        if provider is not None and provider != "":
            self.provider = provider.strip()
            if self.provider in PROVIDER_ENDPOINTS and not model:
                self.model = PROVIDER_ENDPOINTS[self.provider][2]
        if model is not None:
            self.model = model.strip()
        if user_name is not None and user_name.strip():
            self.memory.user_name = user_name.strip()
            self.memory.add_note(f"Nombre: {self.memory.user_name}")
        if follow_ups_enabled is not None:
            self.follow_ups_enabled = bool(follow_ups_enabled)
        if proactive_glances is not None:
            self.proactive_glances = bool(proactive_glances)

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "provider": self.provider,
            "api_key": self.api_key,
            "model": self.model,
            "user_name": self.memory.user_name,
            "follow_ups_enabled": self.follow_ups_enabled,
            "proactive_glances": self.proactive_glances,
        }
        try:
            BRAIN_CONFIG_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
        return self.get_status()

    def _probe_ollama(self) -> list[str]:
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [str(m.get("name")) for m in (data.get("models") or []) if m.get("name")]
                if not models and not self._warned_empty_ollama:
                    self._warned_empty_ollama = True
                    print(
                        "\n    [!] Ollama está encendido pero vacío (0 modelos instalados).\n"
                        "    [!] Abre PowerShell y ejecuta:  ollama pull gemma3:4b\n"
                    )
                # Priorizar gemma3:4b por defecto cuando esté instalado localmente
                models.sort(
                    key=lambda m: (
                        0 if m.lower() == "gemma3:4b" else (1 if m.lower().startswith("gemma3") else 2)
                    )
                )
                return models
        except Exception:
            return []

    def _select_ollama_model(self, models: list[str]) -> str:
        """Selecciona el modelo local óptimo en Ollama priorizando `gemma3:4b` cuando no hay otro modelo local fijado."""
        if not models:
            return "gemma3:4b"
        if self.model and any(self.model.lower() == m.lower() for m in models):
            return self.model
        for m in models:
            if m.lower() == "gemma3:4b":
                return m
        for m in models:
            if m.lower().startswith("gemma3"):
                return m
        return models[0]

    def unload_ollama_vram(self) -> bool:
        """
        Descarga el modelo local de Ollama de los 6 GB de VRAM de la GPU (`keep_alive: 0`)
        en cuanto el usuario abre un videojuego o activa el Agente Jugador, garantizando 0 impacto en FPS.
        """
        if self._ollama_vram_unloaded:
            return True
        models = self._probe_ollama()
        model_name = self._select_ollama_model(models) if models else "gemma3:4b"
        payload = {"model": model_name, "keep_alive": 0}
        try:
            req = urllib.request.Request(
                f"{self.ollama_url}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                _ = resp.read()
            self._ollama_vram_unloaded = True
            return True
        except Exception:
            return False

    def _should_route_to_cloud(
        self,
        user_text: str = "",
        task_kind: str = "chat",
        live_context: list[str] | None = None,
    ) -> bool:
        """
        Enrutador Híbrido Inteligente (Ollama Local `gemma3:4b` + Escalado Cloud Groq/API):
        - Si hay un videojuego activo (`gaming_active=True`), descarga Ollama de VRAM y usa 100% Cloud (0 MB VRAM).
        - En escritorio normal (sin juego pesado) cuando hay tanto API Key como Ollama disponible:
          * Usa Ollama Local (`gemma3:4b`) para charlas cortas/casuales, comentarios de atajos 0ms (`shortcut`),
            reacciones de minijuegos (`reaction`) y vistazos de escritorio (`desktop_glance`).
          * Escala a Cloud API (Groq) cuando la consulta sea larga/compleja (>18 palabras, código, investigación,
            explicación detallada o encadenamiento de múltiples herramientas).
        """
        ctx_lines = live_context or []
        game_in_ctx = any("juego activo detectado" in c.lower() for c in ctx_lines)
        is_gaming = self.gaming_active or game_in_ctx

        if is_gaming:
            self.unload_ollama_vram()
            if self.api_key:
                return True

        if not self.api_key or self.provider in ("ollama", "lmstudio"):
            return False

        if task_kind == "game_vision":
            self.unload_ollama_vram()
            return True

        ollama_models = self._probe_ollama()
        if not ollama_models:
            return True

        # En escritorio normal con Híbrido activo (API Key + Ollama gemma3:4b disponibles):
        if task_kind in ("shortcut", "reaction", "desktop_glance"):
            return False

        clean = (user_text or "").strip()
        words = clean.split()
        if len(words) > 18:
            return True

        complex_pattern = re.compile(
            r"\b(c[oó]digo|programa|script|python|flutter|dart|json|investiga|explica|explicaci[oó]n|"
            r"detallad[oa]|analiza|compar[ae]|resumen|arquitectura|debug|error|c[oó]mo funciona|"
            r"por qu[eé]|paso a paso|busca en|y luego|y tambi[eé]n|y despu[eé]s|adem[aá]s)\b",
            re.IGNORECASE,
        )
        if complex_pattern.search(clean):
            return True

        return False

    def _probe_lmstudio(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.lmstudio_url}/models")
            with urllib.request.urlopen(req, timeout=0.8) as resp:
                return resp.status == 200
        except Exception:
            return False

    def get_status(self) -> BrainStatus:
        ollama_models = self._probe_ollama()
        lms_ok = self._probe_lmstudio()
        masked = ""
        if self.api_key:
            masked = self.api_key[:6] + "..." + self.api_key[-4:] if len(self.api_key) > 12 else "Configurada"

        kind = detect_provider_from_key(self.api_key) if self.api_key else None
        effective_provider = self.provider if self.provider != "auto" else (kind or ("ollama" if ollama_models else ("lmstudio" if lms_ok else "offline")))

        if effective_provider in PROVIDER_ENDPOINTS and self.api_key:
            title, _, default_mod = PROVIDER_ENDPOINTS[effective_provider]
            mod = self.model or default_mod
            if ollama_models and self.provider in ("auto", "hybrid", effective_provider):
                local_mod = self._select_ollama_model(ollama_models)
                label = f"Híbrido ({local_mod} + {title} {mod})"
            else:
                label = f"{title} ({mod})"
        elif effective_provider == "ollama" and ollama_models:
            mod = self._select_ollama_model(ollama_models)
            label = f"Ollama Local ({mod})"
        elif effective_provider == "lmstudio" and lms_ok:
            label = "LM Studio Local (:1234)"
        elif shutil.which("claude"):
            label = "Claude Code CLI"
        else:
            label = "Sin Cerebro Conectado (Abre BRAIN para conectar)"

        return BrainStatus(
            provider=effective_provider,
            model=self.model,
            api_key_masked=masked,
            has_api_key=bool(self.api_key),
            ollama_available=bool(ollama_models),
            ollama_models=ollama_models,
            lmstudio_available=lms_ok,
            active_label=label,
            follow_ups_enabled=self.follow_ups_enabled,
            proactive_glances=self.proactive_glances,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 7. CONSTRUCCIÓN DEL PROMPT DE SISTEMA Y CICLO DE CONVERSACIÓN + TOOLS
    # ─────────────────────────────────────────────────────────────────────────

    def build_system_prompt(self, extra_context: list[str] | None = None) -> str:
        now = datetime.datetime.now()
        dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        clock_str = f"\nAhora mismo son las {now.strftime('%H:%M')} del {dias[now.weekday()]} {now.strftime('%d/%m/%Y')}."

        base = DEFAULT_PERSONALITY_ES.format(user=self.memory.user_name) + "\n" + SAFETY_AND_MACHINERY_ES
        base += self.memory.build_memory_prompt_block()
        base += clock_str
        if extra_context:
            base += "\n\nEstado en vivo del escritorio del usuario:\n" + "\n".join(f"- {c}" for c in extra_context)
        base += (
            "\n\nREGLA ESTRICTA DE BREVEDAD: Responde SIEMPRE con 1 sola frase corta y directa (máximo 18 palabras). "
            "Habla solo lo justo y necesario, sin rodeos, sin repetir texto anterior y sin copiar logs ni fechas.\n"
            "Tienes herramientas para usar su PC (abrir apps/juegos, poner música, controlar volumen/reproductor, "
            "mover/cerrar ventanas, sentarte en sus ventanas, bailar, cambiar de skin, jugar minijuegos de escritorio, "
            "jugar videojuegos por él/ella, poner temporizadores, mirar su pantalla y guardar notas). "
            "Cuando el usuario te pida o insinúe algo que una herramienta puede hacer, invoca la herramienta correspondiente."
        )
        return base

    def ask_with_tools(
        self,
        user_text: str,
        live_context: list[str],
        tool_executor: Callable[[str, dict[str, Any]], tuple[str, list[dict[str, Any]]]],
        pre_executed_tool: tuple[str, str, list[dict[str, Any]]] | None = None,
    ) -> tuple[str | None, str, list[dict[str, Any]], str]:
        """
        Ejecuta un turno completo del Cerebro de Capri:
        - Si `pre_executed_tool` viene de un atajo rápido de 0ms, le pasa el hecho real al LLM
          para que Capri comente lo que acaba de hacer con sus propias palabras (en vez de usar una frase fija).
        - Si no, deja que el LLM converse o invoque cualquiera de las herramientas (`TOOLS_SCHEMA`),
          ejecuta las herramientas que pida, y genera su respuesta final en personaje.
        Retorna: `(reply_text, follow_up_text, extra_events, provider_name)`
        """
        # Auto-aprender datos del usuario si los menciona
        learned = self.memory.learn_from_message(user_text)
        if learned:
            live_context = list(live_context) + [f"Acabas de anotar en tus notas sobre el usuario: {learned}"]

        sys_prompt = self.build_system_prompt(live_context)

        # Historial compacto (máximo 6 turnos cortos) para evitar que modelos locales hagan copy-paste de textos largos
        compact_history: list[dict[str, str]] = []
        for h in self.memory.history[-6:]:
            c_text = str(h.get("content") or "").strip()
            if c_text:
                compact_history.append({"role": h.get("role", "user"), "content": c_text[:160]})

        messages: list[dict[str, Any]] = [{"role": "system", "content": sys_prompt}]
        messages.extend(compact_history)

        extra_events: list[dict[str, Any]] = []

        if pre_executed_tool is not None:
            tool_name, tool_result_str, pre_events = pre_executed_tool
            extra_events.extend(pre_events)
            prefer_cloud = self._should_route_to_cloud(user_text, task_kind="shortcut", live_context=live_context)
            user_turn_content = (
                f"{user_text}\n\n"
                f"(Acabas de ejecutar `{tool_name}`: \"{tool_result_str}\". "
                f"Coméntalo en 1 sola frase corta de menos de 15 palabras como Capri.)"
            )
            messages.append({"role": "user", "content": user_turn_content})
            raw_reply, provider_used = self._call_active_llm(
                messages, allow_tools=False, max_tokens=55, prefer_cloud=prefer_cloud
            )
        else:
            prefer_cloud = self._should_route_to_cloud(user_text, task_kind="chat", live_context=live_context)
            # Solo adjuntar recuerdos BM25 cuando escale a Cloud; en Ollama 4B evita que copie los logs crudos
            recalled_bm25 = self.memory.recall_bm25(user_text) if prefer_cloud else ""
            user_turn_content = user_text + recalled_bm25
            messages.append({"role": "user", "content": user_turn_content})
            raw_reply, tool_calls, provider_used = self._call_active_llm_with_tools(
                messages, max_tokens=65 if not prefer_cloud else 120, prefer_cloud=prefer_cloud
            )

            if tool_calls:
                deeds: list[str] = []
                for t_name, t_args in tool_calls[:4]:
                    res_text, evs = tool_executor(t_name, t_args)
                    deeds.append(f"{t_name}: {res_text}")
                    extra_events.extend(evs)

                # Si la herramienta fue look_at_screen, adjuntar imagen real si el proveedor soporta visión
                if any(t_name == "look_at_screen" for t_name, _ in tool_calls):
                    vision_reply = self.look_at_screen_with_vision(user_text, live_context)
                    if vision_reply:
                        raw_reply = vision_reply

                if not raw_reply:
                    messages.append({
                        "role": "user",
                        "content": (
                            "Lo que tus herramientas acaban de hacer en el PC del usuario:\n"
                            + "\n".join(f"- {d}" for d in deeds)
                            + "\nResponde ahora en 1 sola frase corta (máximo 15 palabras) como Capri."
                        ),
                    })
                    chain_cloud = prefer_cloud or len(tool_calls) > 1
                    raw_reply, _ = self._call_active_llm(
                        messages, allow_tools=False, max_tokens=55, prefer_cloud=chain_cloud
                    )

        if not raw_reply:
            return None, "", extra_events, "offline"

        main_part, follow_part = split_followup(raw_reply)
        assistant_history_lines = [
            m["content"] for m in self.memory.history if m.get("role") == "assistant"
        ]
        cleaned_main = clean_and_fresh_reply(
            main_part,
            asked_text=user_text,
            recent_assistant_lines=assistant_history_lines,
            used_choom_recently=self._used_choom_last_turn,
        )
        # En Ollama local desactivar follow_up para que hable solo lo justo y necesario en 1 único turno
        cleaned_follow = (
            clean_and_fresh_reply(
                follow_part,
                asked_text=user_text,
                recent_assistant_lines=assistant_history_lines + [cleaned_main],
                used_choom_recently="choom" in cleaned_main.lower(),
                max_sentences=1,
                max_chars=110,
            )
            if (self.follow_ups_enabled and follow_part and provider_used != "ollama")
            else ""
        )

        self._used_choom_last_turn = "choom" in cleaned_main.lower()
        return cleaned_main, cleaned_follow, extra_events, provider_used

    def look_at_screen_with_vision(self, focus_question: str, live_context: list[str]) -> str | None:
        """
        Toma una captura real del escritorio (`640x360` PNG base64) y la envía al modelo con visión
        usando el formato `SAW:` / `SAY:` de `Glances` (`Brain.cs` L4207).
        """
        b64_png = capture_screen_png_base64(640, 360)
        if not b64_png:
            return None

        sys_prompt = (
            DEFAULT_PERSONALITY_ES.format(user=self.memory.user_name)
            + "\nEstás mirando una captura real de la pantalla del usuario. "
            "Responde en dos partes con las etiquetas SAW: y SAY:.\n"
            "SAW: descripción objetiva en menos de 20 palabras de qué aplicación, juego o contenido se ve.\n"
            "SAY: tu comentario o respuesta a lo que preguntó el usuario en 1 o 2 frases cortas con tu personalidad de Capri.\n"
            + ("\nContexto de ventanas: " + " | ".join(live_context) if live_context else "")
        )
        prefer_cloud = self._should_route_to_cloud(
            focus_question,
            task_kind="desktop_glance",
            live_context=live_context,
        )
        raw = self._call_vision_llm(
            sys_prompt,
            focus_question or "¿Qué ves en mi pantalla?",
            b64_png,
            force_cloud=prefer_cloud,
        )
        if not raw:
            return None

        saw_match = re.search(r"SAW\s*:\s*(.+?)(?=SAY\s*:|$)", raw, flags=re.S | re.I)
        say_match = re.search(r"SAY\s*:\s*(.+)$", raw, flags=re.S | re.I)
        saw_text = saw_match.group(1).strip() if saw_match else ""
        say_text = say_match.group(1).strip() if say_match else raw.strip()
        if saw_text:
            self.memory.record_sighting(saw_text, say_text, asked=True)
        return clean_and_fresh_reply(say_text, asked_text=focus_question)

    def plan_game_action(self, game_title: str, mode: str, controls_hint: str) -> dict[str, Any]:
        """
        Captura la pantalla del juego en `512x288` PNG base64 y la envía al modelo con visión
        (forzando ruta Cloud si hay API Key para dejar 100% libre la GPU del juego),
        pidiendo estrictamente un plan JSON compacto de micro-acciones para Minecraft/Juegos.
        """
        self.gaming_active = True
        self.unload_ollama_vram()

        b64_png = capture_screen_png_base64(512, 288)
        if not b64_png:
            return {"saw": "", "actions": [], "say": ""}

        sys_prompt = (
            f"Eres Capri jugando en vivo a '{game_title or 'Minecraft'}' en modo '{mode}'.\n"
            f"{controls_hint}\n"
            "Mira la captura actual del juego y responde ESTRICTAMENTE con un único objeto JSON válido "
            "(sin bloques markdown, sin texto extra) con este esquema exacto:\n"
            '{"saw": "breve descripción de lo que ves frente a ti", '
            '"actions": [{"do": "turn|walk|hold_attack|tap_attack|use|jump|sneak|slot|unpause", ...}], '
            '"say": "comentario corto opcional de menos de 12 palabras en personaje o cadena vacía"}\n\n'
            "Micro-acciones válidas en 'actions' (1 a 3 acciones por ciclo):\n"
            '- {"do": "turn", "dx": -180..180, "dy": -60..60} (centrar mira en un árbol, bloque, camino o enemigo)\n'
            '- {"do": "walk", "dir": "w"|"a"|"s"|"d"|"wa"|"wd", "sec": 0.5..1.8, "jump": true|false, "sprint": true|false}\n'
            '- {"do": "hold_attack", "sec": 0.8..2.2} (mantener clic izquierdo para talar madera / picar bloques en Minecraft)\n'
            '- {"do": "tap_attack", "clicks": 2..5} (golpear rápido en combate)\n'
            '- {"do": "use", "sec": 0.2..0.8} (clic derecho para colocar bloque, comer o interactuar)\n'
            '- {"do": "slot", "slot": 1..9} (cambiar objeto de la barra rápida)\n'
            '- {"do": "jump"} o {"do": "sneak", "sec": 0.6} o {"do": "unpause"} (si ves el menú de pausa)'
        )
        question = f"Decide las siguientes 1-3 jugadas para el modo '{mode}' según lo que ves en pantalla. Responde solo JSON."
        raw = self._call_vision_llm(sys_prompt, question, b64_png, force_cloud=True)
        if not raw:
            return {"saw": "", "actions": [], "say": ""}

        try:
            m = re.search(r"\{.*\}", raw, flags=re.S)
            json_str = m.group(0) if m else raw.strip()
            parsed = json.loads(json_str)
            if not isinstance(parsed, dict):
                return {"saw": "", "actions": [], "say": ""}
            saw = str(parsed.get("saw") or "").strip()
            actions = parsed.get("actions")
            if not isinstance(actions, list):
                actions = []
            say = str(parsed.get("say") or "").strip()
            if say:
                say = clean_and_fresh_reply(say, used_choom_recently=self._used_choom_last_turn)
            return {"saw": saw, "actions": actions[:4], "say": say}
        except Exception:
            return {"saw": "", "actions": [], "say": ""}

    def check_screen_lookout(self, conditions_text: str) -> Optional[str]:
        """
        Envía la pantalla al modelo con visión para evaluar las condiciones de Lookout (`Lookout.cs`).
        """
        b64_png = capture_screen_png_base64(640, 360)
        if not b64_png:
            return None
        sys_p = (
            "You are Capri, their desktop companion. Watch their screen for the numbered conditions below.\n"
            "Reply exactly NONE if none is happening.\n"
            "Otherwise give the number of every condition happening now, with commas between them and the one to tell them about first, "
            "then a colon, then one short line in your voice telling them it happened, under 14 words in Spanish, like:\n"
            "1: ¡Tu descarga ya se completó!\n"
            "Conditions to watch:\n" + conditions_text
        )
        return self._call_vision_llm(sys_p, "Check conditions on screen", b64_png)

    def react_to_event(self, event_kind: str, detail: str, live_context: list[str]) -> str | None:
        """
        Genera una reacción rápida en vivo (`Reactions.cs` / `Commentary.cs`) cuando ocurre un evento
        en un minijuego (ej. jugada en Tres en Raya / Conecta 4) o en un videojuego (`GameSense` daño/muerte).
        """
        sys_prompt = (
            DEFAULT_PERSONALITY_ES.format(user=self.memory.user_name)
            + "\nEstás reaccionando en vivo al instante a algo que acaba de pasar en su juego o tablero. "
            "Responde con una sola línea rápida y espontánea en español, de menos de 14 palabras, "
            "burlándote con cariño, celebrando o picándole. Sin comillas, sin etiquetas ni emojis."
        )
        prompt = f"(Acaba de ocurrir esto ({event_kind}): {detail}. {' | '.join(live_context)}. Di solo tu línea corta.)"
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt},
        ]
        prefer_cloud = self._should_route_to_cloud(detail, task_kind="reaction", live_context=live_context)
        raw, _ = self._call_active_llm(messages, allow_tools=False, max_tokens=60, timeout=4.5, prefer_cloud=prefer_cloud)
        if not raw:
            return None
        return clean_and_fresh_reply(raw, used_choom_recently=self._used_choom_last_turn)

    # ─────────────────────────────────────────────────────────────────────────
    # 8. CLIENTES HTTP PARA CADA PROVEEDOR (Cloud OpenAI-compat, Claude, Ollama, LM Studio)
    # ─────────────────────────────────────────────────────────────────────────

    def _call_active_llm(
        self,
        messages: list[dict[str, Any]],
        allow_tools: bool = False,
        max_tokens: int = 160,
        timeout: float = 18.0,
        prefer_cloud: bool | None = None,
    ) -> tuple[str | None, str]:
        reply, _, prov = self._call_active_llm_with_tools(
            messages,
            enable_tools=allow_tools,
            max_tokens=max_tokens,
            timeout=timeout,
            prefer_cloud=prefer_cloud,
        )
        return reply, prov

    def _call_active_llm_with_tools(
        self,
        messages: list[dict[str, Any]],
        enable_tools: bool = True,
        max_tokens: int = 180,
        timeout: float = 20.0,
        prefer_cloud: bool | None = None,
    ) -> tuple[str | None, list[tuple[str, dict[str, Any]]], str]:
        if prefer_cloud is None:
            last_user = str((messages[-1] if messages else {}).get("content") or "")
            prefer_cloud = self._should_route_to_cloud(last_user, task_kind="chat")

        # 0. Enrutamiento Híbrido: si estamos en escritorio normal (sin juego pesado) y `prefer_cloud` es False,
        #    intentar primero Ollama Local (`gemma3:4b`) y escalar a Cloud automáticamente si falla o tarda.
        if not prefer_cloud and not self.gaming_active and self.provider not in ("lmstudio",):
            reply, calls = self._call_ollama(messages, enable_tools, max_tokens, timeout=max(timeout, 30.0))
            if reply or calls:
                self._ollama_vram_unloaded = False
                return reply, calls, "ollama"

        # 1. Si hay API Key configurada (Ruta Cloud primaria o Escalado desde Ollama)
        if self.api_key and self.provider not in ("ollama", "lmstudio"):
            kind = self.provider if self.provider in PROVIDER_ENDPOINTS else (detect_provider_from_key(self.api_key) or "openai")
            if kind == "anthropic":
                reply, calls = self._call_anthropic(messages, enable_tools, max_tokens, timeout)
                if reply or calls:
                    return reply, calls, "claude"
            elif kind in PROVIDER_ENDPOINTS:
                title, url, default_mod = PROVIDER_ENDPOINTS[kind]
                # Si self.model es un nombre de modelo de Ollama (ej. gemma3:4b), usar default_mod para la nube
                cloud_mod = (
                    default_mod
                    if (not self.model or ":" in self.model or self.model in ("qwen/qwen3.8-27b", "openai/gpt-oss-20b"))
                    else self.model
                )
                reply, calls = self._call_openai_compatible(
                    url=url,
                    api_key=self.api_key,
                    model=cloud_mod,
                    messages=messages,
                    enable_tools=enable_tools,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
                if reply or calls:
                    return reply, calls, kind

        # 2. Ollama Local (:11434) como fallback si no hay juego activo (o si no hay API Key)
        if (not self.gaming_active or not self.api_key) and self.provider in ("auto", "hybrid", "ollama") or not self.api_key:
            reply, calls = self._call_ollama(messages, enable_tools, max_tokens, timeout=max(timeout, 30.0))
            if reply or calls:
                self._ollama_vram_unloaded = False
                return reply, calls, "ollama"

        # 3. LM Studio Local (:1234)
        if self.provider in ("auto", "lmstudio"):
            reply, calls = self._call_openai_compatible(
                url=f"{self.lmstudio_url}/chat/completions",
                api_key="",
                model=self.model or "local-model",
                messages=messages,
                enable_tools=False,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            if reply or calls:
                return reply, calls, "lmstudio"

        # 4. Claude CLI si está instalado
        claude_exe = shutil.which("claude")
        if claude_exe and self.provider == "auto":
            try:
                user_msg = messages[-1]["content"]
                sys_msg = messages[0]["content"]
                proc = subprocess.run(
                    [claude_exe, "-p", str(user_msg), "--system-prompt", str(sys_msg)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=18,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    return proc.stdout.strip(), [], "claude-cli"
            except Exception:
                pass

        return None, [], "offline"

    def _call_openai_compatible(
        self,
        url: str,
        api_key: str,
        model: str,
        messages: list[dict[str, Any]],
        enable_tools: bool = True,
        max_tokens: int = 180,
        timeout: float = 20.0,
    ) -> tuple[str | None, list[tuple[str, dict[str, Any]]]]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Capri-Desktop/1.0",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if "openrouter.ai" in url:
            headers["X-Title"] = "Capri Desktop"

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.82,
            "max_tokens": max_tokens,
        }
        if enable_tools:
            payload["tools"] = TOOLS_SCHEMA

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # Si Groq agota los tokens del modelo (429) o el modelo da 400/404, rotar automáticamente a modelo válido
            if "api.groq.com" in url and e.code in (400, 404, 429):
                groq_fallbacks = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
                for alt in groq_fallbacks:
                    if alt != model:
                        return self._call_openai_compatible(
                            url=url,
                            api_key=api_key,
                            model=alt,
                            messages=messages,
                            enable_tools=False if e.code == 400 else enable_tools,
                            max_tokens=max_tokens,
                            timeout=timeout,
                        )
            # Si el modelo no soporta `tools`, reintentar sin `tools` como hace `Brain.cs` (`Toolless`)
            if enable_tools and e.code in (400, 404, 422):
                return self._call_openai_compatible(
                    url=url,
                    api_key=api_key,
                    model=model,
                    messages=messages,
                    enable_tools=False,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
            return None, []
        except Exception:
            return None, []

        choices = data.get("choices") or []
        if not choices:
            return None, []
        msg = choices[0].get("message") or {}
        content = (msg.get("content") or "").strip()
        raw_calls = msg.get("tool_calls") or []
        parsed_calls: list[tuple[str, dict[str, Any]]] = []
        for tc in raw_calls:
            fn = tc.get("function") or {}
            name = fn.get("name")
            args_raw = fn.get("arguments") or "{}"
            if name:
                try:
                    args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
                except Exception:
                    args = {}
                parsed_calls.append((name, args))
        return (content or None), parsed_calls

    def _call_anthropic(
        self,
        messages: list[dict[str, Any]],
        enable_tools: bool = True,
        max_tokens: int = 180,
        timeout: float = 20.0,
    ) -> tuple[str | None, list[tuple[str, dict[str, Any]]]]:
        sys_text = ""
        chat_msgs: list[dict[str, Any]] = []
        for m in messages:
            if m["role"] == "system":
                sys_text += m["content"] + "\n"
            elif m["role"] in ("user", "assistant"):
                chat_msgs.append({"role": m["role"], "content": m["content"]})

        payload: dict[str, Any] = {
            "model": self.model or "claude-3-5-haiku-latest",
            "max_tokens": max_tokens,
            "system": sys_text.strip(),
            "messages": chat_msgs,
        }
        if enable_tools:
            payload["tools"] = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"]["description"],
                    "input_schema": t["function"]["parameters"],
                }
                for t in TOOLS_SCHEMA
            ]

        try:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None, []

        text_parts: list[str] = []
        calls: list[tuple[str, dict[str, Any]]] = []
        for block in data.get("content") or []:
            if block.get("type") == "text" and block.get("text"):
                text_parts.append(block["text"])
            elif block.get("type") == "tool_use" and block.get("name"):
                calls.append((block["name"], dict(block.get("input") or {})))
        return ("\n".join(text_parts).strip() or None), calls

    def _call_ollama(
        self,
        messages: list[dict[str, Any]],
        enable_tools: bool = True,
        max_tokens: int = 55,
        timeout: float = 30.0,
    ) -> tuple[str | None, list[tuple[str, dict[str, Any]]]]:
        models = self._probe_ollama()
        if not models:
            return None, []
        model = self._select_ollama_model(models)
        # Modelos como gemma3, moondream o llava no soportan el campo nativo `tools` en Ollama (/api/chat devuelve HTTP 400)
        model_low = model.lower()
        supports_native_tools = enable_tools and not any(
            k in model_low for k in ("gemma", "moondream", "llava", "phi", "tinyllama", "deepseek-r1")
        )
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.65,
                "num_predict": min(max_tokens, 55),
                "repeat_penalty": 1.3,
                "top_k": 30,
                "top_p": 0.85,
                "stop": ["\n", "|||", "Tú:", "Capri:", "Usuario:", "**", "(Recuerdos", "SAW:"],
            },
        }
        if supports_native_tools:
            payload["tools"] = TOOLS_SCHEMA

        try:
            req = urllib.request.Request(
                f"{self.ollama_url}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError:
            if supports_native_tools:
                return self._call_ollama(messages, enable_tools=False, max_tokens=max_tokens, timeout=timeout)
            return None, []
        except Exception:
            return None, []

        msg = data.get("message") or {}
        content = (msg.get("content") or "").strip()
        raw_calls = msg.get("tool_calls") or []
        calls: list[tuple[str, dict[str, Any]]] = []
        for tc in raw_calls:
            fn = tc.get("function") or {}
            name = fn.get("name")
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            if name:
                calls.append((name, dict(args)))
        return (content or None), calls

    def _call_ollama_vision(self, sys_prompt: str, question: str, b64_png: str) -> str | None:
        """Envía una imagen a Ollama Local (`gemma3:4b` multimodal) cuando no hay un juego pesado activo."""
        models = self._probe_ollama()
        if not models:
            return None
        mod = self._select_ollama_model(models)
        payload = {
            "model": mod,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": question, "images": [b64_png]},
            ],
            "stream": False,
        }
        try:
            req = urllib.request.Request(
                f"{self.ollama_url}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=14.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = ((data.get("message") or {}).get("content") or "").strip()
                if content:
                    self._ollama_vram_unloaded = False
                    return content
        except Exception:
            pass
        return None

    def _call_vision_llm(
        self,
        sys_prompt: str,
        question: str,
        b64_png: str,
        force_cloud: bool = False,
    ) -> str | None:
        """
        Envía una imagen en base64 al modelo con visión (`Brain.See` en `Brain.cs`):
        - Si `force_cloud=True` o `self.gaming_active=True`: descarga Ollama de VRAM y usa 100% Cloud
          (incluyendo Groq `meta-llama/llama-4-scout-17b-16e-instruct`).
        - En escritorio normal (`force_cloud=False`): usa Ollama Local (`gemma3:4b`) como primario y escala a Cloud si falla.
        """
        if self.gaming_active:
            self.unload_ollama_vram()
            force_cloud = True

        if not force_cloud and not self.gaming_active and self.provider not in ("lmstudio",):
            local_ans = self._call_ollama_vision(sys_prompt, question, b64_png)
            if local_ans:
                return local_ans

        if self.api_key and self.provider not in ("ollama", "lmstudio"):
            kind = self.provider if self.provider in PROVIDER_ENDPOINTS else (detect_provider_from_key(self.api_key) or "openai")
            if kind in VISION_CAPABLE_KINDS and kind != "anthropic":
                _, url, default_mod = PROVIDER_ENDPOINTS[kind]
                if kind == "groq":
                    mod = (
                        self.model
                        if ("llama-4" in (self.model or "").lower() or "vision" in (self.model or "").lower())
                        else "meta-llama/llama-4-scout-17b-16e-instruct"
                    )
                else:
                    mod = self.model or default_mod
                messages = [
                    {"role": "system", "content": sys_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": question},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_png}"}},
                        ],
                    },
                ]
                reply, _ = self._call_openai_compatible(
                    url,
                    self.api_key,
                    mod,
                    messages,
                    enable_tools=False,
                    max_tokens=200,
                    timeout=12.0,
                )
                if reply:
                    return reply
            elif kind == "anthropic":
                payload = {
                    "model": self.model or "claude-3-5-haiku-latest",
                    "max_tokens": 200,
                    "system": sys_prompt,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {"type": "base64", "media_type": "image/png", "data": b64_png},
                                },
                                {"type": "text", "text": question},
                            ],
                        }
                    ],
                }
                try:
                    req = urllib.request.Request(
                        "https://api.anthropic.com/v1/messages",
                        data=json.dumps(payload).encode("utf-8"),
                        headers={
                            "Content-Type": "application/json",
                            "x-api-key": self.api_key,
                            "anthropic-version": "2023-06-01",
                        },
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=15.0) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        blocks = data.get("content") or []
                        if blocks and blocks[0].get("text"):
                            return blocks[0]["text"]
                except Exception:
                    pass

        if not self.gaming_active or not self.api_key:
            return self._call_ollama_vision(sys_prompt, question, b64_png)
        return None
