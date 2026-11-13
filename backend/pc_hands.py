"""
Manos de PC, Escáner de Aplicaciones/Juegos, Gestión de Ventanas (Ledges) y Recordatorios
(Ingeniería inversa de `app/Hands.cs`, `app/Ledges.cs`, `app/Websites.cs` y `app/Reminders.cs` de `lachydotmcg/capri-desktop`).
"""

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import subprocess
import time
import webbrowser
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = Path(__file__).resolve().parent / "data"
REMINDERS_FILE = DATA_DIR / "reminders.json"
WEBSITES_FILE = DATA_DIR / "websites.json"

# Protocolos rápidos y ejecutables directos de Windows
KNOWN_TARGETS: Dict[str, str] = {
    "notepad": "notepad.exe",
    "bloc de notas": "notepad.exe",
    "calculadora": "calc.exe",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "explorador": "explorer.exe",
    "explorer": "explorer.exe",
    "archivos": "explorer.exe",
    "cmd": "cmd.exe",
    "terminal": "wt.exe",
    "powershell": "powershell.exe",
    "paint": "mspaint.exe",
    "task manager": "taskmgr.exe",
    "administrador de tareas": "taskmgr.exe",
    "configuracion": "ms-settings:",
    "settings": "ms-settings:",
    "spotify": "spotify:",
    "discord": "discord:",
    "steam": "steam://open/main",
    "vscode": "code",
    "visual studio code": "code",
    "code": "code",
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "brave": "brave",
    "firefox": "firefox",
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "reddit": "https://www.reddit.com",
    "twitch": "https://www.twitch.tv",
    "chatgpt": "https://chatgpt.com",
    "whatsapp": "https://web.whatsapp.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
}


class PCHandsManager:
    """
    Controlador de aplicaciones instaladas, ventanas del escritorio (`Ledges`),
    recordatorios/temporizadores (`Reminders`) y apodos de sitios web (`Websites`).
    """

    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._shortcut_index: Dict[str, str] = {}
        self._indexed_at: float = 0.0
        self.reminders: List[Dict[str, Any]] = self._load_json(REMINDERS_FILE, [])
        self.websites: Dict[str, str] = self._load_json(WEBSITES_FILE, {})

    @staticmethod
    def _load_json(path: Path, default: Any) -> Any:
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return default

    @staticmethod
    def _save_json(path: Path, data: Any) -> None:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _refresh_app_index(self) -> None:
        """Indexa accesos directos `.lnk` del Menú Inicio y carpetas de juegos (Steam/Epic/Riot)."""
        now = time.time()
        if self._shortcut_index and now - self._indexed_at < 120.0:
            return
        self._indexed_at = now
        index: Dict[str, str] = {}

        # 1. Menú Inicio (Usuario y Sistema)
        start_dirs = [
            os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%USERPROFILE%\Desktop"),
        ]
        for base in start_dirs:
            if not os.path.isdir(base):
                continue
            for root, _, files in os.walk(base):
                for f in files:
                    if f.lower().endswith((".lnk", ".url")):
                        name = os.path.splitext(f)[0].strip().lower()
                        if name and not any(skip in name for skip in ("uninstall", "desinstalar", "readme", "help")):
                            index[name] = os.path.join(root, f)

        # 2. Juegos de Steam (`steamapps/common`)
        steam_dirs = [
            r"C:\Program Files (x86)\Steam\steamapps\common",
            r"C:\Program Files\Steam\steamapps\common",
            r"D:\SteamLibrary\steamapps\common",
            r"E:\SteamLibrary\steamapps\common",
        ]
        for sdir in steam_dirs:
            if not os.path.isdir(sdir):
                continue
            try:
                for folder in os.listdir(sdir):
                    full_folder = os.path.join(sdir, folder)
                    if os.path.isdir(full_folder):
                        # Buscar el .exe principal dentro de la carpeta del juego
                        for f in os.listdir(full_folder):
                            if f.lower().endswith(".exe") and "crash" not in f.lower() and "unitycrash" not in f.lower():
                                index[folder.lower()] = os.path.join(full_folder, f)
                                break
            except Exception:
                pass

        self._shortcut_index = index

    def open_apps_or_sites(self, raw_target: str) -> Tuple[bool, str]:
        """
        Permite abrir una o varias aplicaciones, juegos o páginas web en una sola frase
        (ej. "Discord, Spotify y YouTube").
        """
        cleaned = raw_target.strip().strip("\"'")
        if not cleaned:
            return False, "¿Qué aplicación o página quieres que abra, choom?"

        # Separar si pidió varias apps: "Discord, Spotify y Steam"
        parts = [
            p.strip()
            for p in re.split(r"\s*(?:,|\by\b|\band\b)\s*", cleaned, flags=re.IGNORECASE)
            if p.strip()
        ]
        if not parts:
            parts = [cleaned]

        self._refresh_app_index()
        opened_names: List[str] = []

        for item in parts:
            key = item.lower().strip()
            key = re.sub(r"^(?:el|la|los|las|mi|my|the)\s+", "", key).strip()

            # 1. ¿Es un apodo de sitio web guardado por el usuario (`Websites.cs`)?
            if key in self.websites:
                webbrowser.open(self.websites[key])
                opened_names.append(item)
                continue

            # 2. ¿Está en la tabla rápida de apps/protocolos conocidos?
            if key in KNOWN_TARGETS:
                target = KNOWN_TARGETS[key]
                try:
                    if target.startswith(("http://", "https://", "spotify:", "discord:", "steam:", "ms-settings:")):
                        os.startfile(target)  # type: ignore[attr-defined]
                    else:
                        subprocess.Popen(target, shell=True)
                    opened_names.append(item)
                    continue
                except Exception:
                    pass

            # 3. ¿Parece un dominio web directo (ej. `canva.com`)?
            if "." in key and " " not in key:
                url = key if key.startswith(("http://", "https://")) else f"https://{key}"
                webbrowser.open(url)
                opened_names.append(item)
                continue

            # 4. Buscar coincidencia exacta o parcial en el índice del Menú Inicio y Steam
            matched_path: Optional[str] = self._shortcut_index.get(key)
            if not matched_path:
                for idx_name, idx_path in self._shortcut_index.items():
                    if key in idx_name or idx_name in key:
                        matched_path = idx_path
                        break

            if matched_path:
                try:
                    os.startfile(matched_path)  # type: ignore[attr-defined]
                    opened_names.append(item)
                    continue
                except Exception:
                    pass

            # 5. Fallback: intentar ejecutar o abrir en navegador
            try:
                os.startfile(key)  # type: ignore[attr-defined]
                opened_names.append(item)
            except Exception:
                webbrowser.open(f"https://www.google.com/search?q={key}")
                opened_names.append(f"{item} (web)")

        if opened_names:
            joined = ", ".join(opened_names)
            return True, f"Nova, choom. Ya te abrí {joined}."
        return False, f"No encontré '{cleaned}' en tu sistema, choom."

    # ── Gestión de Ventanas y Bordes (`Ledges.cs` + `Hands.cs`) ──────────

    def list_visible_windows(self) -> List[Dict[str, Any]]:
        """Devuelve la lista de ventanas visibles con su posición y tamaño (`Ledges.cs`)."""
        windows: List[Dict[str, Any]] = []
        try:
            user32 = ctypes.windll.user32
            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            def callback(hwnd: int, _lparam: int) -> bool:
                if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length <= 0:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value.strip()
                if not title or title.lower() in ("program manager", "capri", "settings"):
                    return True

                rect = wintypes.RECT()
                if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top
                    if w >= 200 and h >= 120:
                        windows.append(
                            {
                                "hwnd": hwnd,
                                "title": title,
                                "left": rect.left,
                                "top": rect.top,
                                "right": rect.right,
                                "bottom": rect.bottom,
                                "width": w,
                                "height": h,
                                "maximized": bool(user32.IsZoomed(hwnd)),
                            }
                        )
                return True

            user32.EnumWindows(WNDENUMPROC(callback), 0)
        except Exception:
            pass
        return windows

    def control_window(self, action: str, target_name: str) -> str:
        """Permite cambiar a una ventana (`focus`), minimizarla (`minimize`) o cerrarla (`close`)."""
        query = target_name.strip().lower()
        user32 = ctypes.windll.user32
        for w in self.list_visible_windows():
            if query in w["title"].lower():
                hwnd = w["hwnd"]
                if action == "minimize":
                    user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
                    return f"Minimicé la ventana '{w['title']}', choom."
                elif action == "close":
                    user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
                    return f"Cerré '{w['title']}', choom."
                else:
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd)
                    return f"Traje '{w['title']}' al frente, choom."
        return f"No encontré ninguna ventana abierta que coincida con '{target_name}'."

    def find_best_perch_ledge(self) -> Optional[Dict[str, Any]]:
        """
        Encuentra una ventana abierta con borde superior visible (`Ledges.cs`) para que
        Capri salte y se siente sobre ella.
        """
        for w in self.list_visible_windows():
            if not w["maximized"] and 40 <= w["top"] <= 750 and w["width"] >= 320:
                # Posicionar a Capri sobre el borde superior de la ventana
                target_x = int(w["left"] + min(w["width"] * 0.65, w["width"] - 220))
                target_y = max(0, int(w["top"] - 210))
                return {
                    "title": w["title"],
                    "x": target_x,
                    "y": target_y,
                }
        return None

    # ── Temporizadores y Recordatorios (`Reminders.cs`) ─────────────────

    def add_timer_or_reminder(self, text: str, seconds_from_now: float) -> str:
        due_ts = time.time() + max(1.0, seconds_from_now)
        entry = {
            "text": text.strip(),
            "due": due_ts,
            "said": False,
        }
        self.reminders.append(entry)
        self._save_json(REMINDERS_FILE, self.reminders)

        mins = int(seconds_from_now // 60)
        secs = int(seconds_from_now % 60)
        if mins > 0 and secs > 0:
            span_str = f"{mins} min {secs} s"
        elif mins > 0:
            span_str = f"{mins} minuto{'s' if mins != 1 else ''}"
        else:
            span_str = f"{secs} segundo{'s' if secs != 1 else ''}"
        return f"Hecho, choom. Te aviso en {span_str}: «{text.strip()}»."

    def list_reminders(self) -> str:
        now = time.time()
        pending = [r for r in self.reminders if not r.get("said") and r.get("due", 0) > now]
        if not pending:
            return "No tienes recordatorios ni temporizadores pendientes ahora mismo, choom."
        lines = []
        for r in pending:
            rem = max(0, int(r["due"] - now))
            m, s = divmod(rem, 60)
            lines.append(f"• {r['text']} (en {m}m {s}s)")
        return "Tus recordatorios activos:\n" + "\n".join(lines)

    def pop_due_reminders(self) -> List[str]:
        """Devuelve los textos de los recordatorios/temporizadores que ya vencieron."""
        now = time.time()
        fired: List[str] = []
        changed = False
        for r in self.reminders:
            if not r.get("said") and r.get("due", 0) <= now:
                r["said"] = True
                fired.append(r.get("text", "¡Tiempo cumplido!"))
                changed = True
        if changed:
            self._save_json(REMINDERS_FILE, self.reminders)
        return fired

