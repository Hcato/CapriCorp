# Asistente Claret: Módulo de Interfaz e Identidad (Core Loop)

Núcleo interactivo y conversacional para el Asistente de IA Modular en **Windows 11**, optimizado para laptops con GPU discreta moderada (**NVIDIA RTX 4050 6GB VRAM, Intel i5, 16GB RAM**).

---

## 🏛️ Arquitectura del Sistema (Clean Architecture)

```
Claret/
├── config.py             # Configuración central (modelos, voz, audio, modo de escucha)
├── audio_listener.py     # Captura de micrófono (Push-to-Talk / VAD) + STT con faster-whisper
├── llm_router.py         # Cerebro cognitivo inicial (Ollama) con Router Pattern
├── voice_synth.py        # Síntesis de voz (edge-tts) y reproducción no bloqueante (pygame)
├── main.py               # Orquestador del bucle principal interactivo (Core Loop)
├── requirements.txt      # Dependencias exactas
└── README.md             # Guía de instalación y uso
```

### ⚡ Presupuesto y Consumo de Recursos en RTX 4050 (6 GB VRAM)
- **Speech-to-Text (faster-whisper `base` / `small` en CUDA `float16`):** ~300 MB a 800 MB de VRAM. Latencia de transcripción: ~200-400 ms.
- **LLM Enrutador (`qwen2.5:3b` o `llama3.2:3b` en Ollama 4-bit):** ~2.0 GB a 2.3 GB de VRAM.
- **Text-to-Speech (`edge-tts` en streaming):** **0 MB de VRAM** (corre en la nube de Microsoft Edge de forma ultrarrápida y gratuita).
- **VRAM Total Estimada:** **~2.6 GB a 3.0 GB**, dejando más de 3 GB de VRAM libres para el sistema y futuros agentes especializados.

---

## 🚀 Requisitos Previos

### 1. Ollama (Servidor Local de LLM)
Descarga e instala Ollama para Windows desde [ollama.com](https://ollama.com). Luego, descarga el modelo recomendado en tu terminal:

```powershell
ollama pull qwen2.5:3b
# o alternativamente:
# ollama pull llama3.2
```

### 2. Entorno Virtual de Python (Recomendado)
Desde la carpeta del proyecto en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> **Nota sobre CUDA en Windows con `faster-whisper`:**
> `faster-whisper` utiliza CTranslate2. Para aprovechar la GPU al máximo, requiere las librerías cuBLAS y cuDNN para CUDA 12. Si no están configuradas en el PATH del sistema, `audio_listener.py` cuenta con **fallback automático a CPU (`int8`)** para que el asistente funcione de inmediato sin romperse.
> Para activar la aceleración por GPU, puedes instalar las bibliotecas de NVIDIA vía pip:
> ```powershell
> pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
> ```

---

## ⚙️ Configuración (`config.py`)

Puedes ajustar el comportamiento editando `config.py`:
- `stt_config.listen_mode`: `"push_to_talk"` (por defecto) o `"vad"` (detección continua por silencio de voz).
- `stt_config.push_to_talk_key`: Tecla para hablar (por defecto `"space"`).
- `stt_config.model_name`: `"base"` (más rápido) o `"small"` (más preciso).
- `llm_config.model`: `"qwen2.5:3b"` o `"llama3.2"`.
- `tts_config.voice`: Voz de Edge TTS (ej. `"es-ES-AlvaroNeural"`, `"es-ES-ElviraNeural"`, `"es-MX-DaliaNeural"`).

---

## 🎮 Ejecución

Para iniciar el bucle principal interactivo:

```powershell
python main.py
```

### Flujo de Uso en Modo Push-to-Talk:
1. El asistente saluda por voz: *"Asistente Claret en línea y listo..."*
2. **Mantén presionada la barra espaciadora** mientras hablas por el micrófono.
3. **Suelta la barra espaciadora** al terminar.
4. `faster-whisper` transcribe en memoria en milisegundos.
5. El modelo en Ollama clasifica la intención (`chat`, `system`, `agent_search`, `agent_code`) y formula una respuesta breve.
6. `edge-tts` sintetiza y reproduce la voz sin congelar la aplicación.
7. Di **"adiós"** o presiona `Ctrl+C` para finalizar.
