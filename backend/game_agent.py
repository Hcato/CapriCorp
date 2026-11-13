"""
Agente de Videojuegos para Capri: GameKeys, GameSense (Visión GDI 240x135) y Piloto Automático (SendInput/ScanCodes)
(Ingeniería inversa de `app/Play.cs`, `app/GameKeys.cs` y `app/GameSense.cs` de `lachydotmcg/capri-desktop`).
"""

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import random
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional

# Constantes Win32 para SendInput y Teclado de Hardware (DirectInput / RawInput para juegos)
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_LSHIFT = 0xA0
VK_LCONTROL = 0xA2

KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010

VK_MAP: Dict[str, int] = {
    "w": 0x57,
    "a": 0x41,
    "s": 0x53,
    "d": 0x44,
    "e": 0x45,
    "f": 0x46,
    "q": 0x51,
    "r": 0x52,
    "c": 0x43,
    "v": 0x56,
    "x": 0x58,
    "z": 0x5A,
    "1": 0x31,
    "2": 0x32,
    "3": 0x33,
    "4": 0x34,
    "5": 0x35,
    "6": 0x36,
    "7": 0x37,
    "8": 0x38,
    "9": 0x39,
    "space": VK_SPACE,
    "shift": VK_LSHIFT,
    "ctrl": VK_LCONTROL,
}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", INPUT_UNION)]


class BITMAPINFOHEADER(ctypes.Structure):
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


def is_esc_pressed() -> bool:
    """Interruptor de emergencia (`Play.cs`): si el usuario toca ESC, Capri suelta todos los controles al instante."""
    try:
        return bool(ctypes.windll.user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000)
    except Exception:
        return False


def _key_down(vk: int) -> None:
    try:
        user32 = ctypes.windll.user32
        scan = user32.MapVirtualKeyW(vk, 0)
        user32.keybd_event(vk, scan, KEYEVENTF_SCANCODE, 0)
    except Exception:
        pass


def _key_up(vk: int) -> None:
    try:
        user32 = ctypes.windll.user32
        scan = user32.MapVirtualKeyW(vk, 0)
        user32.keybd_event(vk, scan, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0)
    except Exception:
        pass


def _mouse_nudge(dx: int, dy: int, flags: int = MOUSEEVENTF_MOVE) -> None:
    """Mueve la cámara del juego mediante `SendInput` (`Play.cs` `Nudge`)."""
    try:
        inp = INPUT()
        inp.type = 0  # INPUT_MOUSE
        inp.u.mi.dx = int(dx)
        inp.u.mi.dy = int(dy)
        inp.u.mi.mouseData = 0
        inp.u.mi.dwFlags = flags
        inp.u.mi.time = 0
        inp.u.mi.dwExtraInfo = None
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    except Exception:
        pass


class GameKeysReader:
    """
    Lee los controles reales configurados en archivos de juegos (`app/GameKeys.cs`),
    como Minecraft (`options.txt`) y Cyberpunk 2077 (`UserSettings.json`).
    """

    @staticmethod
    def read_summary(game_name: str = "") -> str:
        roaming = os.environ.get("APPDATA", "")
        local = os.environ.get("LOCALAPPDATA", "")
        low = game_name.lower()

        if "minecraft" in low or not low:
            mc_path = Path(roaming) / ".minecraft" / "options.txt"
            if mc_path.exists():
                try:
                    binds: List[str] = []
                    for line in mc_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                        m = re.match(r"^key_key\.([^:]+):(.+)$", line)
                        if m and m.group(1) in ("forward", "left", "back", "right", "jump", "sneak", "sprint", "attack", "use", "inventory", "drop"):
                            key_clean = m.group(2).replace("key.keyboard.", "").replace("key.mouse.", "mouse ")
                            binds.append(f"{m.group(1)}={key_clean}")
                    if binds:
                        return "Controles de Minecraft detectados: " + ", ".join(binds)
                except Exception:
                    pass

        if "cyberpunk" in low or not low:
            cp_path = Path(local) / "CD Projekt Red" / "Cyberpunk 2077" / "UserSettings.json"
            if cp_path.exists():
                try:
                    data = json.loads(cp_path.read_text(encoding="utf-8", errors="ignore"))
                    return f"Configuración de Cyberpunk 2077 detectada ({len(data)} grupos en UserSettings.json)."
                except Exception:
                    pass

        return "Controles estándar de PC (WASD = moverse, Espacio = saltar, Shift = correr, Ratón = cámara/ataque)."


class GameSenseWatcher:
    """
    Port de `app/GameSense.cs`: muestrea la pantalla en baja resolución (240x135) usando GDI nativo (0 VRAM)
    para detectar daño en los bordes (`hurt`), destellos/explosiones (`flash`) y pantalla oscura/muerte (`dark`).
    """

    HURT_LINES = [
        "¡Cuidado, choom! Te están dejando el cromo hecho trizas, cúrate ya.",
        "¡Auch! Vi esos bordes rojos... cubre posición o usa un inhalador.",
        "¡Te están dando duro, choom! Muévete, no te quedes quieto.",
        "¡Nivel de salud crítico detectado! Esquiva eso.",
    ]
    FLASH_LINES = [
        "¡Mis ópticas Kiroshi! ¿Qué fue esa explosión, choom?",
        "¡Flashazo directo! Casi me reinicias el shader.",
        "¡Boom! Eso sí que iluminó toda la pantalla.",
    ]
    DARK_LINES = [
        "Todo se puso oscuro... ¿acaso nos flatlinearon o es pantalla de carga?",
        "Pantalla negra. Si moriste, yo no vi nada, choom.",
    ]

    def __init__(self) -> None:
        self.enabled: bool = False
        self._last_mean: Optional[float] = None
        self._baseline_red: float = 12.0
        self._last_event_at: float = 0.0

    def sample_screen_event(self) -> Optional[str]:
        """Toma una muestra rápida de 120x68 píxeles por GDI y devuelve un comentario si detecta acción."""
        if not self.enabled:
            return None
        now = time.time()
        if now - self._last_event_at < 8.0:
            return None

        try:
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32

            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            w, h = 120, 68

            hdc_screen = user32.GetDC(0)
            if not hdc_screen:
                return None
            hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
            hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
            old_obj = gdi32.SelectObject(hdc_mem, hbmp)

            # StretchBlt copia y reduce en una sola llamada de hardware
            gdi32.StretchBlt(hdc_mem, 0, 0, w, h, hdc_screen, 0, 0, sw, sh, 0x00CC0020)  # SRCCOPY

            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = w
            bmi.biHeight = -h  # Top-down
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = 0

            buf = ctypes.create_string_buffer(w * h * 4)
            gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, ctypes.byref(bmi), 0)

            gdi32.SelectObject(hdc_mem, old_obj)
            gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(0, hdc_screen)

            raw = buf.raw
            total_luma = 0.0
            dark_count = 0
            edge_red_excess = 0.0
            edge_samples = 0
            total_px = w * h

            for y in range(0, h, 2):
                is_edge_y = y < 8 or y >= h - 8
                for x in range(0, w, 2):
                    idx = (y * w + x) * 4
                    b = raw[idx]
                    g = raw[idx + 1]
                    r = raw[idx + 2]
                    luma = (b * 29 + g * 150 + r * 77) >> 8
                    total_luma += luma
                    if luma < 16:
                        dark_count += 1
                    if is_edge_y or x < 12 or x >= w - 12:
                        edge_red_excess += max(0, r - max(g, b))
                        edge_samples += 1

            sampled_px = max(1, total_px // 4)
            mean_luma = total_luma / sampled_px
            dark_ratio = dark_count / sampled_px
            mean_edge_red = edge_red_excess / max(1, edge_samples)

            event_line: Optional[str] = None
            if self._last_mean is not None:
                # 1. Detectar Flashbang / Explosión (`GameSense.cs` flash)
                if mean_luma - self._last_mean > 58.0 and mean_luma > 175.0:
                    event_line = random.choice(self.FLASH_LINES)
                # 2. Detectar Bordes Rojos de Daño (`GameSense.cs` hurt)
                elif mean_edge_red > self._baseline_red + 26.0:
                    event_line = random.choice(self.HURT_LINES)
                # 3. Detectar Pantalla Negra repentina (`GameSense.cs` dark)
                elif dark_ratio > 0.94 and self._last_mean > 35.0:
                    event_line = random.choice(self.DARK_LINES)

            self._last_mean = mean_luma
            self._baseline_red = self._baseline_red * 0.85 + mean_edge_red * 0.15

            if event_line:
                self._last_event_at = now
                return event_line
        except Exception:
            pass
        return None


class GameAutopilot:
    """
    Port de `app/Play.cs`: permite que Capri tome el control del teclado y ratón en un videojuego
    (`walk`, `look`, `jump`, `attack`, `explore`, `patrol`, `dance`) con parada inmediata al pulsar `ESC`.
    """

    KNOWN_GAMES_REGEX = re.compile(
        r"minecraft|cyberpunk|roblox|valorant|fortnite|genshin|elden ring|counter-strike|cs2|overwatch|apex|gta|terraria|stardew|helldivers|baldur|doom|halo|league of legends|dota",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self.is_playing: bool = False
        self._stop_flag: bool = False
        self._thread: Optional[threading.Thread] = None
        self.keys_reader = GameKeysReader()
        self.sense = GameSenseWatcher()

    def stop(self) -> str:
        self._stop_flag = True
        self.is_playing = False
        for vk in (VK_MAP["w"], VK_MAP["a"], VK_MAP["s"], VK_MAP["d"], VK_SPACE, VK_LSHIFT, VK_LCONTROL):
            _key_up(vk)
        _mouse_nudge(0, 0, MOUSEEVENTF_LEFTUP)
        _mouse_nudge(0, 0, MOUSEEVENTF_RIGHTUP)
        return "Solté el mando y los controles del juego, choom."

    def focus_game_window(self) -> str:
        """
        Busca entre las ventanas visibles una que coincida con `KNOWN_GAMES_REGEX` (ej. Minecraft)
        y le da foco con `SetForegroundWindow` antes de enviar inputs. Retorna el título de la ventana.
        """
        try:
            user32 = ctypes.windll.user32
            matched_hwnd = 0
            matched_title = ""

            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            def _enum_cb(hwnd: int, _lparam: int) -> bool:
                nonlocal matched_hwnd, matched_title
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.strip()
                if title and self.KNOWN_GAMES_REGEX.search(title):
                    matched_hwnd = hwnd
                    matched_title = title
                    return False
                return True

            user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)
            if matched_hwnd:
                if user32.IsIconic(matched_hwnd):
                    user32.ShowWindow(matched_hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(matched_hwnd)
                return matched_title
        except Exception:
            pass
        return ""

    @staticmethod
    def steer_cursor() -> None:
        """Sacude ligeramente el cursor (`2, -2, 1, -1`) como en `Play.cs` `Steer()` para juegos como Cyberpunk o Roblox."""
        for counts in (2, -2, 1, -1):
            if is_esc_pressed():
                return
            _mouse_nudge(counts, 0)
            time.sleep(0.025)

    @staticmethod
    def turn_camera(dx: int, dy: int) -> None:
        """Gira suavemente la cámara del juego en pasos de 4 ms (`Play.cs` `Turn`)."""
        longest = max(abs(dx), abs(dy))
        steps = max(1, int((longest + 47) // 48))
        sent_x, sent_y = 0, 0
        for i in range(1, steps + 1):
            if is_esc_pressed():
                return
            want_x = round(dx * i / steps)
            want_y = round(dy * i / steps)
            _mouse_nudge(want_x - sent_x, want_y - sent_y)
            sent_x, sent_y = want_x, want_y
            time.sleep(0.005)

    def turn(self, dx: int, dy: int) -> None:
        """Gira la mira suavemente con `turn_camera`, deteniéndose al instante si se pulsa ESC."""
        if self._stop_flag or is_esc_pressed():
            self._stop_flag = True
            return
        self.turn_camera(int(max(-360, min(dx, 360))), int(max(-160, min(dy, 160))))

    def walk(
        self,
        dir: Any = "w",
        sec: float = 1.0,
        jump: bool = False,
        sprint: bool = False,
        auto_jump: Optional[bool] = None,
    ) -> None:
        """
        Mueve al personaje con W/A/S/D durante `sec` segundos, saltando (`Space`) y corriendo (`Ctrl`),
        con parada inmediata si `is_esc_pressed()`.
        """
        if auto_jump is not None:
            jump = auto_jump
        if isinstance(dir, str):
            raw_keys = [ch for ch in dir.lower() if ch in ("w", "a", "s", "d")]
        elif isinstance(dir, (list, tuple)):
            raw_keys = [str(k).lower() for k in dir]
        else:
            raw_keys = ["w"]

        vks = [VK_MAP[k] for k in raw_keys if k in VK_MAP]
        if not vks:
            vks = [VK_MAP["w"]]
        if sprint and VK_LCONTROL not in vks:
            vks.append(VK_LCONTROL)

        for vk in vks:
            _key_down(vk)
        try:
            end_at = time.time() + max(0.15, min(float(sec), 8.0))
            next_jump = time.time() + (0.25 if jump else 999.0)
            while time.time() < end_at:
                if self._stop_flag or is_esc_pressed():
                    self._stop_flag = True
                    break
                if jump and time.time() >= next_jump:
                    _key_down(VK_SPACE)
                    time.sleep(0.06)
                    _key_up(VK_SPACE)
                    next_jump = time.time() + 1.15
                time.sleep(0.04)
        finally:
            for vk in vks:
                _key_up(vk)

    def hold_attack(self, sec: float = 1.2) -> None:
        """
        Mantiene el clic izquierdo pulsado (`MOUSEEVENTF_LEFTDOWN`) durante `sec` segundos
        y luego lo suelta (`MOUSEEVENTF_LEFTUP`) para talar árboles o picar bloques en Minecraft.
        """
        if self._stop_flag or is_esc_pressed():
            self._stop_flag = True
            return
        _mouse_nudge(0, 0, MOUSEEVENTF_LEFTDOWN)
        try:
            end_at = time.time() + max(0.15, min(float(sec), 5.0))
            while time.time() < end_at:
                if self._stop_flag or is_esc_pressed():
                    self._stop_flag = True
                    break
                time.sleep(0.04)
        finally:
            _mouse_nudge(0, 0, MOUSEEVENTF_LEFTUP)

    def tap_attack(self, clicks: int = 3) -> None:
        """Clics izquierdos rápidos para golpear o combatir en Minecraft/juegos."""
        n = max(1, min(int(clicks), 8))
        for _ in range(n):
            if self._stop_flag or is_esc_pressed():
                self._stop_flag = True
                break
            _mouse_nudge(0, 0, MOUSEEVENTF_LEFTDOWN)
            time.sleep(0.045)
            _mouse_nudge(0, 0, MOUSEEVENTF_LEFTUP)
            time.sleep(0.08)

    def use_item(self, sec: float = 0.25) -> None:
        """Clic derecho (`MOUSEEVENTF_RIGHTDOWN`/`UP`) para colocar bloques, comer o interactuar."""
        if self._stop_flag or is_esc_pressed():
            self._stop_flag = True
            return
        _mouse_nudge(0, 0, MOUSEEVENTF_RIGHTDOWN)
        try:
            end_at = time.time() + max(0.08, min(float(sec), 3.0))
            while time.time() < end_at:
                if self._stop_flag or is_esc_pressed():
                    self._stop_flag = True
                    break
                time.sleep(0.04)
        finally:
            _mouse_nudge(0, 0, MOUSEEVENTF_RIGHTUP)

    def select_slot(self, slot_num: int) -> None:
        """Pulsa la tecla `1`..`9` de la barra rápida (hotbar)."""
        if self._stop_flag or is_esc_pressed():
            self._stop_flag = True
            return
        key = str(max(1, min(int(slot_num), 9)))
        vk = VK_MAP.get(key)
        if vk:
            _key_down(vk)
            time.sleep(0.04)
            _key_up(vk)

    def sneak(self, sec: float = 0.8) -> None:
        """Mantiene `Shift` pulsado durante `sec` segundos para agacharse."""
        if self._stop_flag or is_esc_pressed():
            self._stop_flag = True
            return
        _key_down(VK_LSHIFT)
        try:
            end_at = time.time() + max(0.1, min(float(sec), 4.0))
            while time.time() < end_at:
                if self._stop_flag or is_esc_pressed():
                    self._stop_flag = True
                    break
                time.sleep(0.04)
        finally:
            _key_up(VK_LSHIFT)

    def _execute_plan_actions(self, actions: List[Dict[str, Any]]) -> None:
        """Ejecuta secuencialmente las micro-acciones devueltas por `brain.plan_game_action` con freno inmediato en ESC."""
        for act in actions:
            if self._stop_flag or is_esc_pressed():
                self._stop_flag = True
                break
            if not isinstance(act, dict):
                continue
            do = str(act.get("do") or "").strip().lower()
            if do == "turn":
                self.turn(int(act.get("dx") or 0), int(act.get("dy") or 0))
            elif do == "walk":
                self.walk(
                    dir=str(act.get("dir") or "w"),
                    sec=float(act.get("sec") or 1.0),
                    jump=bool(act.get("jump", False)),
                    sprint=bool(act.get("sprint", False)),
                )
            elif do == "hold_attack":
                self.hold_attack(sec=float(act.get("sec") or 1.2))
            elif do == "tap_attack":
                self.tap_attack(clicks=int(act.get("clicks") or 3))
            elif do in ("use", "use_item"):
                self.use_item(sec=float(act.get("sec") or 0.25))
            elif do == "jump":
                _key_down(VK_SPACE)
                time.sleep(0.07)
                _key_up(VK_SPACE)
            elif do == "sneak":
                self.sneak(sec=float(act.get("sec") or 0.7))
            elif do == "slot":
                self.select_slot(slot_num=int(act.get("slot") or 1))
            elif do == "unpause":
                # Clic central suave para reanudar o cerrar cursor si el juego está en pausa
                self.tap_attack(clicks=1)

    def _run_physical_fallback_step(self, mode: str) -> None:
        """Rutina física de respaldo cuando no hay visión disponible."""
        if mode == "dance":
            for _ in range(6):
                if self._stop_flag or is_esc_pressed():
                    break
                _key_down(VK_LSHIFT)
                time.sleep(0.08)
                _key_up(VK_LSHIFT)
                time.sleep(0.08)
            self.turn_camera(320, 0)
            _key_down(VK_SPACE)
            time.sleep(0.08)
            _key_up(VK_SPACE)
        elif mode == "combat":
            strafe = random.choice(["a", "d"])
            self.walk([strafe, "w"], 1.0, auto_jump=True)
            if self._stop_flag or is_esc_pressed():
                return
            self.turn_camera(random.randint(-140, 140), random.randint(-25, 25))
            self.tap_attack(clicks=3)
        else:
            self.walk(["w"], 1.6, auto_jump=True, sprint=True)
            if self._stop_flag or is_esc_pressed():
                return
            self.turn_camera(random.choice([-160, -100, 100, 160]), random.randint(-20, 20))
            self.hold_attack(sec=0.9)

    def start_autopilot_routine(
        self,
        mode: str = "explore",
        duration_sec: float = 20.0,
        on_done: Optional[Callable[[str], None]] = None,
        brain: Optional[Any] = None,
        on_say: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Inicia el Agente Jugador en segundo plano con bucle Visión -> Acción (~2.5s):
        - Auto-enfoca la ventana del videojuego (`focus_game_window`).
        - Si `brain` está disponible, descarga Ollama de la VRAM (`unload_ollama_vram`) y usa Visión Cloud
          (`plan_game_action`) para ver el juego, comentar sus jugadas y ejecutar micro-acciones reales.
        - Si no hay visión disponible, usa la rutina física de respaldo.
        """
        if self.is_playing:
            return "Ya estoy jugando por ti ahora mismo, choom. Presiona ESC o dime 'deja de jugar' para parar."

        self._stop_flag = False
        self.is_playing = True
        focused_title = self.focus_game_window()
        controls_note = self.keys_reader.read_summary(focused_title)

        if brain is not None:
            try:
                brain.gaming_active = True
                brain.unload_ollama_vram()
            except Exception:
                pass

        def _worker() -> None:
            try:
                # Dar 1.0s para estabilizar el foco en la ventana del juego
                for _ in range(10):
                    if self._stop_flag or is_esc_pressed():
                        return
                    time.sleep(0.1)

                game_title = self.focus_game_window() or focused_title or "Minecraft"
                self.steer_cursor()
                end_time = time.time() + max(6.0, min(duration_sec, 45.0))
                cycle_idx = 0

                while time.time() < end_time and not self._stop_flag and not is_esc_pressed():
                    cycle_start = time.time()
                    executed_vision = False

                    if brain is not None and mode != "dance":
                        plan = brain.plan_game_action(game_title, mode, controls_note)
                        actions = plan.get("actions") if isinstance(plan, dict) else None
                        say_line = (plan.get("say") or "").strip() if isinstance(plan, dict) else ""

                        if say_line and on_say is not None and (cycle_idx % 2 == 0):
                            try:
                                on_say(say_line)
                            except Exception:
                                pass

                        if actions:
                            executed_vision = True
                            self._execute_plan_actions(actions)

                    if not executed_vision:
                        self._run_physical_fallback_step(mode)

                    cycle_idx += 1
                    # Mantener ritmo de ~2.5s por ciclo Visión -> Acción
                    elapsed = time.time() - cycle_start
                    rem = max(0.15, 2.5 - elapsed)
                    steps = int(rem / 0.05)
                    for _ in range(steps):
                        if self._stop_flag or is_esc_pressed() or time.time() >= end_time:
                            break
                        time.sleep(0.05)
            finally:
                for vk in (VK_MAP["w"], VK_MAP["a"], VK_MAP["s"], VK_MAP["d"], VK_SPACE, VK_LSHIFT, VK_LCONTROL):
                    _key_up(vk)
                _mouse_nudge(0, 0, MOUSEEVENTF_LEFTUP)
                _mouse_nudge(0, 0, MOUSEEVENTF_RIGHTUP)
                was_interrupted = self._stop_flag or is_esc_pressed()
                self.is_playing = False
                self._stop_flag = False
                if on_done:
                    if was_interrupted:
                        on_done("Detecté ESC y te devolví el control del juego al instante, choom.")
                    else:
                        on_done("Terminé mi turno al mando del juego, choom. ¿Qué tal jugué?")

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()

        mode_es = "baile gamer" if mode == "dance" else ("combate y strafe" if mode == "combat" else "exploración y supervivencia con visión")
        target_label = f" en '{focused_title}'" if focused_title else ""
        return (
            f"¡Tomando los controles{target_label} en modo {mode_es} por {int(duration_sec)}s! "
            f"({controls_note}) — Pulsa ESC en cualquier momento para detenerme."
        )

