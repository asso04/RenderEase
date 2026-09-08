"""Blender integration regression checks, with every render invocation mocked."""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import renderease
from renderease import properties, handlers, scheduler, render_executor as executor
from renderease.queue_manager import runtime


def forbid_real_render(*args, **kwargs):
    raise AssertionError('Real rendering is forbidden in this adapter suite.')


executor.invoke_render = forbid_real_render


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print('PASS:', message, flush=True)


renderease.register()
with tempfile.TemporaryDirectory(prefix='renderease-adapters-') as directory:
    def add(name='job', **kwargs):
        args = dict(name=name, scene_name=bpy.context.scene.name, frame_start=1, frame_end=1,
                    resolution_x=32, resolution_y=24, output_path=str(Path(directory) / name))
        args.update(kwargs)
        result = bpy.ops.renderease.edit('EXEC_DEFAULT', **args)
        check(result == {'FINISHED'}, 'add definition: ' + name)
        return properties.get_store().jobs[-1]

    item = add()
    job_id = item.id
    copied_scene = bpy.context.scene.copy()
    check(len(properties.get_store().jobs) == 1, 'scene duplication does not clone queue')
    bpy.data.scenes.remove(copied_scene)
    check(properties.get_store().jobs[0].id == job_id, 'scene removal preserves queue')
    path = str(Path(directory) / 'persist.blend')
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    item = properties.get_store().jobs[0]
    check(item.id == job_id, 'Text native properties persist across save/load')
    check(all(getattr(bpy.app.handlers, name).count(callback) == 1 for name, callback in handlers.HANDLERS),
          'all handlers survive load exactly once')
    check(bpy.app.timers.is_registered(scheduler.tick), 'persistent timer survives load')

    # Mock only Blender operator invocation, retaining real validation/settings/state/handlers.
    def rendered(*args, **kwargs):
        handlers.complete(bpy.data.scenes[kwargs['scene']])
        return {'FINISHED'}

    with patch.object(executor, 'invoke_render', side_effect=rendered) as render:
        add('animation', render_type='ANIMATION', frame_end=3)
        runtime.running = True
        scheduler.tick()
        scheduler.tick()
        scheduler.tick()
        check(render.call_count == 2, 'two mocked renders dispatched in queue order')
        check(render.call_args_list[0].kwargs['write_still'] is True, 'still writes output')
        check(render.call_args_list[1].kwargs['animation'] is True, 'animation invocation configured')
        check(all(j.status == 'COMPLETED' for j in properties.get_store().jobs), 'completion signals finalize both jobs')
        check(not runtime.running and not runtime.active_id, 'queue stops after mocked completion')

    # Cancellation callback leaves the job cancelled, not completed.
    cancelled = add('cancelled')
    def cancel_render(*args, **kwargs):
        handlers.cancel(bpy.data.scenes[kwargs['scene']])
        return {'FINISHED'}
    with patch.object(executor, 'invoke_render', side_effect=cancel_render):
        executor.start(cancelled)
        scheduler.tick()
    check(cancelled.status == 'CANCELLED' and runtime.paused, 'native cancellation stops automatic queue')

    failed = add('failure')
    original_path = bpy.context.scene.render.filepath
    with patch.object(executor, 'invoke_render', side_effect=RuntimeError('test engine error')):
        executor.start(failed)
        scheduler.tick()
    check(failed.status == 'FAILED' and 'test engine error' in failed.error_message,
          'operator failure finalized with readable error')
    check(bpy.context.scene.render.filepath == original_path and not runtime.active_id,
          'failed render releases lock and restores settings')

    held = add('held', schedule_enabled=True, scheduled_at='2000-01-01 00:00:00')
    check(held.schedule_held and held.status == 'SCHEDULED', 'past schedule saved visibly held')
    future = add('future', schedule_enabled=True,
                 scheduled_at=(datetime.now() + timedelta(minutes=2)).isoformat())
    runtime.__init__()
    with patch.object(executor, 'start') as start:
        scheduler.last_scan = 0
        scheduler.tick()
        check(start.call_count == 0, 'held and future jobs not dispatched')
        future.scheduled_at = (datetime.now() - timedelta(seconds=1)).isoformat()
        scheduler.last_scan = 0
        scheduler.tick()
        check(start.call_count == 1, 'timer dispatches due schedule')
    executor.recover()
    check(future.schedule_held, 'overdue schedule held on recovery')

    # An active render prevents job execution and blocks mutation operators.
    runtime.active_id = 'existing-render'
    try:
        try:
            executor.start(held)
            raise AssertionError('Concurrent render accepted')
        except RuntimeError:
            pass
        check(bpy.ops.renderease.action(action='REMOVE') == {'CANCELLED'}, 'active render locks queue edits')
    finally:
        runtime.active_id = ''

    for _ in range(52):
        executor.record(failed)
    check(len(properties.get_store().history) == 50, 'history bounded')
    renderease.unregister()
    renderease.unregister()
    check(not hasattr(bpy.types.Text, 'renderease'), 'property registration removed')
    check(not bpy.app.timers.is_registered(scheduler.tick), 'timer removed')
    check(all(callback not in getattr(bpy.app.handlers, name) for name, callback in handlers.HANDLERS), 'handlers removed')
    renderease.register()
    renderease.register()
    check(len(properties.get_store().jobs) == 6, 'enable cycle preserves all definitions')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    check(properties.get_store() is None, 'new file starts with empty queue')
    renderease.unregister()

print('ADAPTERS OK | Blender', bpy.app.version_string, '| actual renders=0', flush=True)
