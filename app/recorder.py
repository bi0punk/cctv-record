import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config import CameraConfig, settings
from app.utils import (
    build_output_path,
    crop_filter,
    halves_for_split,
    seconds_until_next_hour,
    segment_filename,
)

logger = logging.getLogger(__name__)


class CameraRecorder:
    def __init__(self, camera: CameraConfig):
        self.camera = camera
        self._task: Optional[asyncio.Task] = None
        self._processes: list[asyncio.subprocess.Process] = []
        self._started_at: Optional[datetime] = None
        self._last_file: Optional[str] = None
        self._error: Optional[str] = None
        self._lock = asyncio.Lock()

    @property
    def status(self) -> str:
        if self._error:
            return "error"
        if self._task and not self._task.done():
            return "recording"
        return "stopped"

    @property
    def started_at(self) -> Optional[datetime]:
        return self._started_at

    @property
    def last_file(self) -> Optional[str]:
        return self._last_file

    @property
    def error(self) -> Optional[str]:
        return self._error

    async def start(self):
        async with self._lock:
            if self._task and not self._task.done():
                return
            self._error = None
            self._started_at = datetime.now()
            self._task = asyncio.create_task(self._record_loop())

    async def stop(self):
        async with self._lock:
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except (asyncio.CancelledError, Exception):
                    pass
                self._task = None
            await self._kill_processes(self._processes)
            self._processes = []

    async def _record_loop(self):
        is_first = True
        try:
            while True:
                if is_first:
                    remaining = seconds_until_next_hour()
                    is_first = False
                    if remaining > 10:
                        self._processes = await self._spawn_segment(
                            duration=remaining, partial=True
                        )
                    # fall through: if remaining <= 10, start hourly right away

                wait = seconds_until_next_hour() - 5
                if wait > 0:
                    await asyncio.sleep(wait)

                if asyncio.current_task().cancelled():
                    break

                new_procs = await self._spawn_segment(
                    duration=3600 + 5, partial=False
                )

                await asyncio.sleep(10)

                await self._kill_processes(self._processes)
                self._processes = new_procs
        except asyncio.CancelledError:
            await self._kill_processes(self._processes)
            self._processes = []
            raise
        except Exception as e:
            self._error = str(e)
            logger.exception("Camera %s recording loop crashed", self.camera.name)
            await self._kill_processes(self._processes)
            self._processes = []

    async def _spawn_segment(
        self, duration: int, partial: bool
    ) -> list[asyncio.subprocess.Process]:
        now = datetime.now()
        output_dir = build_output_path(
            settings.recordings_dir, self.camera.name, now
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        base_name = segment_filename(now, partial)
        halves = halves_for_split(self.camera.split)
        procs = []

        for half, filt in halves:
            suffix = f"_{half}" if half else ""
            output_path = output_dir / f"{base_name}{suffix}.mp4"
            self._last_file = str(output_path)
            proc = await self._run_ffmpeg(
                url=self.camera.url,
                output_path=output_path,
                duration=duration,
                crop_filter=filt if filt else None,
            )
            procs.append(proc)

        return procs

    async def _run_ffmpeg(
        self,
        url: str,
        output_path: Path,
        duration: int,
        crop_filter: Optional[str] = None,
    ) -> asyncio.subprocess.Process:
        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-rtsp_transport",
            "tcp",
            "-i",
            url,
            "-t",
            str(duration),
        ]
        if crop_filter:
            cmd += [
                "-vf",
                crop_filter,
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "23",
            ]
        else:
            cmd += ["-c", "copy"]
        cmd += ["-an", str(output_path)]

        logger.info("FFmpeg: %s", " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        return proc

    async def _kill_processes(
        self, procs: list[asyncio.subprocess.Process]
    ):
        for proc in procs:
            if proc.returncode is None:
                try:
                    proc.terminate()
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()


class RecorderManager:
    def __init__(self):
        self._recorders: dict[str, CameraRecorder] = {}
        self._started_at: Optional[datetime] = None

    @property
    def started_at(self) -> Optional[datetime]:
        return self._started_at

    def load_cameras(self, cameras: list[CameraConfig]):
        self._recorders = {c.name: CameraRecorder(c) for c in cameras}

    async def start_all(self):
        self._started_at = datetime.now()
        for rec in self._recorders.values():
            await rec.start()

    async def stop_all(self):
        for rec in self._recorders.values():
            await rec.stop()

    async def start_camera(self, name: str):
        if name in self._recorders:
            await self._recorders[name].start()

    async def stop_camera(self, name: str):
        if name in self._recorders:
            await self._recorders[name].stop()

    async def restart_camera(self, name: str):
        if name in self._recorders:
            await self._recorders[name].stop()
            await self._recorders[name].start()

    def get_status(self, name: str) -> Optional[dict]:
        rec = self._recorders.get(name)
        if not rec:
            return None
        return {
            "name": rec.camera.name,
            "url": rec.camera.url,
            "split": rec.camera.split,
            "status": rec.status,
            "started_at": rec.started_at,
            "last_file": rec.last_file,
            "error": rec.error,
        }

    def get_all_status(self) -> list[dict]:
        return [self.get_status(name) for name in self._recorders]

    def system_status(self) -> dict:
        all_status = self.get_all_status()
        recording = sum(1 for s in all_status if s["status"] == "recording")
        errors = sum(1 for s in all_status if s["status"] == "error")
        uptime = None
        if self._started_at:
            uptime = (datetime.now() - self._started_at).total_seconds()
        return {
            "total_cameras": len(all_status),
            "recording_count": recording,
            "error_count": errors,
            "recordings_dir": str(settings.recordings_dir),
            "uptime": uptime,
        }


manager = RecorderManager()
