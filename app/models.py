from datetime import datetime
from typing import Optional

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
    started_at: Optional[datetime] = None
    last_file: Optional[str] = None
    error: Optional[str] = None


class RecordingNode(BaseModel):
    id: str
    parent: str
    text: str
    type: str = "folder"
    data: Optional[dict] = None


class SystemStatusOut(BaseModel):
    total_cameras: int
    recording_count: int
    error_count: int
    recordings_dir: str
    uptime: Optional[float] = None
