"""
Gestor de Recordatorios Fechados y Temporizadores para Capri Desktop Companion.
Portado de `Reminders.cs` (`lachydotmcg/capri-desktop`).

Soporta:
1. Temporizadores relativos:
   - "en 10 minutos sacar la pizza"
   - "en 1 hora y 30 minutos apagar la PC"
   - "en 45 segundos"
2. Fechas absolutas y horas:
   - "mañana a las 9am llamar al médico"
   - "hoy a las 20:30 cenar con chooms"
   - "el 5 de diciembre a las 14:00 cita de proyecto"
   - "el viernes a las 18:00"
3. Listar y cancelar recordatorios pendientes.
4. Persistencia en `backend/data/reminders.json`.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple


MONTHS_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

DAYS_ES = {
    "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2, "jueves": 3,
    "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4,
    "saturday": 5, "sunday": 6,
}


@dataclass
class DatedReminder:
    id: int
    text: str
    due_iso: str
    created_at: float = field(default_factory=time.time)
    spoken: bool = False

    @property
    def due_dt(self) -> datetime:
        try:
            return datetime.fromisoformat(self.due_iso)
        except Exception:
            return datetime.now()


class CapriDatedReminders:
    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = data_dir or (Path(__file__).resolve().parent / "data")
        self.file_path = self.data_dir / "reminders.json"
        self._lock = threading.Lock()
        self._next_id = 1
        self.reminders: List[DatedReminder] = []
        self._load()

    def _load(self) -> None:
        try:
            if self.file_path.exists():
                data = json.loads(self.file_path.read_text(encoding="utf-8"))
                for item in data:
                    r = DatedReminder(
                        id=int(item["id"]),
                        text=str(item["text"]),
                        due_iso=str(item["due_iso"]),
                        created_at=float(item.get("created_at", time.time())),
                        spoken=bool(item.get("spoken", False)),
                    )
                    self.reminders.append(r)
                    if r.id >= self._next_id:
                        self._next_id = r.id + 1
        except Exception:
            pass

    def _save(self) -> None:
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            data = [
                {
                    "id": r.id,
                    "text": r.text,
                    "due_iso": r.due_iso,
                    "created_at": r.created_at,
                    "spoken": r.spoken,
                }
                for r in self.reminders
            ]
            self.file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    @classmethod
    def parse_time_and_text(cls, raw: str) -> Tuple[Optional[datetime], str]:
        """
        Extrae la fecha/hora de vencimiento y el texto a recordar de una frase natural.
        """
        text = raw.strip()
        now = datetime.now()

        # 1. Tiempos relativos: "en X minutos/horas/segundos [de / que / para] <texto>"
        rel_match = re.search(
            r"\ben\s+(?:(\d+)\s*(?:horas?|h))?\s*(?:(\d+)\s*(?:minutos?|mins?|m))?\s*(?:(\d+)\s*(?:segundos?|segs?|s))?\s*(?:(?:de|que|para)\s+)?(.*)$",
            text,
            re.IGNORECASE,
        )
        if rel_match and (rel_match.group(1) or rel_match.group(2) or rel_match.group(3)):
            hours = int(rel_match.group(1) or 0)
            minutes = int(rel_match.group(2) or 0)
            seconds = int(rel_match.group(3) or 0)
            reminder_text = (rel_match.group(4) or "").strip()
            due = now + timedelta(hours=hours, minutes=minutes, seconds=seconds)
            return due, reminder_text or text

        # 2. "mañana a las HH:MM [texto]" o "hoy a las HH:MM [texto]"
        day_match = re.search(
            r"\b(hoy|mañana|manana)\s+(?:a\s+las?|a)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:(?:de|que|para)\s+)?(.*)$",
            text,
            re.IGNORECASE,
        )
        if day_match:
            day_type = day_match.group(1).lower()
            hour = int(day_match.group(2))
            minute = int(day_match.group(3) or 0)
            meridiem = (day_match.group(4) or "").lower()
            reminder_text = (day_match.group(5) or "").strip()

            if meridiem == "pm" and hour < 12:
                hour += 12
            elif meridiem == "am" and hour == 12:
                hour = 0

            target_date = now.date() if day_type == "hoy" else now.date() + timedelta(days=1)
            due = datetime(target_date.year, target_date.month, target_date.day, hour, minute)
            if day_type == "hoy" and due <= now:
                due += timedelta(days=1)
            return due, reminder_text or text

        # 3. "el DD de Mes [a las HH:MM] [texto]"
        cal_match = re.search(
            r"\bel\s+(\d{1,2})\s+de\s+([a-záéíóú]+)(?:\s+(?:de\s+)?(\d{4}))?(?:\s+(?:a\s+las?|a)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?\s*(?:(?:de|que|para)\s+)?(.*)$",
            text,
            re.IGNORECASE,
        )
        if cal_match:
            day = int(cal_match.group(1))
            month_name = cal_match.group(2).lower()
            month = MONTHS_ES.get(month_name, 0)
            year = int(cal_match.group(3) or now.year)
            hour = int(cal_match.group(4) or 9)
            minute = int(cal_match.group(5) or 0)
            meridiem = (cal_match.group(6) or "").lower()
            reminder_text = (cal_match.group(7) or "").strip()

            if month > 0:
                if meridiem == "pm" and hour < 12:
                    hour += 12
                elif meridiem == "am" and hour == 12:
                    hour = 0
                due = datetime(year, month, day, hour, minute)
                if due <= now and not cal_match.group(3):
                    due = datetime(year + 1, month, day, hour, minute)
                return due, reminder_text or text

        return None, text

    def add_reminder(self, raw_input: str, due: Optional[datetime] = None) -> Tuple[int, str]:
        if due is None:
            parsed_due, clean_text = self.parse_time_and_text(raw_input)
            if not parsed_due:
                # Fallback por defecto a 10 minutos
                due = datetime.now() + timedelta(minutes=10)
                clean_text = raw_input.strip()
            else:
                due = parsed_due
        else:
            clean_text = raw_input.strip()

        with self._lock:
            r_id = self._next_id
            self._next_id += 1
            rem = DatedReminder(id=r_id, text=clean_text or "Alerta programada", due_iso=due.isoformat())
            self.reminders.append(rem)
            self._save()

            diff = due - datetime.now()
            mins = int(diff.total_seconds() // 60)
            if mins < 60:
                time_str = f"en {max(1, mins)} minuto(s)"
            else:
                time_str = f"para {due.strftime('%d/%m a las %H:%M')}"

            return r_id, f"Listo, choom. Te recordaré '{clean_text}' {time_str}."

    def list_pending(self) -> List[Dict[str, any]]:
        with self._lock:
            pending = [r for r in self.reminders if not r.spoken]
            pending.sort(key=lambda x: x.due_dt)
            return [
                {
                    "id": r.id,
                    "text": r.text,
                    "due": r.due_dt.strftime("%d/%m/%Y %H:%M"),
                    "minutes_left": max(0, int((r.due_dt - datetime.now()).total_seconds() // 60)),
                }
                for r in pending
            ]

    def cancel_reminder(self, search: Any = "") -> str:
        s = str(search or "").strip().lower()
        with self._lock:
            if not self.reminders:
                return "No tienes ningún recordatorio guardado."
            if not s:
                count = len(self.reminders)
                self.reminders.clear()
                self._save()
                return f"Se cancelaron todos los recordatorios ({count})."

            kept = []
            removed = []
            for r in self.reminders:
                if s in str(r.id) or s in r.text.lower():
                    removed.append(r.text)
                else:
                    kept.append(r)
            self.reminders = kept
            self._save()
            if removed:
                return f"Cancelado: '{', '.join(removed)}'."
            return f"No encontré recordatorios que coincidan con '{search}'."

    def check_due(self) -> List[DatedReminder]:
        """Devuelve los recordatorios que acaban de vencer y no se han dicho."""
        now = datetime.now()
        due_list = []
        with self._lock:
            changed = False
            for r in self.reminders:
                if not r.spoken and r.due_dt <= now:
                    r.spoken = True
                    due_list.append(r)
                    changed = True
            if changed:
                self._save()
        return due_list
