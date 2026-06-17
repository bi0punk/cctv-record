import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="CCTV Recorder")

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

from app.recorder import manager


@app.on_event("startup")
async def startup():
    logger.info("Loading %d cameras from config", len(settings.cameras))
    manager.load_cameras(settings.cameras)
    logger.info("CCTV Recorder ready. Navigate to http://%s:%s", settings.host, settings.port)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "cameras": manager.get_all_status()},
    )


@app.get("/recordings", response_class=HTMLResponse)
async def recordings_page(request: Request):
    return templates.TemplateResponse(
        "recordings.html",
        {"request": request},
    )


@app.get("/api/cameras")
async def get_cameras():
    return manager.get_all_status()


@app.get("/api/status")
async def get_status():
    return manager.system_status()


@app.post("/api/start")
async def start_all():
    await manager.start_all()
    return {"status": "ok", "message": "All cameras started"}


@app.post("/api/stop")
async def stop_all():
    await manager.stop_all()
    return {"status": "ok", "message": "All cameras stopped"}


@app.post("/api/camera/{name}/start")
async def start_camera(name: str):
    status = manager.get_status(name)
    if not status:
        raise HTTPException(404, f"Camera '{name}' not found")
    await manager.start_camera(name)
    return {"status": "ok", "message": f"Camera '{name}' started"}


@app.post("/api/camera/{name}/stop")
async def stop_camera(name: str):
    status = manager.get_status(name)
    if not status:
        raise HTTPException(404, f"Camera '{name}' not found")
    await manager.stop_camera(name)
    return {"status": "ok", "message": f"Camera '{name}' stopped"}


@app.post("/api/camera/{name}/restart")
async def restart_camera(name: str):
    status = manager.get_status(name)
    if not status:
        raise HTTPException(404, f"Camera '{name}' not found")
    await manager.restart_camera(name)
    return {"status": "ok", "message": f"Camera '{name}' restarted"}


@app.get("/api/recordings/tree")
async def recordings_tree():
    base = settings.recordings_dir
    if not base.exists():
        return []

    nodes = []
    dirs = sorted(base.iterdir())

    for year_dir in dirs:
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        year = year_dir.name
        nodes.append({"id": year, "parent": "#", "text": year, "type": "folder"})

        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir() or not month_dir.name.isdigit():
                continue
            month_id = f"{year}/{month_dir.name}"
            month_name = month_name_es(int(month_dir.name))
            nodes.append({
                "id": month_id,
                "parent": year,
                "text": f"{month_dir.name} ({month_name})",
                "type": "folder",
            })

            for day_dir in sorted(month_dir.iterdir()):
                if not day_dir.is_dir() or not day_dir.name.isdigit():
                    continue
                day_id = f"{month_id}/{day_dir.name}"
                nodes.append({
                    "id": day_id,
                    "parent": month_id,
                    "text": day_dir.name,
                    "type": "folder",
                })

                for cam_dir in sorted(day_dir.iterdir()):
                    if not cam_dir.is_dir():
                        continue
                    cam_id = f"{day_id}/{cam_dir.name}"
                    nodes.append({
                        "id": cam_id,
                        "parent": day_id,
                        "text": cam_dir.name,
                        "type": "folder",
                    })

                    for video in sorted(cam_dir.iterdir()):
                        if video.suffix.lower() not in (".mp4", ".mkv", ".avi"):
                            continue
                        vid_id = f"{cam_id}/{video.stem}"
                        rel_path = str(video.relative_to(base))
                        nodes.append({
                            "id": vid_id,
                            "parent": cam_id,
                            "text": video.name,
                            "type": "video",
                            "data": {"path": rel_path},
                        })

    return nodes


@app.get("/api/recordings/stream")
async def stream_recording(path: str):
    resolved = (settings.recordings_dir / path).resolve()
    base = settings.recordings_dir.resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        raise HTTPException(403, "Access denied")
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(str(resolved), media_type="video/mp4")


def month_name_es(m: int) -> str:
    months = [
        "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]
    return months[m] if 1 <= m <= 12 else ""
