"""Local time and logging helpers; no Blender dependency."""
from datetime import datetime
import logging

log = logging.getLogger("renderease")
if not log.handlers:
    log.addHandler(logging.StreamHandler())
log.setLevel(logging.INFO)


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def parse_local(value):
    result = datetime.fromisoformat(value.strip())
    if result.tzinfo is not None:
        raise ValueError("Use local date/time without a timezone offset.")
    return result
