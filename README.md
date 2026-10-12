# CCTV Recorder

Grabador de cámaras IP vía RTSP con segmentación horaria, soporte para cámaras dual-lente y web UI. Construido con FastAPI + FFmpeg.

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/bi0punk/cctv-record/actions/workflows/ci.yml/badge.svg)](https://github.com/bi0punk/cctv-record/actions/workflows/ci.yml)

## Contenido

- [Características](#características)
- [Arquitectura](#arquitectura)
- [Stack](#stack)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Instalación](#instalación)
- [Uso](#uso)
- [Configuración](#configuración)
- [Lógica de grabación](#lógica-de-grabación)
- [Cámaras dual-lente](#cámaras-dual-lente)
- [Estructura de archivos](#estructura-de-archivos)
- [Tests / CI](#tests--ci)
- [Roadmap](#roadmap)
- [Licencia](#licencia)

## Características

- Grabación continua por cámara con segmentos alineados a la hora.
- Overlap de ~10 segundos entre segmentos para no perder frames.
- Cámaras dual-lente: split vertical (izquierda/derecha) y horizontal (arriba/abajo).
- Sin split: copia directa del stream (`-c copy`, escaso uso de CPU).
- Web UI (Dashboard + explorador de grabaciones con jsTree).
- API REST para control de cámaras y acceso a grabaciones.
- Configuración por `.env` con modelos Pydantic.

## Arquitectura

```mermaid
flowchart TD
  CAM[Camaras RTSP red local] -->|RTSP| RDG[FastAPI uvicorn]
  subgraph App [cctv-record]
    RDG --> MG[RecorderManager]
    MG --> CR[CameraRecorder asyncio]
    CR --> FF[FFmpeg subprocess]
    FF --> REC[(recordings/ ano/mes/dia/camara)]
    RDG --> API[API REST + Jinja2]
    API --> CR
  end
  REC --> WD[Web UI navegador :8000]
  API --> WD
```

- **CameraRecorder** (app/recorder.py): loop de grabación por cámara; calcula duraciones, lanza FFmpeg con overlap y mata los procesos viejos (SIGTERM y luego SIGKILL).
- **RecorderManager**: orquesta todas las cámaras (start/stop/restart y estado).
- **FFmpeg**: usa `-c copy` sin split, o crop + `libx264 -preset ultrafast` cuando hay split; sin audio (`-an`).

## Stack

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.11+ |
| Web/API | FastAPI + Uvicorn, Jinja2, Bootstrap 5 |
| Captura | FFmpeg (H.264/H.265) vía `asyncio.create_subprocess_exec` |
| Config | python-dotenv + Pydantic/Pydantic-Settings |
| Frontend | Bootstrap 5 + jsTree (explorador de grabaciones) |
| Testing | pytest + pytest-asyncio |

## Estructura del repositorio

```
cctv-record/
├── app/
│   ├── main.py        # FastAPI app + rutas
│   ├── config.py      # Settings desde .env
│   ├── models.py      # Schemas Pydantic
│   ├── recorder.py    # CameraRecorder + RecorderManager
│   └── utils.py       # Segmentos, nombres, filtros crop
├── templates/         # dashboard.html, recordings.html, base.html
├── static/            # css/js
├── tests/             # test_api, test_config, test_recorder, test_utils
├── .env.example
├── .github/workflows/ci.yml
└── README.md
```

## Instalación

```bash
git clone https://github.com/bi0punk/cctv-record.git
cd cctv-record
pip install -r requirements.txt
```

Requisitos: Python 3.11+, FFmpeg (con soporte H.264/H.265) y acceso RTSP a las cámaras.

## Uso

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Abrir `http://localhost:8000`.

- **Dashboard** (`/`): cards con estado de cada cámara, botones para iniciar/detener, polling automático cada 3 s.
- **Grabaciones** (`/recordings`): explorador por año → mes → día → cámara → archivos con reproducción en navegador y descarga.

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

## Configuración

Editar `.env` (ver `.env.example`):

```ini
# Lista de cámaras en formato JSON (una línea)
CAMERAS_JSON=[{"name":"Entrada","url":"rtsp://admin:pass@192.168.1.100:554/stream1","split":"none"},{"name":"Garaje","url":"rtsp://192.168.1.101:554/stream1","split":"vertical"}]

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

## Lógica de grabación

### Alineación a la hora

1. Si arranca en hora no exacta, calcula los segundos restantes hasta la próxima hora y graba ese primer segmento parcial.
2. A partir de la hora siguiente todos los segmentos son de exactamente 1 hora.
3. Si arranca a menos de 10s de la hora, ignora el parcial y empieza con el primer bloque de 1h.

### Overlap (solapamiento)

```mermaid
sequenceDiagram
  participant F as FFmpeg proceso viejo
  participant N as FFmpeg proceso nuevo
  participant K as RecorderManager
  K->>N: lanza 5s antes de la hora (overlap)
  N-->>F: graba en paralelo ~10s
  K->>F: SIGTERM 5s después de la hora
  F-->>K: si no responde en 5s -> SIGKILL
```

El solapamiento garantiza que ningún frame se pierda durante la transición entre segmentos.

## Cámaras dual-lente

### Split vertical (izquierda/derecha)

Crop FFmpeg: `crop=iw/2:ih:0:0` (izquierda) y `crop=iw/2:ih:iw/2:0` (derecha). Genera `_L.mp4` y `_R.mp4`.

### Split horizontal (arriba/abajo)

Crop FFmpeg: `crop=iw:ih/2:0:0` (superior) y `crop=iw:ih/2:0:ih/2` (inferior). Genera `_T.mp4` y `_B.mp4`.

## Estructura de archivos

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
            │   └── 16_00_00_L.mp4
            └── Patio/              # Cámara (split: horizontal)
                ├── 15_57_15_T.mp4
                └── 16_00_00_T.mp4
```

Sufijos dual-lente: `_L`/`_R` (split vertical), `_T`/`_B` (split horizontal). Los nombres usan el timestamp de inicio del segmento.

## Tests / CI

```bash
pip install -r requirements.txt
pytest tests/ -v
```

GitHub Actions (`.github/workflows/ci.yml`) sobre Python 3.11: lint con ruff y suite pytest.

## Roadmap

- [x] Grabación horaria con overlap y split dual-lente
- [ ] Autoinicio al arrancar el servidor (`AUTO_START`)
- [ ] WebSockets para estado en tiempo real
- [ ] Autenticación básica en la web
- [ ] Retención automática de grabaciones
- [ ] Notificaciones ante caída de cámaras
- [ ] Miniatura en vivo en dashboard

## Licencia

MIT — ver [LICENSE](LICENSE).