import json
import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field


load_dotenv()


class CameraConfig(BaseModel):
    name: str
    url: str
    split: Literal["none", "vertical", "horizontal"] = "none"


class Settings(BaseModel):
    cameras: list[CameraConfig] = Field(default=[])
    recordings_dir: Path = Field(default=Path("./recordings"))
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)


def load_settings() -> Settings:
    raw = os.getenv("CAMERAS_JSON", "[]")
    cameras_data = json.loads(raw)
    cameras = [CameraConfig(**c) for c in cameras_data]

    recordings_dir = Path(os.getenv("RECORDINGS_DIR", "./recordings"))
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    return Settings(
        cameras=cameras,
        recordings_dir=recordings_dir,
        host=host,
        port=port,
    )


settings = load_settings()
