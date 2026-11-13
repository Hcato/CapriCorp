"""
Módulo de Vigilancia Visual (Lookout) para Capri Desktop Companion.
Portado de `Lookout.cs` (`lachydotmcg/capri-desktop`).

Permite a Capri vigilar tu pantalla ante condiciones específicas como:
- "Avísame cuando termine la descarga"
- "Avisa si mi salud baja de la mitad"
- "Dime cuando el render de Blender finalice"
- "Vigila si me mandan un mensaje en Discord"

Flujo de ejecución:
1. Registra condiciones (`WatchCondition`).
2. Cada 3 a 5 segundos (si la pantalla cambió significativamente), toma un thumbnail/captura ligera.
3. Envía la imagen al Cerebro con visión (Gemini, NVIDIA NIM o LLM local) usando el prompt oficial de Lookout:
   "Reply exactly NONE if none is happening. Otherwise give the number of every condition happening now... under 14 words: 1: ¡Tu descarga ya terminó, choom!"
4. Al cumplirse, notifica con voz y texto en la burbuja.
"""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class WatchCondition:
    id: int
    text: str
    repeat: bool = False
    reported: bool = False
    created_at: float = field(default_factory=time.time)


class CapriLookout:
    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = data_dir or (Path(__file__).resolve().parent / "data")
        self.watches_file = self.data_dir / "lookout_watches.json"
        self._lock = threading.Lock()
        self._next_id = 1
        self.watches: List[WatchCondition] = []
        self.is_active: bool = True
        self.last_check_time: float = 0.0
        self.check_interval_sec: float = 4.0
        self._last_screen_thumb: Optional[bytes] = None

        self._load()

    def _load(self) -> None:
        try:
            if self.watches_file.exists():
                data = json.loads(self.watches_file.read_text(encoding="utf-8"))
                for item in data:
                    w = WatchCondition(
                        id=int(item["id"]),
                        text=str(item["text"]),
                        repeat=bool(item.get("repeat", False)),
                        reported=bool(item.get("reported", False)),
                        created_at=float(item.get("created_at", time.time())),
                    )
                    self.watches.append(w)
                    if w.id >= self._next_id:
                        self._next_id = w.id + 1
        except Exception:
            pass

    def _save(self) -> None:
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            data = [
                {
                    "id": w.id,
                    "text": w.text,
                    "repeat": w.repeat,
                    "reported": w.reported,
                    "created_at": w.created_at,
                }
                for w in self.watches
            ]
            self.watches_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def add_watch(self, text: str, repeat: bool = False) -> Tuple[int, str]:
        t = text.strip()
        if not t:
            return 0, "Dime qué quieres que vigile en tu pantalla, choom."
        with self._lock:
            w_id = self._next_id
            self._next_id += 1
            w = WatchCondition(id=w_id, text=t, repeat=repeat)
            self.watches.append(w)
            self._save()
            rep_str = " (cada vez que ocurra)" if repeat else ""
            return w_id, f"Entendido, choom. Vigilaré tu pantalla por si: '{t}'{rep_str}."

    def stop_watch(self, search_text: Any = "") -> str:
        with self._lock:
            if not self.watches:
                return "No estoy vigilando nada actualmente."
            s = str(search_text or "").strip().lower()
            if not s:
                count = len(self.watches)
                self.watches.clear()
                self._save()
                return f"Dejé de vigilar todas las condiciones ({count} activas)."

            remaining = []
            removed = []
            for w in self.watches:
                if s in str(w.id) or s in w.text.lower():
                    removed.append(w.text)
                else:
                    remaining.append(w)
            self.watches = remaining
            self._save()
            if removed:
                return f"Dejé de vigilar: {', '.join(removed)}."
            return f"No encontré ninguna vigilancia con '{search_text}'."

    def list_watches(self) -> List[Dict[str, any]]:
        with self._lock:
            return [
                {
                    "id": w.id,
                    "text": w.text,
                    "repeat": w.repeat,
                    "reported": w.reported,
                }
                for w in self.watches
            ]

    def build_prompt_conditions(self) -> str:
        with self._lock:
            pending = [w for w in self.watches if not w.reported or w.repeat]
            if not pending:
                return ""
            lines = []
            for w in pending:
                status = " (ya reportado antes, ignorar si sigue igual)" if w.reported else ""
                lines.append(f"{w.id}. {w.text}{status}")
            return "\n".join(lines)

    def parse_vision_reply(self, reply: str) -> Optional[Tuple[int, str]]:
        """
        Interpreta la respuesta según el formato de Lookout.cs:
        'NONE' -> Nada.
        '1: Tu descarga ya se completó.' -> Se cumplió la condición 1 con ese aviso.
        '2, 1: Tu vida está crítica.' -> Se cumplió la 2 (primera a avisar).
        """
        r = (reply or "").strip()
        if not r or r.upper() == "NONE":
            return None

        m = re.match(r"^([1-9]\d*(?:\s*,\s*[1-9]\d*)*)\s*:\s*(.+)$", r, re.DOTALL)
        if not m:
            return None

        num_str = m.group(1)
        spoken_line = m.group(2).strip()
        # Quitar sub-encabezados si los hubiere
        spoken_line = re.sub(r"\s\d+\s*:\s*\D.*$", "", spoken_line).strip()

        try:
            ids = [int(x.strip()) for x in num_str.split(",") if x.strip().isdigit()]
            if not ids:
                return None
            hit_id = ids[0]
            with self._lock:
                for w in self.watches:
                    if w.id in ids:
                        w.reported = True
                self._save()
            return hit_id, spoken_line
        except Exception:
            return None
