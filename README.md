# CCTV Recorder

Sistema grabador de cámaras IP vía RTSP con segmentación horaria, soporte para cámaras dual-lente y web UI.

## Arquitectura

```
┌──────────────┐     RTSP      ┌──────────────────────────────────┐
│ Cámara RTSP  │◄────────────►│  FastAPI (uvicorn)                │
│ (red local)  │              │  ├── CameraRecorder (asyncio)    │
└──────────────┘              │  ├── FFmpeg subprocess           │
                              │  └── Jinja2 + Bootstrap 5        │
┌──────────────┐              │         │                        │
│ Cámara RTSP  │◄────────────►│  ┌──────┴──────┐                 │
│ dual-lente   │              │  │ recordings/ │                 │
└──────────────┘              │  │ año/mes/dia │                 │
                              │  │ /camara/*.mp4                 │
                              └──────────────────────────────────┘
                                        │
                                 Web UI (puerto 8000)
```

## Requisitos

- Python 3.11+
- FFmpeg (con soporte para codecs H.264/H.265)
- Acceso a las cámaras por RTSP en la red local

## Instalación

```bash
git clone <repo>
cd cctv-record
pip install -r requirements.txt
```

## Configuración

Editar `.env`:

```ini
# Lista de cámaras en formato JSON (una línea)
CAMERAS_JSON=[{"name":"Entrada","url":"rtsp://admin:pass@192.168.1.100:554/stream1","split":"none"},{"name":"Garaje","url":"rtsp://192.168.1.101:554/stream1","split":"vertical"},{"name":"Patio","url":"rtsp://192.168.1.102:554/stream1","split":"horizontal"}]

# Directorio donde se guardan las grabaciones
RECORDINGS_DIR=./recordings

# Interfaz y puerto del servidor web
HOST=0.0.0.0
PORT=8000
```

### Campos de cada cámara

| Campo | Tipo | Descripción |
|---|---|---|
| `name` | string | Nombre identificativo (se usa como nombre de directorio) |
| `url` | string | URL RTSP completa (`rtsp://user:pass@ip:port/path`) |
| `split` | string | `"none"` = cámara normal, `"vertical"` = lentes izq/der, `"horizontal"` = lentes arriba/abajo |

## Uso

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Abrir `http://localhost:8000` en el navegador.

### Web UI

- **Dashboard** (`/`): Cards con estado de cada cámara. Botones para iniciar/detener todas o individualmente. Polling automático cada 3 segundos.
- **Grabaciones** (`/recordings`): Explorador de archivos con jsTree. Navegación por año → mes → día → cámara → archivos. Al hacer clic en un video se reproduce en el navegador con opción de descarga.

### API REST

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/cameras` | Estado de todas las cámaras |
| `GET` | `/api/status` | Estado general del sistema |
| `POST` | `/api/start` | Iniciar grabación de todas |
| `POST` | `/api/stop` | Detener todas |
| `POST` | `/api/camera/{name}/start` | Iniciar una cámara |
| `POST` | `/api/camera/{name}/stop` | Detener una cámara |
| `POST` | `/api/camera/{name}/restart` | Reiniciar una cámara |
| `GET` | `/api/recordings/tree` | Árbol de archivos para jsTree |
| `GET` | `/api/recordings/stream?path=...` | Stream de video con soporte Range |

## Lógica de Grabación

### Alineación a la hora

El sistema siempre alinea los segmentos de grabación al inicio de cada hora:

1. **Si arranca en hora no exacta** (ej: 10:23:15): calcula los segundos restantes hasta la próxima hora y graba ese primer segmento parcial (37 min en el ejemplo).
2. **A partir de la hora siguiente**: todos los segmentos son de exactamente 1 hora (11:00-12:00, 12:00-13:00, etc.).
3. **Si arranca muy cerca de la hora** (menos de 10s): ignora el segmento parcial y empieza directamente con el primer bloque de 1h.

### Overlap (solapamiento)

Para evitar la pérdida de frames entre segmentos, se usa una técnica de solapamiento:

```
10:00:00 ────────────── 11:00:00 ────────────── 12:00:00
  │                        │                        │
  │ [FFmpeg A] ──t=3600───▶│  (termina natural)     │
  │       10:59:55         │                        │
  │          ├─ [FFmpeg B] ───t=3605────────────────▶│
  │          │  (overlap)   │                        │
  │          └─ mata A      │  11:59:55              │
  │          a las 11:00:05 │    ├─ [FFmpeg C] ──────▶│
  │                         │    └─ mata B           │
  │                         │    a las 12:00:05      │
```

- **5 segundos antes** de la hora: se lanza el nuevo proceso FFmpeg en paralelo.
- **5 segundos después** de la hora: se detiene el proceso anterior (con SIGTERM, luego SIGKILL si no responde en 5s).
- El solapamiento de ~10 segundos garantiza que ningún frame se pierda en la transición.

### Tecnología de captura

Se utiliza `ffmpeg` vía `asyncio.create_subprocess_exec`:

- **Sin split**: `-c copy` (copia directa del stream, sin recodificar, CPU mínimo).
- **Con split**: `-vf crop=... -c:v libx264 -preset ultrafast` (recodifica la mitad recortada).
- **Sin audio**: `-an` (las cámaras IP suelen tener audio de baja calidad o ruido).

## Cámaras Dual-Lente

### Split vertical (izquierda/derecha)

Para cámaras que combinan dos lentes en una imagen partida verticalmente:

```
┌─────────┬─────────┐      ┌─────────┐  ┌─────────┐
│         │         │      │         │  │         │
│  Lente  │  Lente  │  →   │  _L.mp4 │  │  _R.mp4 │
│    A    │    B    │      │         │  │         │
│         │         │      └─────────┘  └─────────┘
└─────────┴─────────┘
```

Crop FFmpeg: `crop=iw/2:ih:0:0` (izquierda) y `crop=iw/2:ih:iw/2:0` (derecha).

### Split horizontal (arriba/abajo)

Para cámaras con lentes apilados verticalmente:

```
┌───────────────┐          ┌───────────────┐
│   Lente A     │          │   _T.mp4      │
├───────────────┤     →    └───────────────┘
│   Lente B     │          ┌───────────────┐
│               │          │   _B.mp4      │
└───────────────┘          └───────────────┘
```

Crop FFmpeg: `crop=iw:ih/2:0:0` (superior) y `crop=iw:ih/2:0:ih/2` (inferior).

## Estructura de Archivos

```
recordings/
└── 2026/                           # Año
    └── 05/                         # Mes
        └── 30/                     # Día
            ├── Entrada/            # Cámara (split: none)
            │   ├── 15_57_15.mp4     # Primer segmento parcial
            │   └── 16_00_00.mp4     # Segmento horario
            ├── Garaje/             # Cámara (split: vertical)
            │   ├── 15_57_15_L.mp4
            │   ├── 15_57_15_R.mp4
            │   ├── 16_00_00_L.mp4
            │   └── 16_00_00_R.mp4
            └── Patio/              # Cámara (split: horizontal)
                ├── 15_57_15_T.mp4
                ├── 15_57_15_B.mp4
                ├── 16_00_00_T.mp4
                └── 16_00_00_B.mp4
```

Los nombres de archivo usan el timestamp de inicio del segmento:
- `15_57_15.mp4` → inicio a las 15:57:15 (primer segmento parcial)
- `16_00_00.mp4` → segmento que cubre 16:00-17:00

Sufijos para dual-lente:
- `_L` / `_R` → mitad izquierda / derecha (split vertical)
- `_T` / `_B` → mitad superior / inferior (split horizontal)

## Scripts Técnicos

### app/recorder.py — CameraRecorder

Clase que maneja el loop de grabación de una cámara:

- `start()` → crea un `asyncio.Task` con `_record_loop()`
- `_record_loop()` → calcula duraciones, spawns FFmpeg con overlap, mata procesos viejos
- `_spawn_segment(duration, partial)` → lanza FFmpeg con los filtros de crop según `split`
- `_run_ffmpeg()` → ejecuta `ffmpeg` con los parámetros adecuados

### app/recorder.py — RecorderManager

Orquesta todas las cámaras:

- `load_cameras()` → crea un `CameraRecorder` por cámara
- `start_all()` / `stop_all()` → control global
- `get_status(name)` / `get_all_status()` → estado actual de cada cámara

### app/utils.py

- `seconds_until_next_hour()` → segundos hasta el próximo minuto :00
- `segment_filename(now, is_partial)` → nombre del archivo (HH_MM_SS para parcial, HH_00_00 para horario)
- `crop_filter(split, half)` → string de filtro FFmpeg para el crop
- `build_output_path()` → ruta año/mes/dia/camara

### app/config.py

Carga la configuración desde `.env` usando `python-dotenv` y modelos Pydantic.

## Posibles Mejoras

- Autoinicio al arrancar el servidor (variable `AUTO_START=true` en `.env`)
- WebSockets para estado en tiempo real sin polling
- Autenticación básica en la web
- Retención automática (borrar grabaciones antiguas según `RETENTION_DAYS`)
- Notificaciones ante caída de cámaras
- Dashboard con miniaturas en vivo (MJPEG o HLS)
