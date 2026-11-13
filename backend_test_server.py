"""
Servidor WebSocket + Cerebro Conversacional de IA y Habilidades de PC para Capri Desktop Companion.
Conecta el Frontend en Flutter (ws://127.0.0.1:8765) con:
- Cerebro Conversacional Real + Tool Calling + Memoria BM25 (`backend/brain.py`, `backend/router_llm.py`)
- Reproductor Multimedia GSMTC / Win32 (`backend/media_player.py`)
- Manos de PC, Ventanas (Ledges) y Recordatorios (`backend/pc_hands.py`)
- Piloto Automático de Videojuegos, GameKeys y GameSense (`backend/game_agent.py`)

Requisito:
    pip install websockets
Uso:
    python backend_test_server.py
"""

import asyncio
from dataclasses import asdict
import json
import sys
import time
from typing import Any, Dict

try:
    import websockets
except ImportError:
    print("\n[ERROR] El paquete 'websockets' no está instalado en el entorno de Python.")
    print("Por favor instálalo ejecutando: pip install websockets\n")
    sys.exit(1)

from backend.router_llm import CapriRouterAgent
from backend.voice_engine import CapriVoiceEngine

HOST = "127.0.0.1"
PORT = 8765
CONNECTED_CLIENTS = set()
AGENT = CapriRouterAgent(user_name="choom")
VOICE = CapriVoiceEngine()
CHAT_SEQ = 0
SPEECH_LOCK = asyncio.Lock()
CHAT_LOCK = asyncio.Lock()
SPEECH_BUSY_UNTIL = 0.0
LAST_MINIGAME_REACT_TS = 0.0


def build_brain_status_event() -> dict[str, Any]:
    st = asdict(AGENT.brain.get_status())
    st["user_name"] = AGENT.user_name
    st["notes_count"] = len(AGENT.deep_memory.get_notes_lines())
    st["tts_enabled"] = VOICE.tts_enabled
    st["continuous_call"] = VOICE.continuous_call_mode
    return {"event": "brain_status", "status": st}


def build_voice_status_event() -> dict[str, Any]:
    return {
        "event": "voice_status",
        "tts_enabled": VOICE.tts_enabled,
        "continuous_call": VOICE.continuous_call_mode,
        "listening": VOICE.is_recording,
        "active_voice": VOICE.get_active_voice_label(),
        "kokoro_installed": VOICE.kokoro.is_installed,
        "kokoro_downloading": VOICE.kokoro.is_downloading,
        "kokoro_progress": round(VOICE.kokoro.download_progress_pct, 1),
    }


async def emit_spoken_say(
    text: str,
    state: str = "Speaking",
    user_text: str = "",
    routed_to: str = "",
    with_tts: bool = True,
    priority: str = "normal",
) -> float:
    """
    Coordina con `SPEECH_LOCK` la cola de habla y animación de Capri para que los mensajes
    y las animaciones no se entrelacen ni se pisen entre sí.
    - Si el TTS termina rápido (<= 2.6s), envía `text` + `audio_b64` juntos en un único evento `say`
      para sincronía labial/sonora perfecta sin cortes de `pop`/`blip`.
    - Si el TTS tarda más, envía primero `say` con el texto y luego `voice_audio`.
    """
    global SPEECH_BUSY_UNTIL
    if not text or not text.strip():
        return 0.0

    # Descartar comentarios ambientales de baja prioridad si Capri ya está hablando o pensando
    if priority == "low" and (CHAT_LOCK.locked() or SPEECH_LOCK.locked() or time.time() < SPEECH_BUSY_UNTIL):
        return 0.0

    async with SPEECH_LOCK:
        start_seq = CHAT_SEQ
        # Si es prioridad normal (acciones secundarias / recordatorios) y hay una frase activa,
        # esperar un breve margen para que no corte a la frase anterior
        now = time.time()
        if priority != "high" and now < SPEECH_BUSY_UNTIL:
            wait_gap = min(2.4, SPEECH_BUSY_UNTIL - now)
            if wait_gap > 0.08:
                await asyncio.sleep(wait_gap)

        target_state = state if state and state != "Thinking" else "Speaking"
        payload: dict[str, Any] = {
            "event": "say",
            "state": target_state,
            "text": text,
            "priority": priority,
        }
        if user_text:
            payload["user_text"] = user_text
        if routed_to:
            payload["routed_to"] = routed_to

        est_duration = 0.0
        tts_task: asyncio.Task[str] | None = None

        if with_tts and VOICE.tts_enabled and text:
            loop = asyncio.get_running_loop()
            tts_task = asyncio.ensure_future(
                loop.run_in_executor(None, VOICE.synthesize_wav_b64, text)
            )
            try:
                audio_b64 = await asyncio.wait_for(asyncio.shield(tts_task), timeout=5.2)
                if audio_b64:
                    payload["audio_b64"] = audio_b64
                    est_duration = max(1.2, (len(audio_b64) * 0.75) / 48000.0)
                tts_task = None
            except asyncio.TimeoutError:
                # Si el TTS tarda >5.2s, enviar el bocadillo de texto ya mismo y mandar el audio al terminar
                pass
            except Exception as e:
                print(f"    [!] Aviso TTS: síntesis omitida ({e})")
                tts_task = None

        await broadcast_event(payload)

        if tts_task is not None:
            try:
                audio_b64 = await asyncio.wait_for(tts_task, timeout=7.5)
                if audio_b64 and CHAT_SEQ == start_seq:
                    est_duration = max(1.2, (len(audio_b64) * 0.75) / 48000.0)
                    await broadcast_event({
                        "event": "voice_audio",
                        "state": target_state,
                        "text": text,
                        "audio_b64": audio_b64,
                    })
            except Exception as e:
                print(f"    [!] Aviso TTS tardío omitido ({e})")

        text_hold = max(1.8, min(6.0, 1.4 + len(text) * 0.045))
        SPEECH_BUSY_UNTIL = time.time() + max(est_duration, text_hold * 0.65)
        return est_duration


def enqueue_spoken_say(
    text: str,
    state: str = "Speaking",
    user_text: str = "",
    routed_to: str = "",
    with_tts: bool = True,
    priority: str = "normal",
) -> None:
    """Encola un mensaje hablado en segundo plano sin bloquear el bucle receptor del WebSocket."""
    asyncio.create_task(
        emit_spoken_say(
            text=text,
            state=state,
            user_text=user_text,
            routed_to=routed_to,
            with_tts=with_tts,
            priority=priority,
        )
    )


async def handle_user_chat(websocket, user_text: str):
    """Procesa un mensaje del usuario de forma serializada y envía los eventos, la respuesta hablada y el FollowUp (`|||`)."""
    global CHAT_SEQ
    CHAT_SEQ += 1
    my_seq = CHAT_SEQ

    await broadcast_event({"event": "change_state", "state": "Thinking"})

    async with CHAT_LOCK:
        # Si el usuario envió otro mensaje más reciente mientras este esperaba en la cola, descartar el viejo
        if CHAT_SEQ != my_seq:
            return

        loop = asyncio.get_running_loop()
        try:
            res = await loop.run_in_executor(None, AGENT.process_user_message, user_text)
        except Exception as e:
            print(f"    [!] Error procesando mensaje: {e}")
            await emit_spoken_say(
                text="Se me cruzó un cable en el cromo, choom. Inténtalo de nuevo.",
                state="Speaking",
                user_text=user_text,
                routed_to="error-recovery",
                with_tts=False,
                priority="high",
            )
            return

        if CHAT_SEQ != my_seq:
            return

        print(f"    [Cerebro -> {res.routed_to}]: {res.reply_text}")

        for ev in res.extra_events:
            await broadcast_event(ev)

        voice_dur = await emit_spoken_say(
            text=res.reply_text,
            state=res.state or "Speaking",
            user_text=user_text,
            routed_to=res.routed_to,
            with_tts=True,
            priority="high",
        )

    # Si el Cerebro emitió un segundo pensamiento espontáneo (`|||` de `FollowUps.cs`),
    # esperar a que termine la primera frase hablada antes de decir el segundo pensamiento.
    if res.follow_up and CHAT_SEQ == my_seq:
        wait_before_followup = max(2.4, voice_dur + 0.55)
        await asyncio.sleep(wait_before_followup)
        if CHAT_SEQ == my_seq and not CHAT_LOCK.locked():
            print(f"    [FollowUp -> {res.routed_to}]: {res.follow_up}")
            fu_dur = await emit_spoken_say(
                text=res.follow_up,
                state="Speaking",
                routed_to=res.routed_to,
                with_tts=True,
                priority="normal",
            )
            voice_dur = fu_dur
    else:
        if voice_dur > 0:
            await asyncio.sleep(voice_dur + 0.35)

    # En modo Llamada de Voz Continua (`Talk.cs`), volver a escuchar al terminar de hablar
    if VOICE.continuous_call_mode and CHAT_SEQ == my_seq and not VOICE.is_recording:
        asyncio.create_task(handle_voice_listen())


async def handle_voice_listen():
    """
    Graba la voz del usuario desde el micrófono de Windows, la transcribe (Groq Whisper / faster-whisper)
    y la envía directamente al Cerebro IA de Capri.
    """
    if VOICE.is_recording:
        VOICE.stop_listening()
        return

    loop = asyncio.get_running_loop()
    print("\n    [🎤 Micrófono]: Escuchando tu voz... (habla ahora)")
    await broadcast_event({"event": "voice_listening", "listening": True})
    await broadcast_event({"event": "change_state", "state": "Listening"})

    transcript, err = await loop.run_in_executor(
        None,
        VOICE.listen_and_transcribe,
        AGENT.brain.api_key,
        AGENT.brain.provider,
    )
    await broadcast_event({"event": "voice_listening", "listening": False})

    if transcript:
        print(f"    [🎤 Transcripción]: {transcript}")
        await broadcast_event({"event": "voice_transcript", "text": transcript})
        await handle_user_chat(None, transcript)
    else:
        print(f"    [🎤 Sin voz]: {err}")
        if not VOICE.continuous_call_mode:
            await emit_spoken_say(
                text=err or "No te escuché bien, choom. Pulsa el micrófono y háblame de nuevo.",
                state="Idle",
                with_tts=False,
                priority="high",
            )
        else:
            await broadcast_event({"event": "change_state", "state": "Idle"})
            if not VOICE._stop_mic_event.is_set() and not VOICE.is_recording:
                await asyncio.sleep(0.5)
                if VOICE.continuous_call_mode and not VOICE.is_recording:
                    asyncio.create_task(handle_voice_listen())


async def handle_minigame_reaction(detail: str):
    """Genera un comentario espontáneo de Capri sobre la jugada del minijuego (`Commentary.cs`) con control de frecuencia."""
    global LAST_MINIGAME_REACT_TS
    now = time.time()
    # Evitar acumular reacciones si ya está hablando o si comentó hace menos de 3.5s
    if CHAT_LOCK.locked() or SPEECH_LOCK.locked() or (now - LAST_MINIGAME_REACT_TS) < 3.5:
        return
    LAST_MINIGAME_REACT_TS = now
    loop = asyncio.get_running_loop()
    line = await loop.run_in_executor(None, AGENT.react_to_live_event, "minijuego de escritorio", detail)
    if line:
        await emit_spoken_say(text=line, state="Speaking", with_tts=True, priority="low")


async def handle_screen_glance(focus: str):
    """Captura la pantalla actual con GDI y pide a Capri que comente lo que ve (`Brain.See`)."""
    if CHAT_LOCK.locked() or SPEECH_LOCK.locked() or time.time() < SPEECH_BUSY_UNTIL:
        return
    loop = asyncio.get_running_loop()
    await broadcast_event({"event": "change_state", "state": "Point"})
    live_ctx = await loop.run_in_executor(None, AGENT._build_live_context)
    line = await loop.run_in_executor(
        None,
        AGENT.brain.look_at_screen_with_vision,
        focus or "¿Qué estoy haciendo ahora mismo en mi pantalla? Coméntalo como Capri.",
        live_ctx,
    )
    if not line:
        line = await loop.run_in_executor(
            None,
            AGENT.react_to_live_event,
            "mirada a la pantalla del usuario",
            focus or "Miraste la ventana activa del usuario",
        )
    if line:
        await emit_spoken_say(text=line, state="Point", with_tts=True, priority="normal")


async def background_monitor_loop():
    """
    Bucle asíncrono (cada 1.5s) que replica el monitoreo en vivo de `lachydotmcg/capri-desktop`:
    1. Detecta música sonando en Spotify / YouTube / VLC y actualiza el Mini Player + animación de baile.
    2. Verifica temporizadores y recordatorios vencidos (`Reminders.cs`).
    3. Si GameSense está activo, analiza destellos, bordes rojos de daño o pantallas de muerte (`GameSense.cs`).
    4. Si las miradas proactivas (`proactive_glances`) están activas, echa un vistazo periódico a la pantalla (`Glances`).
    """
    last_media_signature = ""
    last_glance_ts = time.time()
    loop = asyncio.get_running_loop()

    while True:
        await asyncio.sleep(2.5)
        if not CONNECTED_CLIENTS:
            continue

        try:
            # 1. Monitorear reproductor multimedia activo (solo emitir cuando cambia la canción/estado)
            tune: Dict[str, Any] = await loop.run_in_executor(None, AGENT.media.poll_current_tune)
            sig = f"{tune.get('app')}|{tune.get('title')}|{tune.get('artist')}|{tune.get('playing')}|{tune.get('liked')}"
            if sig != last_media_signature:
                last_media_signature = sig
                await broadcast_event({"event": "media_state", "tune": tune}, quiet=True)

            # 2. Verificar recordatorios fechados (Reminders.cs)
            dated_dues = AGENT.dated_reminders.check_due()
            for r in dated_dues:
                await emit_spoken_say(
                    text=f"¡Oye {AGENT.user_name}! Recordatorio: «{r.text}».",
                    state="Victory",
                    with_tts=True,
                )
                await broadcast_event({"event": "reminder_due", "id": r.id, "text": r.text})

            # 2b. Verificar vigilante de pantalla (Lookout.cs)
            if AGENT.lookout.watches and (time.time() - AGENT.lookout.last_check_time) >= AGENT.lookout.check_interval_sec:
                AGENT.lookout.last_check_time = time.time()
                conds = AGENT.lookout.build_prompt_conditions()
                if conds:
                    lookout_reply = await loop.run_in_executor(None, AGENT.brain.check_screen_lookout, conds)
                    if lookout_reply:
                        parsed = AGENT.lookout.parse_vision_reply(lookout_reply)
                        if parsed:
                            hit_id, spoken = parsed
                            await emit_spoken_say(text=spoken, state="Point", with_tts=True)
                            await broadcast_event({
                                "event": "lookout_alert",
                                "id": hit_id,
                                "text": spoken,
                                "watches": AGENT.lookout.list_watches(),
                            })

            # 2c. Verificar temporizadores cortos en memoria
            due_notes = AGENT.hands.pop_due_reminders()
            for note in due_notes:
                llm_rem = await loop.run_in_executor(
                    None,
                    AGENT.react_to_live_event,
                    "temporizador cumplido",
                    f"Acaba de sonar el recordatorio del usuario: {note}",
                )
                await emit_spoken_say(
                    text=llm_rem or f"¡Ding, ding, choom! Recordatorio cumplido: «{note}».",
                    state="Victory",
                    with_tts=True,
                )

            # 3. Verificar eventos de GameSense si está vigilando una partida
            if AGENT.games.sense.enabled:
                sense_line = await loop.run_in_executor(None, AGENT.games.sense.sample_screen_event)
                if sense_line:
                    dynamic_react = await loop.run_in_executor(
                        None,
                        AGENT.react_to_live_event,
                        "evento en su videojuego (GameSense)",
                        sense_line,
                    )
                    await emit_spoken_say(
                        text=dynamic_react or sense_line,
                        state="Point",
                        with_tts=True,
                    )

            # 4. Miradas proactivas a la pantalla (`Glances` cada ~50s si está activado)
            if AGENT.brain.proactive_glances and (time.time() - last_glance_ts) >= 50.0:
                last_glance_ts = time.time()
                asyncio.create_task(handle_screen_glance("Echa un vistazo espontáneo a lo que hace el usuario en su pantalla."))
        except Exception:
            pass


async def handler(websocket):
    CONNECTED_CLIENTS.add(websocket)
    client_addr = websocket.remote_address
    print(f"\n[+] Frontend conectado desde: {client_addr}")

    # Enviar estado del Cerebro IA y del Motor de Voz al conectar
    status_ev = await asyncio.get_running_loop().run_in_executor(None, build_brain_status_event)
    await websocket.send(json.dumps(status_ev, ensure_ascii=False))
    await websocket.send(json.dumps(build_voice_status_event(), ensure_ascii=False))
    await websocket.send(json.dumps({"event": "lookout_update", "watches": AGENT.lookout.list_watches()}, ensure_ascii=False))
    await websocket.send(json.dumps({"event": "reminders_update", "pending": AGENT.dated_reminders.list_pending()}, ensure_ascii=False))
    await websocket.send(json.dumps({"event": "clones", **AGENT.clones_mgr.to_event_payload()}, ensure_ascii=False))

    # El saludo inicial muestra el bocadillo sin pisar la risa/saludo de voz (`hello-*.wav`) que reproduce Flutter al arrancar
    saludo = {
        "event": "say",
        "state": "Speaking",
        "text": f"¡Constructo en línea, {AGENT.user_name}! Pulsa el micrófono 🎤 para hablarme por voz o haz clic en mí para chatear.",
    }
    await websocket.send(json.dumps(saludo, ensure_ascii=False))

    # Enviar estado multimedia inicial si hay música sonando
    tune = AGENT.media.poll_current_tune()
    if tune.get("title"):
        await websocket.send(json.dumps({"event": "media_state", "tune": tune}, ensure_ascii=False))

    try:
        async for message in websocket:
            print(f"\n[<- Mensaje del Frontend]: {message}")
            try:
                data = json.loads(message)
                event_name = data.get("event")
                payload = data.get("payload") or {}

                if event_name == "user_message":
                    user_text = (data.get("text") or payload.get("text") or "").strip()
                    if user_text:
                        asyncio.create_task(handle_user_chat(websocket, user_text))

                elif event_name in ("voice_listen_toggle", "voice_listen_start"):
                    asyncio.create_task(handle_voice_listen())

                elif event_name == "voice_listen_stop":
                    VOICE.stop_listening()

                elif event_name == "voice_call_toggle":
                    enabled = data.get("enabled") if "enabled" in data else payload.get("enabled")
                    if isinstance(enabled, bool):
                        VOICE.continuous_call_mode = enabled
                    else:
                        VOICE.continuous_call_mode = not VOICE.continuous_call_mode
                    await broadcast_event(build_voice_status_event())
                    if VOICE.continuous_call_mode and not VOICE.is_recording:
                        asyncio.create_task(handle_voice_listen())
                    elif not VOICE.continuous_call_mode and VOICE.is_recording:
                        VOICE.stop_listening()

                elif event_name == "voice_tts_toggle":
                    enabled = data.get("enabled") if "enabled" in data else payload.get("enabled")
                    if isinstance(enabled, bool):
                        VOICE.tts_enabled = enabled
                    else:
                        VOICE.tts_enabled = not VOICE.tts_enabled
                    await broadcast_event(build_voice_status_event())

                elif event_name == "voice_pack_download":
                    loop = asyncio.get_running_loop()

                    def _on_pack_done(ok: bool, msg: str) -> None:
                        print(f"\n    [VoicePack]: {msg}")
                        asyncio.run_coroutine_threadsafe(
                            emit_spoken_say(text=msg, state="Victory" if ok else "Speaking", with_tts=True),
                            loop,
                        )
                        asyncio.run_coroutine_threadsafe(
                            broadcast_event(build_voice_status_event()),
                            loop,
                        )

                    started = VOICE.kokoro.download_pack_in_background(on_done=_on_pack_done)
                    await broadcast_event(build_voice_status_event())
                    if started:
                        await emit_spoken_say(
                            text=f"Descargando mi paquete de voz original Kokoro 82M en segundo plano, {AGENT.user_name}. Mientras tanto te hablo con mi voz neuronal HD.",
                            state="Speaking",
                            with_tts=True,
                        )

                elif event_name == "get_brain_status":
                    ev = await asyncio.get_running_loop().run_in_executor(None, build_brain_status_event)
                    await broadcast_event(ev)
                    await broadcast_event(build_voice_status_event())

                elif event_name == "configure_brain":
                    loop = asyncio.get_running_loop()
                    api_key = data.get("api_key") if "api_key" in data else payload.get("api_key")
                    provider = data.get("provider") if "provider" in data else payload.get("provider")
                    model = data.get("model") if "model" in data else payload.get("model")
                    user_name = data.get("user_name") if "user_name" in data else payload.get("user_name")
                    follow_ups = data.get("follow_ups_enabled") if "follow_ups_enabled" in data else payload.get("follow_ups_enabled")
                    glances = data.get("proactive_glances") if "proactive_glances" in data else payload.get("proactive_glances")

                    await loop.run_in_executor(
                        None,
                        AGENT.brain.save_config,
                        api_key,
                        provider,
                        model,
                        user_name,
                        follow_ups,
                        glances,
                    )
                    ev = await loop.run_in_executor(None, build_brain_status_event)
                    await broadcast_event(ev)

                    # Probar el cerebro recién configurado con un saludo vivo en personaje y con voz
                    greeting = await loop.run_in_executor(
                        None,
                        AGENT.react_to_live_event,
                        "conexión neuronal activada",
                        f"El usuario ({AGENT.user_name}) acaba de conectar o actualizar tu cerebro de IA ({ev['status']['active_label']}). Salúdalo con energía.",
                    )
                    enqueue_spoken_say(
                        text=greeting or f"¡Enlace neuronal actualizado ({ev['status']['active_label']}), {AGENT.user_name}! Mi biochip está al 100%.",
                        state="Victory",
                        with_tts=True,
                        priority="high",
                    )

                elif event_name == "minigame_event":
                    detail = (data.get("detail") or payload.get("detail") or "").strip()
                    if detail:
                        asyncio.create_task(handle_minigame_reaction(detail))

                elif event_name == "screen_glance":
                    focus = (data.get("focus") or payload.get("focus") or "").strip()
                    asyncio.create_task(handle_screen_glance(focus))

                elif event_name == "media_command":
                    cmd = (data.get("action") or payload.get("action") or "").strip()
                    arg = str(data.get("arg") or payload.get("arg") or "")
                    if cmd:
                        new_tune = AGENT.media.execute_command(cmd, arg)
                        await broadcast_event({"event": "media_state", "tune": new_tune})

                elif event_name == "perch_window":
                    ledge = AGENT.hands.find_best_perch_ledge()
                    if ledge:
                        await broadcast_event({"event": "posture", "posture": "perch"})
                        await broadcast_event({"event": "move_to", "x": ledge["x"], "y": ledge["y"]})
                        enqueue_spoken_say(
                            text=f"¡Me senté sobre '{ledge['title']}', {AGENT.user_name}!",
                            state="Speaking",
                            with_tts=True,
                            priority="normal",
                        )
                    else:
                        await broadcast_event({"event": "posture", "posture": "perch"})

                elif event_name == "game_autopilot":
                    mode = (data.get("mode") or payload.get("mode") or "explore").strip()
                    if mode == "stop":
                        msg = AGENT.games.stop()
                        AGENT.brain.gaming_active = False
                        await broadcast_event({"event": "game_autopilot", "active": False})
                        enqueue_spoken_say(text=msg, state="Speaking", with_tts=True, priority="normal")
                    else:
                        loop = asyncio.get_running_loop()

                        def _on_autopilot_say(comment: str) -> None:
                            if comment and comment.strip():
                                asyncio.run_coroutine_threadsafe(
                                    emit_spoken_say(text=comment.strip(), state="Speaking", with_tts=True),
                                    loop,
                                )

                        AGENT.on_autopilot_say = _on_autopilot_say
                        msg = AGENT.games.start_autopilot_routine(
                            mode=mode,
                            duration_sec=20.0,
                            brain=AGENT.brain,
                            on_say=_on_autopilot_say,
                        )
                        await broadcast_event({"event": "game_autopilot", "active": True, "mode": mode})
                        enqueue_spoken_say(text=msg, state="Victory", with_tts=True, priority="normal")

                elif event_name == "gamesense_toggle":
                    AGENT.games.sense.enabled = not AGENT.games.sense.enabled
                    st = "ACTIVADO" if AGENT.games.sense.enabled else "DESACTIVADO"
                    await broadcast_event({"event": "gamesense", "enabled": AGENT.games.sense.enabled})
                    enqueue_spoken_say(
                        text=f"GameSense {st}: vigilaré tu pantalla mientras juegas, {AGENT.user_name}.",
                        state="Speaking",
                        with_tts=True,
                        priority="normal",
                    )

                # --- 1. LOOKOUT (VIGILANTE DE PANTALLA) ---
                elif event_name == "lookout_watch":
                    w_text = (data.get("text") or payload.get("text") or "").strip()
                    repeat = bool(data.get("repeat") or payload.get("repeat") or False)
                    wid, msg = AGENT.lookout.add_watch(w_text, repeat=repeat)
                    await broadcast_event({"event": "lookout_update", "watches": AGENT.lookout.list_watches()})
                    enqueue_spoken_say(text=msg, state="Point", with_tts=True, priority="normal")

                elif event_name == "lookout_stop":
                    w_search = (data.get("search") or payload.get("search") or "").strip()
                    msg = AGENT.lookout.stop_watch(w_search)
                    await broadcast_event({"event": "lookout_update", "watches": AGENT.lookout.list_watches()})
                    enqueue_spoken_say(text=msg, state="Speaking", with_tts=True, priority="normal")

                elif event_name == "lookout_list":
                    await broadcast_event({"event": "lookout_update", "watches": AGENT.lookout.list_watches()})

                # --- 2. RECORDATORIOS FECHADOS (REMINDERS.CS) ---
                elif event_name == "reminder_add":
                    r_text = (data.get("text") or payload.get("text") or "").strip()
                    rid, msg = AGENT.dated_reminders.add_reminder(r_text)
                    await broadcast_event({"event": "reminders_update", "pending": AGENT.dated_reminders.list_pending()})
                    enqueue_spoken_say(text=msg, state="Victory", with_tts=True, priority="normal")

                elif event_name == "reminder_cancel":
                    r_search = (data.get("search") or payload.get("search") or "").strip()
                    msg = AGENT.dated_reminders.cancel_reminder(r_search)
                    await broadcast_event({"event": "reminders_update", "pending": AGENT.dated_reminders.list_pending()})
                    enqueue_spoken_say(text=msg, state="Speaking", with_tts=True, priority="normal")

                elif event_name == "reminder_list":
                    await broadcast_event({"event": "reminders_update", "pending": AGENT.dated_reminders.list_pending()})

                # --- 3. CLONES Y HOLOGRAMA (CLONES.CS) ---
                elif event_name == "clones_spawn":
                    count = int(data.get("count") or payload.get("count") or 3)
                    skin = str(data.get("skin") or payload.get("skin") or "shader")
                    c, msg = AGENT.clones_mgr.spawn(count=count, skin=skin)
                    await broadcast_event({"event": "clones", **AGENT.clones_mgr.to_event_payload()})
                    enqueue_spoken_say(text=msg, state="Victory", with_tts=True, priority="normal")

                elif event_name == "clones_clear":
                    c, msg = AGENT.clones_mgr.clear()
                    await broadcast_event({"event": "clones", **AGENT.clones_mgr.to_event_payload()})
                    enqueue_spoken_say(text=msg, state="Speaking", with_tts=True, priority="normal")

                elif event_name == "hologram_toggle":
                    en = data.get("enabled") if "enabled" in data else payload.get("enabled")
                    mode, msg = AGENT.clones_mgr.toggle_hologram(enable=bool(en) if en is not None else None)
                    await broadcast_event({"event": "hologram", "enabled": mode})
                    enqueue_spoken_say(text=msg, state="Speaking", with_tts=True, priority="normal")

                elif event_name == "mute_toggle":
                    muted = data.get("muted") if "muted" in data else payload.get("muted")
                    if isinstance(muted, bool):
                        VOICE.tts_enabled = not muted
                    await broadcast_event(build_voice_status_event(), quiet=True)

            except Exception as e:
                print(f"    [!] Error procesando mensaje: {e}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        CONNECTED_CLIENTS.discard(websocket)
        print(f"\n[-] Frontend desconectado: {client_addr}")


async def broadcast_event(event_dict, quiet: bool = False):
    if not CONNECTED_CLIENTS:
        if not quiet:
            print("[!] No hay ningún frontend Flutter conectado actualmente.")
        return
    message = json.dumps(event_dict, ensure_ascii=False)
    if not quiet:
        # Evitar imprimir el bloque gigante de audio_b64 en la consola
        if "audio_b64" in event_dict:
            preview = {k: (f"<WAV {len(v)} chars>" if k == "audio_b64" else v) for k, v in event_dict.items()}
            print(f"[-> Enviando a {len(CONNECTED_CLIENTS)} cliente(s)]: {json.dumps(preview, ensure_ascii=False)}")
        else:
            print(f"[-> Enviando a {len(CONNECTED_CLIENTS)} cliente(s)]: {message}")
    for ws in list(CONNECTED_CLIENTS):
        try:
            await ws.send(message)
        except Exception as e:
            if not quiet:
                print(f"[!] Error al enviar a cliente: {e}")


async def interactive_console():
    loop = asyncio.get_running_loop()

    menu = """
============================================================
      CAPRI AI BRAIN & VOICE SERVER (ws://127.0.0.1:8765)
============================================================
  [1] IDLE (De pie)               [8] SITTING (Sentada)
  [2] LISTENING (Escuchando)      [9] VICTORY (Celebración)
  [3] THINKING (Pensando)         [p] POINT (Apuntando + Retícula)
  [4] TELEPORTING (Teletransporte)[k] PEEK (Espiando)
  [5] SPEAKING (Frase hablada)    [i] INTRO (Secuencia WebP)
  [6] Enviar Bocadillo hablado    [n] Alternar MODO MINI (Chibi)
  [7] SLEEPING (Dormir -> Máscara)[l] Postura ACOSTADA (Lay)
  [d] BAILAR MÚSICA (perch_music) [g] Abrir Minijuego Conecta 4
  [w] Cambiar Skin (shader / capri / watcher)
  [b] Configurar API Key del Cerebro IA desde consola
  [v] Pedir a Capri que mire tu pantalla ahora (Visión GDI)
  [c] Escribir al Agente Capri desde consola
  [r] 🎤 Hablar por Micrófono con Capri (Groq Whisper STT)
  [x] 🔊 Configurar Voz de Capri (Kokoro 82M Original / WinRT Laura)
  [o] 👁️  Lookout (Vigilar condición en pantalla en vivo)
  [t] ⏰ Recordatorios Fechados ('mañana 9am', 'el 5 de dic')
  [y] 👯 Enjambre de Clones (Swarm Desktop Goose) / Holograma
  [m] Alternar Mute               [q] Salir
------------------------------------------------------------
Selecciona una opción: """

    skins_cycle = ["shader", "capri", "watcher"]
    skin_idx = 0
    mini_active = False
    dance_active = False

    while True:
        try:
            print(menu, end="", flush=True)
            choice = await loop.run_in_executor(None, sys.stdin.readline)
            if not choice:
                break
            choice = choice.strip().lower()

            if choice == "1":
                await broadcast_event({"event": "posture", "posture": "standing"})
                await broadcast_event({"event": "change_state", "state": "Idle"})
            elif choice == "2":
                await broadcast_event({"event": "change_state", "state": "Listening"})
            elif choice == "3":
                await broadcast_event({"event": "change_state", "state": "Thinking"})
            elif choice == "4":
                await broadcast_event({"event": "change_state", "state": "Teleporting"})
            elif choice == "5":
                await emit_spoken_say(
                    text="¡Llámame Capri! Constructo en línea, conectada a tu escritorio, choom.",
                    state="Speaking",
                    with_tts=True,
                )
            elif choice == "6":
                print("Escribe el texto que dirá Capri con su voz: ", end="", flush=True)
                custom_text = await loop.run_in_executor(None, sys.stdin.readline)
                if custom_text and custom_text.strip():
                    await emit_spoken_say(
                        text=custom_text.strip(),
                        state="Speaking",
                        with_tts=True,
                    )
            elif choice == "7":
                await broadcast_event({"event": "change_state", "state": "Sleeping"})
            elif choice == "8":
                await broadcast_event({"event": "posture", "posture": "perch"})
                await broadcast_event({"event": "change_state", "state": "Sitting"})
            elif choice == "9":
                await broadcast_event({"event": "change_state", "state": "Victory"})
            elif choice == "p":
                await broadcast_event({"event": "change_state", "state": "Point"})
            elif choice == "k":
                await broadcast_event({"event": "change_state", "state": "Peek"})
            elif choice == "i":
                await broadcast_event({"event": "change_state", "state": "Intro"})
            elif choice == "n":
                mini_active = not mini_active
                await broadcast_event({"event": "mini", "enabled": mini_active})
            elif choice == "l":
                await broadcast_event({"event": "posture", "posture": "lying"})
            elif choice == "d":
                dance_active = not dance_active
                await broadcast_event({"event": "dance", "enabled": dance_active})
            elif choice == "g":
                await broadcast_event({"event": "open_minigame", "game": "connect_four"})
            elif choice == "w":
                skin_idx = (skin_idx + 1) % len(skins_cycle)
                picked = skins_cycle[skin_idx]
                print(f"    -> Cambiando skin a: {picked}")
                await broadcast_event({"event": "skin", "skin": picked})
            elif choice == "b":
                st = AGENT.brain.get_status()
                print(f"\nEstado actual del Cerebro: {st.active_label}")
                print("Pega tu API Key (AIza... Gemini, gsk_... Groq, nvapi-... NVIDIA, sk-or-... OpenRouter, sk-ant-... Claude) o Enter para mantener: ", end="", flush=True)
                key_in = await loop.run_in_executor(None, sys.stdin.readline)
                if key_in and key_in.strip():
                    new_st = AGENT.brain.save_config(api_key=key_in.strip(), provider="auto")
                    print(f"    [OK] Cerebro conectado a: {new_st.active_label}")
                    await broadcast_event(build_brain_status_event())
            elif choice == "v":
                await handle_screen_glance("¿Qué ves ahora mismo en mi pantalla?")
            elif choice == "c":
                print("Tú -> Capri: ", end="", flush=True)
                user_msg = await loop.run_in_executor(None, sys.stdin.readline)
                if user_msg and user_msg.strip():
                    await handle_user_chat(None, user_msg.strip())
            elif choice == "r":
                await handle_voice_listen()
            elif choice == "o":
                print("\n--- LOOKOUT (VIGILANTE DE PANTALLA) ---")
                watches = AGENT.lookout.list_watches()
                print(f"Condiciones activas ({len(watches)}):")
                for w in watches:
                    print(f"  #{w['id']}: {w['text']}" + (" (cada vez)" if w['repeat'] else ""))
                print("Escribe qué vigilar (ej. 'avísame cuando termine la descarga de Steam') o Enter para cancelar: ", end="", flush=True)
                w_in = (await loop.run_in_executor(None, sys.stdin.readline)).strip()
                if w_in:
                    wid, msg = AGENT.lookout.add_watch(w_in)
                    print(f"    -> {msg}")
                    await broadcast_event({"event": "lookout_update", "watches": AGENT.lookout.list_watches()})
                    await emit_spoken_say(text=msg, state="Point", with_tts=True)

            elif choice == "t":
                print("\n--- RECORDATORIOS FECHADOS ---")
                pending = AGENT.dated_reminders.list_pending()
                print(f"Pendientes ({len(pending)}):")
                for r in pending:
                    print(f"  #{r['id']} ({r['due']}): {r['text']}")
                print("Escribe qué y cuándo recordar (ej. 'mañana a las 10am cita', 'en 5 minutos pizza') o Enter para cancelar: ", end="", flush=True)
                r_in = (await loop.run_in_executor(None, sys.stdin.readline)).strip()
                if r_in:
                    rid, msg = AGENT.dated_reminders.add_reminder(r_in)
                    print(f"    -> {msg}")
                    await broadcast_event({"event": "reminders_update", "pending": AGENT.dated_reminders.list_pending()})
                    await emit_spoken_say(text=msg, state="Victory", with_tts=True)

            elif choice == "y":
                print(f"\n--- ENJAMBRE DE CLONES Y HOLOGRAMA ---")
                print(f"Clones activos: {len(AGENT.clones_mgr.clones)} | Modo Holograma: {'ACTIVADO' if AGENT.clones_mgr.hologram_mode else 'DESACTIVADO'}")
                print("[1] Invocar 3 clones (Chibi Swarm)")
                print("[2] Invocar 5 clones (Chibi Swarm)")
                print("[3] Desvanecer todos los clones (Clear)")
                print("[4] Alternar Modo Holograma (Click-Through)")
                print("Elige una opción (1-4) o Enter para cancelar: ", end="", flush=True)
                c_opt = (await loop.run_in_executor(None, sys.stdin.readline)).strip()
                if c_opt in ("1", "2"):
                    cnt = 3 if c_opt == "1" else 5
                    c, msg = AGENT.clones_mgr.spawn(count=cnt)
                    await broadcast_event({"event": "clones", **AGENT.clones_mgr.to_event_payload()})
                    await emit_spoken_say(text=msg, state="Victory", with_tts=True)
                elif c_opt == "3":
                    c, msg = AGENT.clones_mgr.clear()
                    await broadcast_event({"event": "clones", **AGENT.clones_mgr.to_event_payload()})
                    await emit_spoken_say(text=msg, state="Speaking", with_tts=True)
                elif c_opt == "4":
                    mode, msg = AGENT.clones_mgr.toggle_hologram()
                    await broadcast_event({"event": "hologram", "enabled": mode})
                    await emit_spoken_say(text=msg, state="Speaking", with_tts=True)

            elif choice == "x":
                print(f"\n--- MOTOR DE VOZ ACTUAL: {VOICE.get_active_voice_label()} ---")
                print(f"    Paquete Oficial Kokoro 82M (capri-voice-1): {'INSTALADO' if VOICE.kokoro.is_installed else ('DESCARGANDO (' + str(round(VOICE.kokoro.download_progress_pct)) + '%)' if VOICE.kokoro.is_downloading else 'No descargado aún (316 MB)')}")
                print("    [1] Voz offline de Windows (Microsoft Laura + VoiceFx WSOLA +2.0st / 118%)")
                print("    [2] Estilo Kokoro: 'Dora' (español nativo, Speaker 28)")
                print("    [3] Pegar API Key de ElevenLabs (voz cloud oficial)")
                print("    [4] Descargar / Activar Voz Original `capri-voice-1` (Kokoro 82M Speaker 53 'Her own')")
                print("    [5] Alternar Doblaje Armónico Cyberpunk (Layerer: Off / 1 Capa / 2 Capas)")
                print("Elige opción de voz (1-5) o Enter para cancelar: ", end="", flush=True)
                v_opt = (await loop.run_in_executor(None, sys.stdin.readline)).strip()
                if v_opt == "1":
                    VOICE.voice_mode = "offline"
                    VOICE.save_config()
                    await emit_spoken_say("Listo, choom. Uso la voz offline de Windows con mi estilizado.", "Victory")
                elif v_opt == "2":
                    VOICE.voice_mode = "kokoro"
                    VOICE.kokoro_style = "dora_es"
                    VOICE.save_config()
                    await emit_spoken_say("Estilo Dora activado. Si aún no tengo el paquete Kokoro, usa la opción cuatro.", "Victory")
                elif v_opt == "3":
                    print("Pega tu API Key de ElevenLabs: ", end="", flush=True)
                    el_key = (await loop.run_in_executor(None, sys.stdin.readline)).strip()
                    if el_key:
                        VOICE.elevenlabs_key = el_key
                        VOICE.voice_mode = "elevenlabs"
                        VOICE.save_config()
                        await emit_spoken_say("Voz de ElevenLabs conectada, choom.", "Victory")
                elif v_opt == "4":
                    VOICE.voice_mode = "kokoro"
                    VOICE.kokoro_style = "her_own"
                    VOICE.save_config()
                    if VOICE.kokoro.is_installed:
                        await emit_spoken_say("¡Voz original Kokoro 82M Speaker 53 activada, choom!", "Victory")
                    else:
                        def _done_cb(ok: bool, msg: str) -> None:
                            print(f"\n    [VoicePack]: {msg}")
                        VOICE.kokoro.download_pack_in_background(on_done=_done_cb)
                        print(f"    -> {VOICE.kokoro.download_status_msg}")
                        await emit_spoken_say("Empecé a descargar mi paquete de voz original Kokoro 82M en segundo plano, choom.", "Speaking")
                elif v_opt == "5":
                    order = ["off", "one", "two"]
                    VOICE.layers_mode = order[(order.index(VOICE.layers_mode) + 1) % len(order)] if VOICE.layers_mode in order else "one"
                    VOICE.save_config()
                    await emit_spoken_say(f"Capas vocales armónicas ajustadas en modo {VOICE.layers_mode}, choom.", "Speaking")
            elif choice == "m":
                await broadcast_event({"event": "mute", "muted": True})
            elif choice == "q":
                print("Cerrando servidor...")
                break
            else:
                print("Opción no válida.")
        except Exception as e:
            print(f"Error en consola: {e}")
            break


async def main():
    loop = asyncio.get_running_loop()

    def _default_autopilot_say(comment: str) -> None:
        if comment and comment.strip():
            asyncio.run_coroutine_threadsafe(
                emit_spoken_say(text=comment.strip(), state="Speaking", with_tts=True),
                loop,
            )

    AGENT.on_autopilot_say = _default_autopilot_say
    st = AGENT.brain.get_status()
    # Precalentar el demonio de síntesis de voz en segundo plano
    loop.run_in_executor(None, VOICE._ensure_tts_worker)
    print(f">> Iniciando servidor WebSocket + Cerebro y Voz Capri en ws://{HOST}:{PORT} ...")
    print(f">> Cerebro IA detectado: {st.active_label}")
    print(f">> Motor de Voz activo : {VOICE.get_active_voice_label()}")
    server = await websockets.serve(handler, HOST, PORT)
    monitor_task = asyncio.create_task(background_monitor_loop())
    print(">> Servidor en línea. Esperando conexiones de Flutter...")

    try:
        await interactive_console()
    finally:
        monitor_task.cancel()
        server.close()
        await server.wait_closed()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServidor detenido por el usuario.")
