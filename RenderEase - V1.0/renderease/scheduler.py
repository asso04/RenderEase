"""One timer; completion is finalized after Blender releases its render job."""
import time
import bpy
from .queue_manager import runtime, next_job
from .utils import log

enabled = False
last_scan = 0.0
recovery_pending = False


def ensure_ready():
    """Access file data only after Blender's restricted registration context ends."""
    global recovery_pending
    if recovery_pending:
        from .render_executor import recover
        recover()
        recovery_pending = False


def tick():
    global last_scan
    if not enabled:
        return None
    from . import render_executor as executor
    from .properties import get_store
    try:
        ensure_ready()
        if bpy.app.is_job_running('RENDER'):
            return 0.5
        if runtime.active_id:
            if runtime.outcome:
                executor.finish(*runtime.outcome)
            else:
                executor.finish('FAILED', 'Render ended without a completion callback.')
        if runtime.paused:
            return 1.0
        if not runtime.running and time.monotonic() - last_scan < 10:
            return 1.0
        last_scan = time.monotonic()
        store = get_store()
        if store is None:
            return 1.0
        job = next_job(store.jobs, scheduled_only=not runtime.running)
        if job:
            if job.schedule_enabled:
                log.info('scheduler_trigger job_id=%s', job.id)
            executor.start(job)
        elif runtime.running:
            runtime.running = False
            executor.notify('Queue completed; future scheduled jobs remain armed.')
    except Exception as exc:
        log.exception('scheduler_failure')
        if runtime.active_id:
            executor.finish('FAILED', str(exc))
        runtime.message = f'RenderEase stopped: {exc}'
        runtime.stop(failed=True)
    return 0.5


def register():
    global enabled, last_scan, recovery_pending
    enabled, last_scan = True, 0.0
    recovery_pending = True
    if not bpy.app.timers.is_registered(tick):
        bpy.app.timers.register(tick, first_interval=1.0, persistent=True)


def unregister():
    global enabled, recovery_pending
    enabled = False
    recovery_pending = False
    if bpy.app.timers.is_registered(tick):
        bpy.app.timers.unregister(tick)
