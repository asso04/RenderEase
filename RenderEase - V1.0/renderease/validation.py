"""Deterministic validation. Never creates or overwrites files."""
from datetime import datetime
from pathlib import Path
from .utils import parse_local


def validate(job, scene_names, *, saving=False, now=None):
    errors, warnings = [], []
    now = now or datetime.now()
    if not job.name.strip():
        errors.append("Enter a job name.")
    if job.scene_name not in scene_names:
        errors.append("Referenced scene does not exist.")
    if job.render_type not in ('STILL', 'ANIMATION'):
        errors.append("Choose still or animation.")
    if not 0 <= job.frame_start <= 1048574 or not 0 <= job.frame_end <= 1048574:
        errors.append("Frames must be between 0 and 1048574.")
    if job.frame_end < job.frame_start:
        errors.append("End frame must not precede start frame.")
    if not 4 <= job.resolution_x <= 65536 or not 4 <= job.resolution_y <= 65536:
        errors.append("Resolution must be between 4 and 65536 pixels.")
    if not 1 <= job.resolution_percentage <= 100:
        errors.append("Resolution scale must be between 1 and 100 percent.")
    if not job.output_path.strip():
        errors.append("Choose an output path.")
    if job.schedule_enabled:
        try:
            scheduled = parse_local(job.scheduled_at)
            if saving and scheduled <= now:
                warnings.append("Scheduled time is in the past. Automatic start is held; use Run Now or edit the schedule.")
        except (ValueError, TypeError):
            errors.append("Use local date/time: YYYY-MM-DD HH:MM:SS.")
    return errors, warnings


def validate_output(path):
    """Inspect the nearest existing ancestor, without writing a probe file."""
    try:
        if '\x00' in path:
            return ["Output path contains an invalid character."]
        parent = Path(path).parent
        while not parent.exists() and parent != parent.parent:
            parent = parent.parent
        if not parent.is_dir():
            return ["Output parent is not a folder."]
    except (OSError, ValueError) as exc:
        return [f"Cannot access output folder: {exc}"]
    return []
