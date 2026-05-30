from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


def seconds_until_next_hour() -> int:
    now = datetime.now()
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return int((next_hour - now).total_seconds())


def segment_filename(now: datetime, is_partial: bool) -> str:
    if is_partial:
        return now.strftime("%H_%M_%S")
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return next_hour.strftime("%H_%M_%S")


def build_output_path(
    base_dir: Path, camera_name: str, dt: datetime
) -> Path:
    return base_dir / str(dt.year) / f"{dt.month:02d}" / f"{dt.day:02d}" / camera_name


def crop_filter(split: str, half: str) -> Optional[str]:
    if split == "vertical":
        if half == "L":
            return "crop=iw/2:ih:0:0"
        elif half == "R":
            return "crop=iw/2:ih:iw/2:0"
    elif split == "horizontal":
        if half == "T":
            return "crop=iw:ih/2:0:0"
        elif half == "B":
            return "crop=iw:ih/2:0:ih/2"
    return None


def halves_for_split(split: str) -> list[tuple[str, str]]:
    if split == "vertical":
        return [("L", "crop=iw/2:ih:0:0"), ("R", "crop=iw/2:ih:iw/2:0")]
    elif split == "horizontal":
        return [("T", "crop=iw:ih/2:0:0"), ("B", "crop=iw:ih/2:0:ih/2")]
    return [("", "")]
