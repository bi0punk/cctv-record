from datetime import datetime

from pydantic import BaseModel


class CameraConfigOut(BaseModel):
    name: str
    url: str
    split: str


class CameraStatusOut(BaseModel):
    name: str
    url: str
    split: str
    status: str  # "recording" | "stopped" | "error"
    started_at: datetime | None = None
    last_file: str | None = None
    error: str | None = None


class RecordingNode(BaseModel):
    id: str
    parent: str
    text: str
    type: str = "folder"
    data: dict | None = None


class SystemStatusOut(BaseModel):
    total_cameras: int
    recording_count: int
    error_count: int
    recordings_dir: str
    uptime: float | None = None
