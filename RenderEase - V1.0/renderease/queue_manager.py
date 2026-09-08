"""Pure queue selection and session state, independent of Blender UI."""
from datetime import datetime
from .utils import parse_local


def eligible(job, now, scheduled_only=False):
    if job.status not in ('PENDING', 'SCHEDULED'):
        return False
    if job.schedule_enabled:
        if job.schedule_held:
            return False
        try:
            return parse_local(job.scheduled_at) <= now
        except ValueError:
            # Selected for execution validation so malformed data visibly fails.
            return True
    return not scheduled_only


def next_job(jobs, now=None, scheduled_only=False):
    now = now or datetime.now()
    return next((job for job in jobs if eligible(job, now, scheduled_only)), None)


class Runtime:
    def __init__(self):
        self.running = False
        self.paused = False
        self.active_id = ''
        self.outcome = None
        self.message = 'Ready'
        self.last_error = ''
        self.snapshot = None

    def stop(self, failed=False):
        self.running = False
        self.paused = True
        if failed:
            self.last_error = self.message


runtime = Runtime()
