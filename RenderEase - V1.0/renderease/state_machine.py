"""Conservative transitions, shared by execution and editing."""
from .utils import log

TRANSITIONS = {
    'PENDING': {'SCHEDULED', 'RENDERING', 'CANCELLED', 'FAILED'},
    'SCHEDULED': {'PENDING', 'RENDERING', 'CANCELLED', 'FAILED'},
    'RENDERING': {'COMPLETED', 'FAILED', 'CANCELLED'},
    'COMPLETED': {'PENDING'}, 'FAILED': {'PENDING'}, 'CANCELLED': {'PENDING'},
}


def transition(job, target):
    if target not in TRANSITIONS.get(job.status, set()):
        raise ValueError(f"Cannot change {job.status} to {target}.")
    log.info("job_id=%s name=%r transition=%s->%s", job.id, job.name, job.status, target)
    job.status = target
