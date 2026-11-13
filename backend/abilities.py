"""
Habilidades de escritorio de Capri (Memoria persistente, Ojos de ventana activa sin VRAM,
Lanzador de apps/web, Música de Night City y Reloj).
Adaptado de Capri-cmd/capri-ai (capri/abilities/).
"""

from __future__ import annotations

import ctypes
import datetime
import json
import os
import random
import subprocess
import urllib.parse
import webbrowser
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
MEMORY_FILE = DATA_DIR / "memory.json"

# Favoritas de Night City (Edgerunners & Cyberpunk 2077)
NIGHT_CITY_TRACKS = [
    "Rosa Walton - I Really Want to Stay at Your House",
    "Franz Ferdinand - This Fffire",
    "Dawid Podsiadlo - Let You Down",
    "SAMURAI - Never Fade Away",
    "SAMURAI - Chippin' In",
    "HEALTH - Major Crimes",
    "Rezodrone - Resist and Disorder",
]

# Palabras clave de ventanas sensibles que Capri nunca lee por privacidad
_PRIVACY_BLOCKLIST = (
    "password",
    "contraseña",
    "bitwarden",
    "1password",
    "keepass",
    "bank",
    "banco",
    "paypal",
    "inprivate",
    "incógnito",
    "incognito",
)

# Mapa rápido de aplicaciones comunes en Windows
_WINDOWS_APPS = {
    "calculadora": "calc.exe",
    "calculator": "calc.exe",
    "bloc de notas": "notepad.exe",
    "notepad": "notepad.exe",
    "explorador": "explorer.exe",
    "archivos": "explorer.exe",
    "cmd": "cmd.exe",
    "terminal": "wt.exe",
    "powershell": "powershell.exe",
    "paint": "mspaint.exe",
    "administrador de tareas": "taskmgr.exe",
    "spotify": "spotify:",
    "discord": "discord://",
    "steam": "steam://open/main",
}


class CapriMemory:
    """Memoria ligera en JSON para recordar datos sobre el usuario e historial reciente."""

    def __init__(self, path: Path = MEMORY_FILE):
        self.path = path
        self.facts: list[str] = []
        self.history: list[dict[str, str]] = []
        self._load()

    def _load(self) -> None:
        try:
            if self.path.is_file():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.facts = list(data.get("facts") or [])
                self.history = list(data.get("history") or [])[-20:]
        except Exception:
            self.facts = []
            self.history = []

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "facts": self.facts[-50:],
                "history": self.history[-20:],
            }
            self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def add_fact(self, fact: str) -> None:
        clean = fact.strip()
        if clean and clean not in self.facts:
            self.facts.append(clean)
            self.save()

    def add_turn(self, user_text: str, assistant_text: str) -> None:
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": assistant_text})
        self.history = self.history[-20:]
        self.save()


def get_active_window_title() -> str:
    """Obtiene el título de la ventana en primer plano en Windows usando ctypes (0 VRAM)."""
    if os.name != "nt":
        return ""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        lower = title.lower()
        if any(bad in lower for bad in _PRIVACY_BLOCKLIST):
            return "(Ventana privada protegida por el filtro de seguridad de Capri)"
        return title
    except Exception:
        return ""


def current_time_string() -> str:
    now = datetime.datetime.now()
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    dia_sem = dias[now.weekday()]
    return f"Son las {now.strftime('%H:%M')} del {dia_sem} {now.strftime('%d/%m/%Y')}"


def open_application_or_site(target: str) -> tuple[bool, str]:
    """Abre una aplicación local de Windows o un sitio web conocido."""
    key = target.strip().lower()
    if key in ("youtube", "yt"):
        webbrowser.open("https://www.youtube.com")
        return True, "YouTube abierto en tu navegador"
    if key in ("github",):
        webbrowser.open("https://github.com")
        return True, "GitHub abierto en tu navegador"
    if key in ("google", "navegador", "browser"):
        webbrowser.open("https://www.google.com")
        return True, "Navegador abierto"

    cmd = _WINDOWS_APPS.get(key)
    if cmd:
        try:
            if cmd.endswith(":") or "://" in cmd:
                os.startfile(cmd)  # type: ignore[attr-defined]
            else:
                subprocess.Popen([cmd])
            return True, f"Aplicación '{target}' iniciada"
        except Exception as e:
            return False, f"No pude iniciar '{target}': {e}"

    # Si no está en el mapa directo, buscar en la web
    q = urllib.parse.quote_plus(target)
    webbrowser.open(f"https://www.google.com/search?q={q}")
    return True, f"Búsqueda abierta para '{target}'"


def play_music_track(arg: str) -> str:
    """Reproduce una canción en YouTube o Spotify (o elige una favorita de Night City)."""
    parts = arg.split("|", 1)
    where = parts[0] if len(parts) == 2 else "youtube"
    query = parts[1].strip() if len(parts) == 2 else arg.strip()

    if query.lower() in ("música", "musica", "algo", "algo bueno", "music", "something", "tu favorita"):
        query = random.choice(NIGHT_CITY_TRACKS)

    encoded = urllib.parse.quote_plus(query)
    if where == "spotify":
        webbrowser.open(f"https://open.spotify.com/search/{encoded}")
        return f"Buscando '{query}' en Spotify"
    else:
        webbrowser.open(f"https://www.youtube.com/results?search_query={encoded}")
        return f"Reproduciendo '{query}' en YouTube"


def search_on_web(query: str) -> str:
    encoded = urllib.parse.quote_plus(query.strip())
    webbrowser.open(f"https://www.google.com/search?q={encoded}")
    return f"Búsqueda en Google abierta para '{query}'"

