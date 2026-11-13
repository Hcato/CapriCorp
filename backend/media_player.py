"""
Módulo de Reproductor Multimedia y Mezclador de Audio de Windows para Capri
(Ingeniería inversa de `app/Player.cs` y `app/Mixer.cs` de `lachydotmcg/capri-desktop`).
"""

import ctypes
from ctypes import wintypes
import re
import time
import urllib.parse
import webbrowser
from typing import Any, Dict, List, Optional

# Códigos de teclas virtuales multimedia de Windows (Win32)
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002


def _press_vk(vk_code: int, times: int = 1) -> None:
    """Envía pulsaciones de tecla multimedia reales al sistema operativo."""
    try:
        user32 = ctypes.windll.user32
        for _ in range(max(1, times)):
            user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY, 0)
            user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
            if times > 1:
                time.sleep(0.02)
    except Exception:
        pass


def _press_chord(vk_codes: List[int]) -> None:
    """Presiona una combinación de teclas simultáneamente (como Alt+Shift+B para Like en Spotify)."""
    try:
        user32 = ctypes.windll.user32
        for vk in vk_codes:
            user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.04)
        for vk in reversed(vk_codes):
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    except Exception:
        pass


class WindowsMediaController:
    """
    Detecta qué canción o video está sonando en Windows (`Spotify`, `YouTube`, `Chrome`, `Edge`, `VLC`, etc.)
    y permite controlar la reproducción, el volumen y el estado de "Me gusta" desde el Mini Player de Capri.
    """

    BROWSER_SUFFIXES = re.compile(
        r"\s*[-—]\s*(?:Google Chrome|Microsoft\u200b? Edge|Mozilla Firefox|Brave|Opera(?: GX)?|Vivaldi).*$",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self._last_tune: Dict[str, Any] = {
            "title": "",
            "artist": "",
            "app": "",
            "playing": False,
            "liked": False,
            "position": 0.0,
            "length": 210.0,
        }
        self._track_key: str = ""
        self._track_started_at: float = time.time()
        self._paused_position: float = 0.0
        self._manual_override_until: float = 0.0
        self._manual_playing: Optional[bool] = None

    def _enumerate_windows(self) -> List[Dict[str, Any]]:
        """Enumera ventanas visibles con su título y nombre de ejecutable."""
        results: List[Dict[str, Any]] = []
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            def callback(hwnd: int, _lparam: int) -> bool:
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.strip()
                if not title:
                    return True

                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                exe_name = ""
                if pid.value:
                    h_proc = kernel32.OpenProcess(0x0410, False, pid.value)  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
                    if h_proc:
                        try:
                            exe_buf = ctypes.create_unicode_buffer(260)
                            if psapi.GetModuleBaseNameW(h_proc, None, exe_buf, 260) > 0:
                                exe_name = exe_buf.value.lower()
                        finally:
                            kernel32.CloseHandle(h_proc)

                results.append({"hwnd": hwnd, "title": title, "exe": exe_name})
                return True

            user32.EnumWindows(WNDENUMPROC(callback), 0)
        except Exception:
            pass
        return results

    def poll_current_tune(self) -> Dict[str, Any]:
        """
        Escanea las sesiones/ventanas multimedia activas (Spotify, YouTube, VLC, reproductores)
        y devuelve el diccionario de estado para el Cyberpunk Mini Player.
        """
        now = time.time()
        windows = self._enumerate_windows()

        detected_title = ""
        detected_artist = ""
        detected_app = ""
        detected_playing = False

        # 1. Buscar Spotify primero (Prioridad alta, igual que `ReadSpotify` en `Player.cs`)
        for w in windows:
            exe = w["exe"]
            title = w["title"]
            if "spotify" in exe:
                if title.lower() in ("spotify", "spotify free", "spotify premium"):
                    # Spotify está abierto pero en pausa
                    if self._last_tune["app"] == "Spotify" and self._last_tune["title"]:
                        detected_title = self._last_tune["title"]
                        detected_artist = self._last_tune["artist"]
                        detected_app = "Spotify"
                        detected_playing = False
                elif " - " in title:
                    parts = title.split(" - ", 1)
                    detected_artist = parts[0].strip()
                    detected_title = parts[1].strip()
                    detected_app = "Spotify"
                    detected_playing = True
                    break

        # 2. Buscar YouTube Music / YouTube / SoundCloud en navegadores si Spotify no está sonando
        if not detected_playing:
            for w in windows:
                exe = w["exe"]
                title = w["title"]
                if any(b in exe for b in ("chrome", "msedge", "firefox", "brave", "opera", "vivaldi")):
                    clean = self.BROWSER_SUFFIXES.sub("", title).strip()
                    # Quitar indicador de audio "(1) " o "▶ " al principio
                    clean = re.sub(r"^(?:\(\d+\)\s*|[\u25b6\u23f8]\s*)", "", clean)
                    if clean.endswith(" - YouTube Music"):
                        song_part = clean[: -len(" - YouTube Music")].strip()
                        if " - " in song_part:
                            a, t = song_part.split(" - ", 1)
                            detected_artist, detected_title = a.strip(), t.strip()
                        else:
                            detected_artist, detected_title = "YouTube Music", song_part
                        detected_app = "YouTube Music"
                        detected_playing = True
                        break
                    elif clean.endswith(" - YouTube") and clean != "YouTube":
                        video_part = clean[: -len(" - YouTube")].strip()
                        if " - " in video_part:
                            a, t = video_part.split(" - ", 1)
                            detected_artist, detected_title = a.strip(), t.strip()
                        else:
                            detected_artist, detected_title = "YouTube", video_part
                        detected_app = "YouTube"
                        detected_playing = True
                        break
                    elif "soundcloud" in clean.lower():
                        detected_artist = "SoundCloud"
                        detected_title = clean
                        detected_app = "SoundCloud"
                        detected_playing = True
                        break

        # 3. Buscar VLC / Media Player / foobar2000 / MusicBee
        if not detected_playing and not detected_title:
            for w in windows:
                exe = w["exe"]
                title = w["title"]
                if "vlc" in exe and "vlc media player" in title.lower():
                    raw = re.sub(r"\s*[-—]\s*VLC media player.*$", "", title, flags=re.IGNORECASE).strip()
                    if raw and raw.lower() != "vlc media player":
                        detected_title = raw
                        detected_artist = "VLC"
                        detected_app = "VLC"
                        detected_playing = True
                        break

        # Si el usuario acaba de pulsar Play/Pause manualmente desde el Mini Player, respetar durante 3.5s
        if now < self._manual_override_until and self._manual_playing is not None:
            if detected_title:
                detected_playing = self._manual_playing
            elif self._last_tune["title"]:
                detected_title = self._last_tune["title"]
                detected_artist = self._last_tune["artist"]
                detected_app = self._last_tune["app"]
                detected_playing = self._manual_playing

        if detected_title:
            new_key = f"{detected_app}:{detected_artist}:{detected_title}"
            if new_key != self._track_key:
                self._track_key = new_key
                self._track_started_at = now
                self._paused_position = 0.0
                self._last_tune["liked"] = False
                self._last_tune["length"] = 210.0

            if detected_playing:
                pos = (now - self._track_started_at) % max(30.0, self._last_tune["length"])
                self._paused_position = pos
            else:
                pos = self._paused_position

            self._last_tune.update(
                {
                    "title": detected_title,
                    "artist": detected_artist or detected_app,
                    "app": detected_app or "Player",
                    "playing": detected_playing,
                    "position": round(pos, 1),
                    "length": 210.0,
                }
            )
        else:
            self._last_tune["playing"] = False

        return dict(self._last_tune)

    def execute_command(self, cmd: str, arg: str = "") -> Dict[str, Any]:
        """
        Ejecuta un comando multimedia (`play`, `pause`, `toggle`, `next`, `previous`, `like`,
        `vol_up`, `vol_down`, `mute`, `seek`, `play_query`) y devuelve el nuevo estado.
        """
        action = cmd.strip().lower()
        now = time.time()

        if action in ("play", "pause", "toggle", "play_pause"):
            _press_vk(VK_MEDIA_PLAY_PAUSE)
            new_playing = not self._last_tune.get("playing", False)
            if action == "play":
                new_playing = True
            elif action == "pause":
                new_playing = False
            self._manual_playing = new_playing
            self._manual_override_until = now + 4.0
            if new_playing and not self._last_tune.get("title"):
                self._last_tune["title"] = "Night City Radio"
                self._last_tune["artist"] = "Cyberpunk Mix"
                self._last_tune["app"] = "System Audio"
            self._last_tune["playing"] = new_playing

        elif action in ("next", "skip"):
            _press_vk(VK_MEDIA_NEXT_TRACK)
            self._track_started_at = now
            self._paused_position = 0.0

        elif action in ("previous", "prev", "back"):
            _press_vk(VK_MEDIA_PREV_TRACK)
            self._track_started_at = now
            self._paused_position = 0.0

        elif action == "like":
            self._last_tune["liked"] = not self._last_tune.get("liked", False)
            # En Spotify, Alt+Shift+B guarda en Canciones que te gustan (`Player.cs`)
            if "spotify" in self._last_tune.get("app", "").lower():
                _press_chord([0x12, 0x10, 0x42])

        elif action == "seek":
            try:
                sec = float(arg)
                self._paused_position = max(0.0, min(sec, self._last_tune.get("length", 210.0)))
                self._track_started_at = now - self._paused_position
                self._last_tune["position"] = round(self._paused_position, 1)
            except ValueError:
                pass

        elif action == "vol_up":
            _press_vk(VK_VOLUME_UP, times=5)

        elif action == "vol_down":
            _press_vk(VK_VOLUME_DOWN, times=5)

        elif action == "mute":
            _press_vk(VK_VOLUME_MUTE, times=1)

        elif action == "play_query":
            q = (arg or "Cyberpunk Edgerunners Stay at Your House").strip()
            encoded = urllib.parse.quote_plus(q)
            webbrowser.open(f"https://www.youtube.com/results?search_query={encoded}")
            self._last_tune.update(
                {
                    "title": q,
                    "artist": "YouTube Mix",
                    "app": "YouTube",
                    "playing": True,
                    "position": 0.0,
                    "length": 210.0,
                }
            )
            self._track_started_at = now
            self._manual_playing = True
            self._manual_override_until = now + 8.0

        return self.poll_current_tune()

