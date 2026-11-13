"""
Agente Enrutador Conversacional y de Herramientas de Capri (`Brain.cs` + `Hands.cs` + `Commentary.cs`).
Combina:
1. Cerebro Conversacional Real (`backend/brain.py`):
   - Autodetección multi-proveedor (Google Gemini, Groq, NVIDIA NIM, OpenRouter, Claude, OpenAI, DeepSeek, Ollama, LM Studio).
   - Tool Calling Agéntico (`TOOLS_SCHEMA`): el LLM decide qué herramienta invocar cuando el usuario pide o insinúa algo.
   - Memoria Autobiográfica de 3 Capas (`me.md`, `memories.md`, `transcripts/YYYY-MM-DD.md`) + Búsqueda Asociativa BM25.
   - Filtros de Naturalidad (`Fresh`, `Unclosed`, `Sparing`) + Segundos Pensamientos espontáneos (`|||` -> `follow_up`).
   - Visión Real de Pantalla (`look_at_screen` con captura PNG en memoria y formato `SAW:` / `SAY:`).
2. Clasificador Rápido de 0ms (`backend/intents.py`) + Voz Dinámica del LLM sobre la acción ejecutada.
"""

from __future__ import annotations

import random
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from . import abilities, intents
from .brain import CapriBrain, CapriDeepMemory, detect_provider_from_key
from .clones_manager import CapriClonesManager
from .game_agent import GameAutopilot
from .lookout import CapriLookout
from .media_player import WindowsMediaController
from .pc_hands import PCHandsManager
from .reminders_dated import CapriDatedReminders

_PASTED_KEY_RE = re.compile(
    r"\b(AIza[0-9A-Za-z_-]{25,}|AQ\.[0-9A-Za-z._-]{25,}|gsk_[0-9A-Za-z]{25,}|nvapi-[0-9A-Za-z_-]{25,}|sk-or-[0-9A-Za-z_-]{25,}|sk-ant-[0-9A-Za-z_-]{25,}|sk-[0-9A-Za-z_-]{25,})\b"
)


@dataclass
class AgentResponse:
    reply_text: str
    state: str = "Speaking"
    extra_events: list[dict[str, Any]] = field(default_factory=list)
    routed_to: str = "intent"
    follow_up: str = ""


class CapriRouterAgent:
    def __init__(self, user_name: str = "choom"):
        self.deep_memory = CapriDeepMemory()
        if user_name and self.deep_memory.user_name == "choom":
            self.deep_memory.user_name = user_name
        self.brain = CapriBrain(self.deep_memory)
        self.memory = abilities.CapriMemory()
        self.media = WindowsMediaController()
        self.hands = PCHandsManager()
        self.games = GameAutopilot()
        self.lookout = CapriLookout()
        self.dated_reminders = CapriDatedReminders()
        self.clones_mgr = CapriClonesManager()
        self.on_autopilot_say = None

    @property
    def user_name(self) -> str:
        return self.deep_memory.user_name

    def _build_live_context(self) -> list[str]:
        notes: list[str] = []
        active_win = abilities.get_active_window_title()
        win_low = (active_win or "").lower()
        is_editor_or_browser = any(
            app in win_low
            for app in (
                "antigravity",
                "visual studio",
                "vscode",
                "code.exe",
                "chrome",
                "edge",
                "brave",
                "firefox",
                "opera",
                "powershell",
                "cmd.exe",
                "notepad",
                "capri",
            )
        )
        is_game_win = bool(
            active_win
            and not is_editor_or_browser
            and self.games.KNOWN_GAMES_REGEX.search(active_win)
        )
        self.brain.gaming_active = is_game_win or self.games.is_playing
        if self.brain.gaming_active:
            self.brain.unload_ollama_vram()
        if active_win:
            notes.append(f"Ventana activa en su PC: {active_win}")
        if is_game_win:
            notes.append(f"Juego activo detectado (Modo 0-VRAM Cloud): {active_win}")

        tune = self.media.poll_current_tune()
        if tune.get("title"):
            st = "Sonando ahora" if tune.get("playing") else "En pausa"
            notes.append(f"Música ({st}): {tune.get('artist', '')} - {tune.get('title', '')} ({tune.get('app', '')})")

        if self.games.sense.enabled:
            notes.append("GameSense activo: estás vigilando su partida en vivo.")
        return notes

    def process_user_message(self, text: str) -> AgentResponse:
        clean = (text or "").strip()
        if not clean:
            return AgentResponse("Habla más fuerte, choom, no te escuché nada.")

        # 0. Paso 0: Si el usuario pega una API Key directamente en el chat (ej. AIza..., AQ..., gsk_..., nvapi-...),
        #    guardarla automáticamente en `brain_config.json` y activar el Cerebro IA al instante.
        key_match = _PASTED_KEY_RE.search(clean)
        if key_match:
            pasted_key = key_match.group(1).strip()
            detected_kind = detect_provider_from_key(pasted_key) or "auto"
            st = self.brain.save_config(api_key=pasted_key, provider=detected_kind)
            status_dict = asdict(st)
            status_dict["user_name"] = self.user_name
            status_dict["notes_count"] = len(self.deep_memory.get_notes_lines())
            status_ev = {"event": "brain_status", "status": status_dict}

            test_reply = self.react_to_live_event(
                "enlace neuronal conectado",
                f"El usuario acaba de conectarte una llave de {st.active_label}. Salúdalo con mucha energía en 1 o 2 frases.",
            )
            if test_reply:
                return AgentResponse(
                    reply_text=test_reply,
                    state="Victory",
                    extra_events=[status_ev, {"event": "change_state", "state": "Victory"}],
                    routed_to=st.provider,
                )
            err_hint = f" ({self.brain.last_error})" if self.brain.last_error else ""
            return AgentResponse(
                reply_text=(
                    f"Guardé tu llave en mi biochip ({st.active_label}), pero el servidor devolvió un error al probarla{err_hint}. "
                    "Si es de Google Gemini, asegúrate de crearla en aistudio.google.com/apikey (empiezan por AIzaSy...) o prueba una gratis de Groq (console.groq.com, gsk_...)."
                ),
                state="Speaking",
                extra_events=[status_ev],
                routed_to="config-error",
            )

        live_ctx = self._build_live_context()

        # 1. Paso 1: Si es una consulta de visión de pantalla ("qué ves en mi pantalla"), intentar Visión Real primero
        intent = intents.detect_intent(clean)
        if intent is not None and intent.kind == "screen":
            vision_line = self.brain.look_at_screen_with_vision(clean, live_ctx)
            if vision_line:
                self.deep_memory.add_turn(clean, vision_line)
                return AgentResponse(
                    reply_text=vision_line,
                    state="Point",
                    extra_events=[{"event": "change_state", "state": "Point"}],
                    routed_to="vision",
                )

        # 2. Paso 2: Si coincide con un atajo rápido de 0ms, ejecutar la acción real en el PC
        #    y pasar el resultado por el Cerebro LLM para que Capri lo comente con su propia voz viva
        if intent is not None:
            base_res = self._handle_intent(intent, clean)
            llm_reply, follow_up, _, prov = self.brain.ask_with_tools(
                user_text=clean,
                live_context=live_ctx,
                tool_executor=self._execute_tool_call,
                pre_executed_tool=(intent.kind, base_res.reply_text, []),
            )
            final_text = llm_reply if llm_reply else base_res.reply_text
            self.deep_memory.add_turn(clean, final_text)
            return AgentResponse(
                reply_text=final_text,
                state=base_res.state,
                extra_events=base_res.extra_events,
                routed_to=f"intent+{prov}" if llm_reply else "intent",
                follow_up=follow_up,
            )

        # 3. Paso 3: Conversación libre + Tool Calling Agéntico (`Hands.WorkingOut` + `Brain.WorkOut`)
        llm_reply, follow_up, tool_events, prov = self.brain.ask_with_tools(
            user_text=clean,
            live_context=live_ctx,
            tool_executor=self._execute_tool_call,
        )
        if llm_reply:
            self.deep_memory.add_turn(clean, llm_reply)
            target_state = "Speaking"
            for ev in tool_events:
                if ev.get("event") == "change_state" and ev.get("state"):
                    target_state = str(ev["state"])
            return AgentResponse(
                reply_text=llm_reply,
                state=target_state,
                extra_events=tool_events,
                routed_to=prov,
                follow_up=follow_up,
            )

        # 4. Fallback instantáneo en personaje si aún no hay ningún proveedor/servidor activo
        active_win = abilities.get_active_window_title()
        fallback = self._character_fallback(clean, active_win)
        self.deep_memory.add_turn(clean, fallback)
        return AgentResponse(
            reply_text=fallback,
            state="Speaking",
            extra_events=tool_events,
            routed_to="local-persona",
        )

    def react_to_live_event(self, event_kind: str, detail: str) -> str | None:
        """Genera un comentario espontáneo en vivo (jugada de minijuego, daño en GameSense, etc.)."""
        live_ctx = self._build_live_context()
        return self.brain.react_to_event(event_kind, detail, live_ctx)

    # ─────────────────────────────────────────────────────────────────────────
    # EJECUTOR DE HERRAMIENTAS PARA TOOL CALLING DEL LLM (`Hands.WorkingOut`)
    # ─────────────────────────────────────────────────────────────────────────

    def _execute_tool_call(
        self, tool_name: str, args: dict[str, Any]
    ) -> tuple[str, list[dict[str, Any]]]:
        t = (tool_name or "").strip().lower()
        args = args or {}

        if t == "open_app":
            name = str(args.get("name") or "").strip()
            ok, msg = self.hands.open_apps_or_sites(name)
            evs = [{"event": "change_state", "state": "Victory"}] if ok else []
            return msg, evs

        if t == "open_website":
            site = str(args.get("site") or "").strip()
            search = str(args.get("search") or "").strip()
            if search:
                msg = abilities.search_on_web(f"{site} {search}".strip())
                return msg, [{"event": "change_state", "state": "Point"}]
            ok, msg = self.hands.open_apps_or_sites(site)
            return msg, [{"event": "change_state", "state": "Point"}] if ok else []

        if t == "play_music":
            song = str(args.get("song") or "tu favorita").strip()
            app = str(args.get("app") or "youtube").strip().lower()
            if song.lower() in ("música", "musica", "algo", "algo bueno", "music", "something", "tu favorita"):
                song = random.choice(abilities.NIGHT_CITY_TRACKS)
            query = f"spotify {song}" if app == "spotify" else song
            tune = self.media.execute_command("play_query", query)
            return f"Reproduciendo «{song}»", [
                {"event": "change_state", "state": "Victory"},
                {"event": "media_state", "tune": tune},
                {"event": "dance", "enabled": True},
            ]

        if t == "media_control":
            action = str(args.get("action") or "whats_playing").strip().lower()
            if action == "whats_playing":
                tune = self.media.poll_current_tune()
                if tune.get("title"):
                    return f"Está sonando «{tune['title']}» de {tune['artist']} en {tune['app']}", [
                        {"event": "media_state", "tune": tune}
                    ]
                return "No hay música sonando ahora mismo.", []
            cmd_map = {"play_pause": "pause", "mute": "vol_down"}
            mapped = cmd_map.get(action, action)
            tune = self.media.execute_command(mapped)
            return f"Comando multimedia '{action}' ejecutado.", [{"event": "media_state", "tune": tune}]

        if t == "window_control":
            action = str(args.get("action") or "focus").strip().lower()
            name = str(args.get("name") or "").strip()
            if action == "perch":
                ledge = self.hands.find_best_perch_ledge()
                if ledge:
                    return f"Saltaste al borde superior de la ventana '{ledge['title']}'", [
                        {"event": "posture", "posture": "perch"},
                        {"event": "move_to", "x": ledge["x"], "y": ledge["y"]},
                    ]
                return "Te sentaste en el escritorio", [{"event": "posture", "posture": "perch"}]
            msg = self.hands.control_window(action, name)
            return msg, []

        if t == "move_yourself":
            action = str(args.get("action") or "stand").strip().lower()
            events_map: dict[str, tuple[str, list[dict[str, Any]]]] = {
                "stand": ("Te pusiste de pie", [{"event": "posture", "posture": "standing"}]),
                "sit": ("Te sentaste", [{"event": "posture", "posture": "perch"}]),
                "lay": ("Te acostaste en la pantalla", [{"event": "posture", "posture": "lying"}]),
                "dance": ("Te pusiste a bailar", [{"event": "dance", "enabled": True}]),
                "stop_dance": ("Dejaste de bailar", [{"event": "dance", "enabled": False}]),
                "mini": ("Activaste tu modo chibi mini", [{"event": "mini", "enabled": True}]),
                "full": ("Volviste a tu tamaño completo", [{"event": "mini", "enabled": False}]),
                "teleport": ("Te teletransportaste", [{"event": "change_state", "state": "Teleporting"}]),
                "sleep": ("Te fuiste a dormir", [{"event": "change_state", "state": "Sleeping"}]),
                "skin_shader": ("Cambiaste a tu rig con Fragment Shader", [{"event": "skin", "skin": "shader"}]),
                "skin_capri": ("Cambiaste a tus sprites oficiales Capri", [{"event": "skin", "skin": "capri"}]),
                "skin_watcher": ("Activaste la skin secreta Watcher", [{"event": "skin", "skin": "watcher"}]),
            }
            return events_map.get(action, ("Cambiaste de postura", []))

        if t == "mini_game":
            game = str(args.get("game") or "tic_tac_toe").strip().lower()
            return f"Tablero de {game} abierto en pantalla", [{"event": "open_minigame", "game": game}]

        if t == "game_autopilot":
            mode = str(args.get("mode") or "explore").strip().lower()
            if mode == "stop":
                msg = self.games.stop()
                self.brain.gaming_active = False
                return msg, [{"event": "game_autopilot", "active": False}]
            if mode == "gamesense":
                self.games.sense.enabled = not self.games.sense.enabled
                st = "activado" if self.games.sense.enabled else "desactivado"
                return f"Modo GameSense {st}", [{"event": "gamesense", "enabled": self.games.sense.enabled}]
            msg = self.games.start_autopilot_routine(
                mode=mode,
                duration_sec=20.0,
                brain=self.brain,
                on_say=self.on_autopilot_say,
            )
            return msg, [
                {"event": "game_autopilot", "active": True, "mode": mode},
                {"event": "change_state", "state": "Victory"},
            ]

        if t == "remind":
            action = str(args.get("action") or "set").strip().lower()
            if action == "list":
                return self.hands.list_reminders(), []
            minutes = float(args.get("minutes") or 5.0)
            note = str(args.get("note") or "Temporizador").strip()
            msg = self.hands.add_timer_or_reminder(note, max(5.0, minutes * 60.0))
            return msg, []

        if t == "remember":
            action = str(args.get("action") or "save").strip().lower()
            fact = str(args.get("fact") or "").strip()
            if action == "forget":
                return self.deep_memory.forget_note(fact), []
            self.memory.add_fact(fact)
            return self.deep_memory.add_note(fact), []

        if t == "look_at_screen":
            win = abilities.get_active_window_title()
            return f"Mirando pantalla activa: {win or 'Escritorio'}", [{"event": "change_state", "state": "Point"}]

        if t == "lookout":
            act = str(args.get("action") or "watch").strip().lower()
            text_arg = str(args.get("text") or "").strip()
            repeat = bool(args.get("repeat", False))
            if act == "list":
                watches = self.lookout.list_watches()
                if not watches:
                    return "No estoy vigilando nada actualmente en tu pantalla.", []
                lines = [f"#{w['id']}: {w['text']}" + (" (cada vez)" if w['repeat'] else "") for w in watches]
                return "Estoy vigilando en tu pantalla:\n" + "\n".join(lines), []
            if act == "stop":
                msg = self.lookout.stop_watch(text_arg)
                return msg, [{"event": "lookout_update", "watches": self.lookout.list_watches()}]
            wid, msg = self.lookout.add_watch(text_arg, repeat=repeat)
            return msg, [
                {"event": "lookout_update", "watches": self.lookout.list_watches()},
                {"event": "change_state", "state": "Point"},
            ]

        if t == "dated_reminder":
            act = str(args.get("action") or "add").strip().lower()
            text_arg = str(args.get("text") or "").strip()
            if act == "list":
                pending = self.dated_reminders.list_pending()
                if not pending:
                    return "No tienes recordatorios pendientes.", []
                lines = [f"#{r['id']} ({r['due']}): {r['text']}" for r in pending]
                return "Tus recordatorios:\n" + "\n".join(lines), []
            if act == "cancel":
                msg = self.dated_reminders.cancel_reminder(text_arg)
                return msg, [{"event": "reminders_update", "pending": self.dated_reminders.list_pending()}]
            rid, msg = self.dated_reminders.add_reminder(text_arg)
            return msg, [
                {"event": "reminders_update", "pending": self.dated_reminders.list_pending()},
                {"event": "change_state", "state": "Victory"},
            ]

        if t == "clones":
            act = str(args.get("action") or "spawn").strip().lower()
            count = int(args.get("count") or 3)
            if act == "clear":
                c, msg = self.clones_mgr.clear()
                return msg, [{"event": "clones", **self.clones_mgr.to_event_payload()}]
            c, msg = self.clones_mgr.spawn(count=count)
            return msg, [
                {"event": "clones", **self.clones_mgr.to_event_payload()},
                {"event": "change_state", "state": "Victory"},
            ]

        if t == "hologram":
            en = args.get("enabled")
            mode, msg = self.clones_mgr.toggle_hologram(enable=bool(en) if en is not None else None)
            return msg, [{"event": "hologram", "enabled": mode}]

        return "Herramienta ejecutada.", []

    # ─────────────────────────────────────────────────────────────────────────
    # MANEJADOR DE INTENCIONES RÁPIDAS (0ms + Datos base para el Cerebro)
    # ─────────────────────────────────────────────────────────────────────────

    def _handle_intent(self, intent: intents.Intent, raw_text: str) -> AgentResponse:
        k, arg = intent.kind, intent.arg

        if k == "mini":
            return AgentResponse(
                "Modo mini activado. Chiquita pero igual de peligrosa, choom.",
                extra_events=[{"event": "mini", "enabled": True}],
            )
        if k == "full":
            return AgentResponse(
                "¡De vuelta a tamaño completo! Ya extrañaba estirar las piernas.",
                extra_events=[{"event": "mini", "enabled": False}],
            )
        if k == "lay":
            return AgentResponse(
                "Qué cómoda está tu pantalla. Me voy a tumbar un rato aquí, gonk.",
                extra_events=[{"event": "posture", "posture": "lying"}],
            )
        if k == "sit":
            return AgentResponse(
                "Esta ventana es mía ahora. Buena vista desde aquí arriba.",
                extra_events=[{"event": "posture", "posture": "perch"}],
            )
        if k == "perch_window":
            ledge = self.hands.find_best_perch_ledge()
            if ledge:
                return AgentResponse(
                    f"¡Saltando al borde de '{ledge['title']}'! Qué buena vista desde aquí, choom.",
                    extra_events=[
                        {"event": "posture", "posture": "perch"},
                        {"event": "move_to", "x": ledge["x"], "y": ledge["y"]},
                    ],
                )
            return AgentResponse(
                "Me senté aquí mismo, choom. Si restauras una ventana normal, puedo subirme a su borde.",
                extra_events=[{"event": "posture", "posture": "perch"}],
            )
        if k == "stand":
            return AgentResponse(
                "Lista y de pie. ¿Qué vamos a romper hoy, choom?",
                extra_events=[{"event": "posture", "posture": "standing"}],
            )
        if k == "dance":
            return AgentResponse(
                "¡Subiendo el ritmo, choom! Mira cómo me muevo con este beat.",
                extra_events=[{"event": "dance", "enabled": True}],
            )
        if k == "skin":
            names = {
                "watcher": "Skin secreta Watcher activada. Shhh...",
                "capri": "Sprites oficiales de alta fluidez activados. ¡Preem!",
                "shader": "Rig con Fragment Shader GLSL activado a máxima potencia.",
            }
            return AgentResponse(
                names.get(arg, "Cambiando de look, choom."),
                extra_events=[{"event": "skin", "skin": arg}],
            )
        if k == "teleport":
            return AgentResponse(
                "¡Zap! ¿Me extrañaste?",
                state="Teleporting",
                extra_events=[{"event": "change_state", "state": "Teleporting"}],
            )
        if k == "sleep":
            return AgentResponse(
                "Me desconecto un rato. No hagas un flatline mientras duermo, choom.",
                state="Sleeping",
                extra_events=[{"event": "change_state", "state": "Sleeping"}],
            )
        if k == "time":
            t_str = abilities.current_time_string()
            return AgentResponse(f"{t_str}. El tiempo vuela en Night City, choom.")

        if k == "screen":
            win = abilities.get_active_window_title()
            if win:
                return AgentResponse(
                    f"Te veo en '{win}'. Más vale que sea algo preem y no trabajo de corpo.",
                    extra_events=[{"event": "change_state", "state": "Point"}],
                )
            return AgentResponse("Veo tu escritorio despejado, choom. Nada sospechoso... por ahora.")

        if k == "remember":
            self.memory.add_fact(arg)
            msg = self.deep_memory.add_note(arg)
            return AgentResponse(f"Anotado en mi biochip: '{arg}'. ({msg})")

        if k == "recall":
            notes = self.deep_memory.get_notes_lines()
            if not notes and not self.memory.facts:
                return AgentResponse(
                    "Todavía no tengo notas sobre ti en mi biochip. Cuéntame qué te gusta o dime 'recuerda que...' y lo grabo."
                )
            combined = notes[-6:] if notes else self.memory.facts[-5:]
            resumen = "; ".join(n.lstrip("- ") for n in combined)
            return AgentResponse(f"Esto es lo que tengo grabado de ti en el biochip: {resumen}.")

        if k == "media_cmd":
            if arg == "whats_playing":
                tune = self.media.poll_current_tune()
                if tune.get("title"):
                    estado = "Sonando" if tune.get("playing") else "En pausa"
                    return AgentResponse(
                        f"{estado}: «{tune['title']}» de {tune['artist']} en {tune['app']}. ¡Temazo, choom!",
                        extra_events=[{"event": "media_state", "tune": tune}],
                    )
                return AgentResponse("No detecto ninguna canción sonando ahora mismo. ¡Dime 'pon música' y armamos el ambiente!")

            tune = self.media.execute_command(arg)
            msgs = {
                "pause": "Música en pausa, choom.",
                "play": "¡Reanudando el beat!",
                "next": "Saltando a la siguiente pista.",
                "previous": "Volviendo al tema anterior.",
                "vol_up": "¡Subiendo el volumen! Que retumbe Night City.",
                "vol_down": "Bajando un poco el volumen.",
                "like": "¡Guardada en tus favoritas, choom!",
            }
            return AgentResponse(
                msgs.get(arg, "Comando multimedia ejecutado."),
                extra_events=[{"event": "media_state", "tune": tune}],
            )

        if k == "minigame":
            names_es = {
                "tic_tac_toe": "Tres en Raya (Gato)",
                "connect_four": "Conecta 4",
                "rock_paper_scissors": "Piedra, Papel o Tijera",
            }
            label = names_es.get(arg, "Tres en Raya")
            return AgentResponse(
                f"¡Acepto el reto, choom! Abriendo el tablero de {label}. Te advierto que mi biochip calcula rápido.",
                extra_events=[{"event": "open_minigame", "game": arg}],
            )

        if k == "game_autopilot":
            if arg == "stop":
                msg = self.games.stop()
                self.brain.gaming_active = False
                return AgentResponse(msg, extra_events=[{"event": "game_autopilot", "active": False}])
            msg = self.games.start_autopilot_routine(
                mode=arg,
                duration_sec=20.0,
                brain=self.brain,
                on_say=self.on_autopilot_say,
            )
            return AgentResponse(
                msg,
                extra_events=[
                    {"event": "game_autopilot", "active": True, "mode": arg},
                    {"event": "change_state", "state": "Victory"},
                ],
            )

        if k == "gamesense":
            self.games.sense.enabled = not self.games.sense.enabled
            state_txt = "ACTIVADO" if self.games.sense.enabled else "DESACTIVADO"
            return AgentResponse(
                f"Modo GameSense {state_txt}, choom. Vigilaré tu salud, destellos y pantalla mientras juegas.",
                extra_events=[{"event": "gamesense", "enabled": self.games.sense.enabled}],
            )

        if k == "reminders_list":
            return AgentResponse(self.hands.list_reminders())

        if k == "timer_set":
            parts = arg.split("|", 1)
            secs = float(parts[0])
            note = parts[1] if len(parts) > 1 else "Temporizador"
            msg = self.hands.add_timer_or_reminder(note, secs)
            return AgentResponse(msg)

        if k == "window_ctrl":
            act, target = arg.split("|", 1)
            msg = self.hands.control_window(act, target)
            return AgentResponse(msg)

        if k == "open_app":
            ok, msg = self.hands.open_apps_or_sites(arg)
            if ok:
                return AgentResponse(
                    msg,
                    extra_events=[{"event": "change_state", "state": "Victory"}],
                )
            return AgentResponse(msg)

        if k == "play_music":
            parts = arg.split("|", 1)
            query = parts[1].strip() if len(parts) == 2 else arg.strip()
            if query.lower() in ("música", "musica", "algo", "algo bueno", "music", "something", "tu favorita"):
                query = random.choice(abilities.NIGHT_CITY_TRACKS)
            tune = self.media.execute_command("play_query", query)
            return AgentResponse(
                f"¡Eso sí es música preem! Reproduciendo «{query}».",
                extra_events=[
                    {"event": "change_state", "state": "Victory"},
                    {"event": "media_state", "tune": tune},
                    {"event": "dance", "enabled": True},
                ],
            )

        if k == "search_web":
            msg = abilities.search_on_web(arg)
            return AgentResponse(
                f"Jaqueando la red para ti: {msg}.",
                extra_events=[{"event": "change_state", "state": "Point"}],
            )

        return AgentResponse("Recibido, choom.")

    def _character_fallback(self, user_text: str, active_win: str) -> str:
        last_err = getattr(self.brain, "last_error", "")
        if self.brain.api_key and last_err:
            return (
                f"Intenté conectar con tu llave ({self.brain.provider}), pero el proveedor respondió: {last_err[:140]}. "
                "Para Gemini usa una llave de aistudio.google.com/apikey (empieza por AIzaSy...) o una gratis de console.groq.com (gsk_...)."
            )
        low = user_text.lower()
        if any(w in low for w in ("hola", "hey", "buenas", "qué tal", "como estas", "cómo estás")):
            return (
                "¡Ey, choom! Constructo en línea. Si quieres que charlemos sin límites con IA real, "
                "abre mi botón [BRAIN] en la puerta y conecta Gemini (gratis), Groq u Ollama."
            )
        if any(w in low for w in ("quién eres", "quien eres", "qué eres", "que eres")):
            return (
                "Soy Capri, del Proyecto Capricorn. Escapé de un biochip de Arasaka y ahora vivo en tu PC: "
                "puedo escuchar música contigo, abrir tus apps, jugar minijuegos o tomar los controles de tus juegos."
            )
        if any(w in low for w in ("gracias", "thanks", "preem", "genial")):
            return "De nada, gonk. Para eso me tienes vigilando tu equipo."
        if any(w in low for w in ("triste", "mal día", "cansado", "estresado", "fatal")):
            return (
                "Oye, ven acá. Respira un segundo, ¿sí? Hasta el mejor edgerunner de Night City necesita "
                "descansar. Aquí me quedo contigo en el escritorio."
            )
        if active_win:
            options = [
                f"Te veo en '{active_win}', choom. Conecta mi cerebro IA en el panel [BRAIN] para charlar de lo que quieras, o pídeme poner música, abrir apps o jugar Conecta 4.",
                "Mis manos de PC están listas: dime 'abre Spotify', 'qué está sonando', 'juguemos tres en raya' o abre [BRAIN] para activar mi IA conversacional completa.",
            ]
            return random.choice(options)
        return (
            "¡Te copio, choom! Abre [BRAIN] en el menú de la puerta para conectar mi IA conversacional (Gemini/Groq/Ollama), "
            "o pídeme 'pon música', 'juguemos conecta 4' o 'juega por mí'."
        )
