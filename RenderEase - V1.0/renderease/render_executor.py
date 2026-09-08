"""Blender execution adapter. Session state never resumes a saved render."""
from datetime import datetime
from pathlib import Path
import bpy
from .properties import get_store
from .queue_manager import runtime
from .state_machine import transition
from .utils import now_iso, log
from .validation import validate, validate_output

RENDER_FIELDS = ('resolution_x', 'resolution_y', 'resolution_percentage', 'filepath')
SCENE_FIELDS = ('frame_start', 'frame_end', 'frame_step', 'frame_current')


def invoke_render(*args, **kwargs):
    """Small adapter boundary so tests never patch Blender's dynamic ops proxy."""
    return bpy.ops.render.render(*args, **kwargs)


def notify(message):
    runtime.message = message
    log.info('notification=%r', message)
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()


def record(job):
    store = get_store()
    entry = store.history.add()
    entry.job_id = job.id
    for key in ('name', 'status', 'started_at', 'completed_at', 'error_message'):
        setattr(entry, key, getattr(job, key))
    while len(store.history) > 50:
        store.history.remove(0)


def restore():
    snapshot = runtime.snapshot
    runtime.snapshot = None
    if not snapshot:
        return
    scene = bpy.data.scenes.get(snapshot['scene'])
    if scene:
        for key, value in snapshot['render'].items():
            setattr(scene.render, key, value)
        for key, value in snapshot['settings'].items():
            if key == 'frame_current':
                scene.frame_set(value)
            else:
                setattr(scene, key, value)
    window = snapshot['window']
    original = bpy.data.scenes.get(snapshot['window_scene'])
    if window and original and any(w == window for w in bpy.context.window_manager.windows):
        window.scene = original


def finish(status, error=''):
    store = get_store()
    job = next((j for j in store.jobs if j.id == runtime.active_id), None) if store else None
    runtime.active_id, runtime.outcome = '', None
    try:
        restore()
    except Exception as exc:
        log.exception('restore_failure')
        status, error = 'FAILED', f'Could not restore scene settings: {exc}'
    if job:
        transition(job, status)
        job.completed_at = now_iso()
        job.error_message = error
        record(job)
        notify(f'{job.name}: {status.lower()}' + (f' — {error}' if error else ''))
    if status != 'COMPLETED':
        runtime.stop(failed=status == 'FAILED')


def start(job):
    if runtime.active_id or bpy.app.is_job_running('RENDER'):
        raise RuntimeError('Another render is already active.')
    if job.status not in ('PENDING', 'SCHEDULED'):
        raise ValueError('Reset this job before running it again.')
    errors, _ = validate(job, bpy.data.scenes.keys())
    if job.output_path.startswith('//') and not bpy.data.filepath:
        errors.append('Save the .blend file before using a relative output path.')
    path = bpy.path.abspath(job.output_path)
    errors.extend(validate_output(path))
    scene = bpy.data.scenes.get(job.scene_name)
    if scene and not scene.camera:
        errors.append('Assign a render camera to the scene.')
    if scene and job.render_type == 'STILL' and scene.render.image_settings.file_format in {'FFMPEG', 'AVI_JPEG', 'AVI_RAW'}:
        errors.append('Still renders require an image output format in scene Output Properties.')
    if errors:
        transition(job, 'FAILED')
        job.error_message = ' '.join(errors)
        job.completed_at = now_iso()
        record(job)
        notify(job.error_message)
        log.error('validation_failure job_id=%s error=%s', job.id, job.error_message)
        runtime.stop(failed=True)
        return False
    runtime.active_id = job.id
    runtime.outcome = None
    runtime.snapshot = dict(scene=scene.name,
        window=bpy.context.window,
        window_scene=bpy.context.window.scene.name if bpy.context.window else '',
        render={k: getattr(scene.render, k) for k in RENDER_FIELDS},
        settings={k: getattr(scene, k) for k in SCENE_FIELDS})
    transition(job, 'RENDERING')
    job.started_at, job.completed_at, job.error_message = now_iso(), '', ''
    try:
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError(f'Output folder does not exist and could not be created: {exc}') from exc
        if bpy.context.window:
            bpy.context.window.scene = scene
        for key in RENDER_FIELDS[:-1]:
            setattr(scene.render, key, getattr(job, key))
        scene.render.filepath = path
        scene.frame_start, scene.frame_end, scene.frame_step = job.frame_start, job.frame_end, 1
        scene.frame_set(job.frame_start)
        notify(f'Render started: {job.name}')
        # Background execution is synchronous, used by the minimal integration test.
        mode = 'EXEC_DEFAULT' if bpy.app.background else 'INVOKE_DEFAULT'
        result = invoke_render(mode, animation=job.render_type == 'ANIMATION',
                                       write_still=job.render_type == 'STILL', scene=scene.name)
        if 'CANCELLED' in result:
            runtime.outcome = ('FAILED', 'Blender could not start the render.')
    except Exception as exc:
        log.exception('render_failure job_id=%s', job.id)
        runtime.outcome = ('FAILED', f'Render failed: {exc}')
    return True


def abandon(message):
    if runtime.active_id:
        if bpy.app.is_job_running('RENDER'):
            # Do not change render settings while Blender is using them.
            runtime.snapshot = None
        finish('FAILED', message)
    runtime.__init__()


def recover():
    runtime.__init__()
    store = get_store()
    if store is None:
        return
    for job in store.jobs:
        if job.status == 'RENDERING':
            transition(job, 'FAILED')
            job.error_message = 'Previous render was interrupted. Reset and run explicitly.'
            job.completed_at = now_iso()
            record(job)
        if job.schedule_enabled and job.status in ('PENDING', 'SCHEDULED'):
            errors, warnings = validate(job, bpy.data.scenes.keys(), saving=True, now=datetime.now())
            job.schedule_held = bool(errors or warnings)
            if errors or warnings:
                job.error_message = ' '.join(errors + warnings)
    notify('Ready. Overdue saved schedules are held; use Run Now or edit their date.')
