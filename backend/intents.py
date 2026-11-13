"""
Clasificador rápido de intenciones bilingüe (Español + Inglés) sin consumo de VRAM.
Combina `Capri-cmd/capri-ai` con las herramientas de escritorio, música, ventanas,
recordatorios y videojuegos de `lachydotmcg/capri-desktop`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Intent:
    kind: str
    arg: str = ""


_RE_MINI = re.compile(
    r"\b(?:modo mini|ponte (?:mini|pequeña|chiquita)|hazte (?:mini|pequeña|chiquita)|go mini|mini mode|shrink)\b",
    re.I,
)
_RE_FULL = re.compile(
    r"\b(?:tamaño (?:normal|completo|grande)|hazte grande|vuelve a (?:normal|grande)|full size|normal size)\b",
    re.I,
)
_RE_LAY = re.compile(
    r"\b(?:acuéstate|túmbate|échate|recuéstate|lie down|lay down)\b",
    re.I,
)
_RE_PERCH_WIN = re.compile(
    r"\b(?:siéntate en (?:mi |la )?ventana|sube a (?:mi |la )?ventana|salta a (?:mi |la )?ventana|sit on (?:my |the )?window|perch on window)\b",
    re.I,
)
_RE_SIT = re.compile(
    r"\b(?:siéntate|sentada|sit down|perch)\b",
    re.I,
)
_RE_STAND = re.compile(
    r"\b(?:levántate|ponte de pie|párate|stand up)\b",
    re.I,
)
_RE_DANCE = re.compile(
    r"\b(?:baila|ponte a bailar|dance for me|start dancing|baila conmigo)\b",
    re.I,
)
_RE_TELEPORT = re.compile(
    r"\b(?:teletranspórtate|teletransporte|salta|zap|teleport)\b",
    re.I,
)
_RE_SLEEP = re.compile(
    r"\b(?:vete a dormir|duérmete|a dormir|descansa|go to sleep|take a nap)\b",
    re.I,
)
_RE_SKIN = re.compile(
    r"\b(?:skin|aspecto|modo visual)\s+(?P<skin>watcher|shader|sprites|capri|oficial)\b",
    re.I,
)
_RE_TIME = re.compile(
    r"\b(?:qué hora es|dime la hora|hora actual|qué día es hoy|qué fecha es hoy|what time is it|what day is it)\b",
    re.I,
)
_RE_SCREEN = re.compile(
    r"\b(?:qué ves|mira mi pantalla|qué hay en mi pantalla|qué estoy haciendo|what do you see|look at my screen)\b",
    re.I,
)

# ── Controles de Música y Volumen (`Player.cs` / `Mixer.cs`) ─────────
_RE_WHATS_PLAYING = re.compile(
    r"\b(?:qué (?:está sonando|canción es|música suena)|what(?:'s| is) playing|what song is this)\b",
    re.I,
)
_RE_MEDIA_PAUSE = re.compile(
    r"^(?:pausa(?: la música| la canción)?|detén la música|para la música|pause(?: music)?)$",
    re.I,
)
_RE_MEDIA_RESUME = re.compile(
    r"^(?:continúa(?: la música)?|reanuda(?: la música)?|dale play|resume(?: music)?)$",
    re.I,
)
_RE_MEDIA_NEXT = re.compile(
    r"\b(?:siguiente(?: canción| tema)?|salta(?: la canción| esta canción)?|cambia de canción|next (?:song|track)|skip(?: song)?)\b",
    re.I,
)
_RE_MEDIA_PREV = re.compile(
    r"\b(?:canción anterior|anterior canción|tema anterior|previous (?:song|track)|go back a song)\b",
    re.I,
)
_RE_VOL_UP = re.compile(
    r"\b(?:sube el volumen|más volumen|volumen arriba|turn up (?:the )?volume|louder)\b",
    re.I,
)
_RE_VOL_DOWN = re.compile(
    r"\b(?:baja el volumen|menos volumen|volumen abajo|turn down (?:the )?volume|quieter)\b",
    re.I,
)
_RE_LIKE_SONG = re.compile(
    r"\b(?:me gusta esta canción|guarda esta canción|dale like a la canción|like this song)\b",
    re.I,
)

# ── Videojuegos: Piloto Automático, GameSense y Minijuegos (`Play.cs`, `GameSense.cs`, `Minis.cs`) ──
_RE_MINIGAME = re.compile(
    r"\b(?:juguemos|jugar|abre|vamos a jugar)(?: al| a la| a)?\s+(?P<game>tres en raya|gato|tic[\s-]?tac[\s-]?toe|conecta\s*4|connect\s*(?:four|4)|piedra[,\s]*papel\s*(?:o|y)\s*tijera(?:s)?|rock[,\s]*paper[,\s]*scissors)\b",
    re.I,
)
_RE_STOP_GAME = re.compile(
    r"\b(?:deja de jugar|suelta el mando|suelta los controles|para de jugar|stop playing)\b",
    re.I,
)
_RE_PLAY_FOR_ME = re.compile(
    r"\b(?:juega por mí|toma el (?:control|mando)(?: del juego)?|camina en el juego|explora en el juego|modo combate en el juego|baila en el juego|play for me|take the controls)\b",
    re.I,
)
_RE_GAMESENSE = re.compile(
    r"\b(?:vigila mi (?:partida|juego)|mira cómo juego|comenta mi partida|activa gamesense|watch me play|watch my game)\b",
    re.I,
)

# ── Temporizadores y Recordatorios (`Reminders.cs`) ─────────────────
_RE_LIST_REMINDERS = re.compile(
    r"\b(?:qué recordatorios tengo|mis recordatorios|lista mis recordatorios|what reminders do i have|list my reminders)\b",
    re.I,
)
_RE_TIMER = re.compile(
    r"\b(?:pon(?:me)? un )?(?:temporizador|timer|alarma)\s+(?:de\s+|por\s+|for\s+)?(?P<num>\d+)\s*(?P<unit>segundos?|segs?|s|minutos?|mins?|m|horas?|hrs?|h)(?:\s+para\s+(?P<note>.+))?$",
    re.I,
)
_RE_REMIND_IN = re.compile(
    r"\b(?:recuérdame|avísame|remind me)\s+en\s+(?P<num>\d+)\s*(?P<unit>segundos?|segs?|s|minutos?|mins?|m|horas?|hrs?|h)\s+(?:que\s+|de\s+|to\s+)?(?P<note>.+)$",
    re.I,
)

# ── Control de Ventanas (`Hands.cs`) ────────────────────────────────
_RE_WIN_CTRL = re.compile(
    r"^(?:por favor\s+)?(?P<act>cierra|minimiza|enfoca|cambia a|trae al frente|close|minimize|switch to)\s+(?:la ventana\s+|el\s+|la\s+)?(?P<target>.+?)[\s.!?]*$",
    re.I,
)

# ── Memoria, Música, Búsqueda y Apps ────────────────────────────────
_RE_REMEMBER = re.compile(
    r"\b(?:recuerda que|no olvides que|anota que|guarda en tu memoria que|remember that)\s+(?P<fact>.+)$",
    re.I,
)
_RE_RECALL = re.compile(
    r"\b(?:qué recuerdas de mí|qué sabes de mí|qué tienes en tu memoria|what do you remember about me)\b",
    re.I,
)
_RE_PLAY = re.compile(
    r"\b(?:pon(?:me)?|reproduce|toca|play|put on)\s+(?:la canción\s+|música\s+|algo de\s+)?(?P<song>.+?)(?:\s+en\s+(?P<where>youtube|spotify))?[\s.!?]*$",
    re.I,
)
_RE_OPEN = re.compile(
    r"^(?:(?:oye|hey|hola)?[,\s]*(?:capri)?[,\s]*)?(?:por favor\s+)?(?:abre|ábreme|inicia|ejecuta|lanza|open|launch|start)\s+(?:el\s+|la\s+|mi\s+)?(?P<app>.+?)[\s.!?]*$",
    re.I,
)
_RE_SEARCH = re.compile(
    r"\b(?:busca(?: en google| en internet| en la web)?|googlea|investiga sobre|search(?: for| the web for)?|google)\s+(?P<q>.{2,}?)[\s.!?]*$",
    re.I,
)


def _to_seconds(num_str: str, unit_str: str) -> float:
    val = float(num_str)
    u = unit_str.lower()
    if u.startswith("h"):
        return val * 3600.0
    if u.startswith("m"):
        return val * 60.0
    return val


def detect_intent(text: str) -> Intent | None:
    """Detecta si el mensaje del usuario corresponde a una acción directa en el escritorio o en la UI."""
    clean = (text or "").strip()
    if not clean:
        return None

    # 1. Minijuegos de escritorio (`Minis.cs`)
    m_mg = _RE_MINIGAME.search(clean)
    if m_mg:
        g = m_mg.group("game").lower()
        if "conecta" in g or "connect" in g:
            return Intent("minigame", "connect_four")
        if "piedra" in g or "rock" in g:
            return Intent("minigame", "rock_paper_scissors")
        return Intent("minigame", "tic_tac_toe")

    # 2. Piloto automático y GameSense (`Play.cs`, `GameSense.cs`)
    if _RE_STOP_GAME.search(clean):
        return Intent("game_autopilot", "stop")
    if _RE_PLAY_FOR_ME.search(clean):
        low = clean.lower()
        if "baila" in low:
            return Intent("game_autopilot", "dance")
        if "combate" in low:
            return Intent("game_autopilot", "combat")
        return Intent("game_autopilot", "explore")
    if _RE_GAMESENSE.search(clean):
        return Intent("gamesense", "toggle")

    # 3. Temporizadores y Recordatorios (`Reminders.cs`)
    if _RE_LIST_REMINDERS.search(clean):
        return Intent("reminders_list")
    m_timer = _RE_TIMER.search(clean)
    if m_timer:
        secs = _to_seconds(m_timer.group("num"), m_timer.group("unit"))
        note = (m_timer.group("note") or f"Temporizador de {m_timer.group('num')} {m_timer.group('unit')}").strip()
        return Intent("timer_set", f"{secs}|{note}")
    m_remin = _RE_REMIND_IN.search(clean)
    if m_remin:
        secs = _to_seconds(m_remin.group("num"), m_remin.group("unit"))
        note = m_remin.group("note").strip(" .!")
        return Intent("timer_set", f"{secs}|{note}")

    # 4. Controles Multimedia (`Player.cs`)
    if _RE_WHATS_PLAYING.search(clean):
        return Intent("media_cmd", "whats_playing")
    if _RE_MEDIA_PAUSE.search(clean):
        return Intent("media_cmd", "pause")
    if _RE_MEDIA_RESUME.search(clean):
        return Intent("media_cmd", "play")
    if _RE_MEDIA_NEXT.search(clean):
        return Intent("media_cmd", "next")
    if _RE_MEDIA_PREV.search(clean):
        return Intent("media_cmd", "previous")
    if _RE_VOL_UP.search(clean):
        return Intent("media_cmd", "vol_up")
    if _RE_VOL_DOWN.search(clean):
        return Intent("media_cmd", "vol_down")
    if _RE_LIKE_SONG.search(clean):
        return Intent("media_cmd", "like")

    # 5. Posturas, Mini, Skins y Baile
    if _RE_MINI.search(clean):
        return Intent("mini", "true")
    if _RE_FULL.search(clean):
        return Intent("full", "false")
    if _RE_PERCH_WIN.search(clean):
        return Intent("perch_window")
    if _RE_LAY.search(clean):
        return Intent("lay")
    if _RE_SIT.search(clean):
        return Intent("sit")
    if _RE_STAND.search(clean):
        return Intent("stand")
    if _RE_DANCE.search(clean):
        return Intent("dance")
    if _RE_TELEPORT.search(clean):
        return Intent("teleport")
    if _RE_SLEEP.search(clean):
        return Intent("sleep")

    m_skin = _RE_SKIN.search(clean)
    if m_skin:
        raw_skin = m_skin.group("skin").lower()
        if raw_skin == "watcher":
            return Intent("skin", "watcher")
        if raw_skin in ("sprites", "capri", "oficial"):
            return Intent("skin", "capri")
        return Intent("skin", "shader")

    # 6. Hora, Pantalla, Memoria
    if _RE_TIME.search(clean):
        return Intent("time")
    if _RE_SCREEN.search(clean):
        return Intent("screen")
    if _RE_RECALL.search(clean):
        return Intent("recall")

    m_rem = _RE_REMEMBER.search(clean)
    if m_rem and not clean.endswith("?"):
        return Intent("remember", m_rem.group("fact").strip(" .!"))

    # 7. Control de ventanas (`Hands.cs`)
    m_win = _RE_WIN_CTRL.search(clean)
    if m_win:
        act_raw = m_win.group("act").lower()
        target = m_win.group("target").strip()
        if act_raw in ("cierra", "close"):
            return Intent("window_ctrl", f"close|{target}")
        if act_raw in ("minimiza", "minimize"):
            return Intent("window_ctrl", f"minimize|{target}")
        return Intent("window_ctrl", f"focus|{target}")

    # 8. Búsqueda web, Reproducir canción, Abrir Apps
    m_search = _RE_SEARCH.search(clean)
    if m_search:
        return Intent("search_web", m_search.group("q").strip())

    m_play = _RE_PLAY.search(clean)
    if m_play:
        song = m_play.group("song").strip()
        where = (m_play.group("where") or "youtube").lower()
        return Intent("play_music", f"{where}|{song}")

    m_open = _RE_OPEN.search(clean)
    if m_open:
        return Intent("open_app", m_open.group("app").strip())

    return None
