"""
Gestor de Enjambre de Clones (Swarm) y Modo Holograma (Click-Through) para Capri Desktop.
Portado de `Clones.cs` y `ChaosScreen.cs` (`lachydotmcg/capri-desktop`).

Características:
1. Enjambre de Clones:
   - Permite invocar N copias Chibi de Capri ("haz 5 clones", "llena mi pantalla de clones").
   - Cada clon tiene su posición, velocidad, estado aleatorio (idle, walk, perch, sleep)
     y frases traviesas de `NoteLines`:
     "there are more of me now", "we voted. you lost.", "hold esc if you're scared",
     "capri.exe has duplicated", "we're unionising", "who let me out",
     "don't check task manager", "all of us are the real one".
   - Al presionar/mantener ESC o pulsar 'Limpiar clones', todos se disuelven en un glitch.
2. Modo Holograma (Click-Through):
   - Hace que la ventana de Capri ignore clicks del ratón (`WS_EX_TRANSPARENT` o `window_manager.setIgnoreMouseEvents(true)`),
     permitiendo jugar o hacer clics justo debajo de ella sin moverla.
"""

from dataclasses import dataclass, field
import random
import time
from typing import Dict, List, Optional, Tuple


CLONE_QUOTES = [
    "there are more of me now",
    "we voted. you lost.",
    "hold esc if you're scared",
    "capri.exe has duplicated",
    "we're unionising",
    "who let me out",
    "don't check task manager",
    "all of us are the real one",
    "nice desktop, choom",
    "i named the others",
    "jk. your files are fine",
    "chaos protocol initiated",
]


@dataclass
class DesktopClone:
    id: int
    x: float
    y: float
    vx: float
    vy: float
    skin: str = "shader"
    state: str = "Idle"
    quote: str = ""
    quote_until: float = 0.0
    born_at: float = field(default_factory=time.time)


class CapriClonesManager:
    def __init__(self) -> None:
        self.clones: List[DesktopClone] = []
        self._next_id = 1
        self.hologram_mode: bool = False
        self.max_clones: int = 15

    def spawn(self, count: int = 3, skin: str = "shader") -> Tuple[int, str]:
        c = max(1, min(count, self.max_clones - len(self.clones)))
        if c <= 0:
            return 0, f"Ya hay demasiados clones en tu escritorio ({len(self.clones)}). Mantén Esc para limpiarlos."

        for _ in range(c):
            clone_id = self._next_id
            self._next_id += 1
            # Posición aleatoria dentro de una pantalla estándar
            x = random.uniform(100.0, 1100.0)
            y = random.uniform(150.0, 650.0)
            vx = random.choice([-1.5, -1.0, 1.0, 1.5])
            vy = random.uniform(-0.5, 0.5)
            q = random.choice(CLONE_QUOTES)
            now = time.time()
            self.clones.append(DesktopClone(
                id=clone_id,
                x=x,
                y=y,
                vx=vx,
                vy=vy,
                skin=skin,
                state=random.choice(["Idle", "Sitting", "Intro"]),
                quote=q,
                quote_until=now + random.uniform(3.0, 6.0),
            ))

        total = len(self.clones)
        msg = f"¡Invoqué {c} clones más! Ahora somos {total} en tu pantalla. (Mantén Esc si te asustas)."
        return c, msg

    def clear(self) -> Tuple[int, str]:
        count = len(self.clones)
        self.clones.clear()
        if count > 0:
            return count, f"Clones desvanecidos ({count}). Solo quedo yo, choom."
        return 0, "No había clones activos."

    def toggle_hologram(self, enable: Optional[bool] = None) -> Tuple[bool, str]:
        if enable is not None:
            self.hologram_mode = enable
        else:
            self.hologram_mode = not self.hologram_mode

        st = "ACTIVADO" if self.hologram_mode else "DESACTIVADO"
        msg = (
            f"Modo Holograma {st}: los clics atraviesan mi cuerpo directamente a tus ventanas."
            if self.hologram_mode
            else f"Modo Holograma {st}: ya puedes interactuar y moverme normalmente."
        )
        return self.hologram_mode, msg

    def to_event_payload(self) -> Dict[str, any]:
        return {
            "clones": [
                {
                    "id": c.id,
                    "x": c.x,
                    "y": c.y,
                    "skin": c.skin,
                    "state": c.state,
                    "quote": c.quote if time.time() < c.quote_until else "",
                }
                for c in self.clones
            ],
            "hologram": self.hologram_mode,
            "count": len(self.clones),
        }

