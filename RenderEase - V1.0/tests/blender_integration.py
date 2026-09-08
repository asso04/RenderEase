"""Run with factory-startup, background Blender. Two tiny CPU stills only."""
import sys
from pathlib import Path
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bpy
import renderease
from renderease import properties, handlers, scheduler, render_executor as executor
from renderease.queue_manager import runtime


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print('PASS:', message, flush=True)


renderease.register()
renderease.register()
check(scheduler.enabled and bpy.app.timers.is_registered(scheduler.tick), 'timer registered once')
for name, callback in handlers.HANDLERS:
    check(getattr(bpy.app.handlers, name).count(callback) == 1, name + ' handler unique')

with tempfile.TemporaryDirectory(prefix='renderease-test-') as temporary:
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 2
    scene.render.image_settings.file_format = 'PNG'
    scene.use_nodes = False
    scene.render.resolution_x = 32
    scene.render.resolution_y = 24
    scene.render.resolution_percentage = 100
    original_path = scene.render.filepath

    def add(name, scene_name=None):
        result = bpy.ops.renderease.edit('EXEC_DEFAULT', name=name, scene_name=scene_name or scene.name,
            frame_start=1, frame_end=1, resolution_x=32, resolution_y=24,
            output_path=str(Path(temporary) / (name + '.png')))
        check(result == {'FINISHED'}, 'job added: ' + name)
        return properties.get_store().jobs[-1]

    first = add('first')
    first_id = first.id
    bpy.ops.renderease.action(action='DUPLICATE')
    store = properties.get_store()
    check(len(store.jobs) == 2 and store.jobs[1].id != first_id, 'duplicate has fresh ID')
    bpy.ops.renderease.action(action='UP')
    check(store.jobs[1].id == first_id, 'move preserves order')
    bpy.ops.renderease.action(action='REMOVE')

    blend = str(Path(temporary) / 'queue.blend')
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    bpy.ops.wm.open_mainfile(filepath=blend)
    scene = bpy.context.scene
    store = properties.get_store()
    check(len(store.jobs) == 1 and store.jobs[0].id == first_id, 'queue persists across actual file load')
    for name, callback in handlers.HANDLERS:
        check(getattr(bpy.app.handlers, name).count(callback) == 1, 'handler survives load: ' + name)
    check(bpy.app.timers.is_registered(scheduler.tick), 'timer survives file load')

    # Invalid execution must stop both queue continuation and independent schedules.
    store.jobs[0].scene_name = 'missing scene'
    runtime.running = True
    check(not executor.start(store.jobs[0]), 'missing scene rejected without rendering')
    check(store.jobs[0].status == 'FAILED' and not runtime.running and runtime.paused,
          'validation failure stops all automatic work')
    bpy.ops.renderease.action(action='RESET')
    store.jobs[0].scene_name = scene.name
    runtime.__init__()

    # Scheduler adapter tests use fake execution; no waiting and no renders.
    scheduled = store.jobs[0]
    scheduled.schedule_enabled = True
    scheduled.status = 'SCHEDULED'
    scheduled.scheduled_at = (datetime.now() + timedelta(minutes=1)).isoformat()
    with patch.object(executor, 'start') as start:
        scheduler.last_scan = 0
        scheduler.tick()
        check(start.call_count == 0, 'future scheduled job waits')
        scheduled.scheduled_at = (datetime.now() - timedelta(seconds=1)).isoformat()
        scheduler.last_scan = 0
        scheduler.tick()
        check(start.call_count == 1, 'due scheduled job dispatched by timer')
        runtime.stop()
        scheduler.last_scan = 0
        scheduler.tick()
        check(start.call_count == 1, 'cancel pauses scheduled dispatch')
    executor.recover()
    check(scheduled.schedule_held, 'overdue loaded schedule held')
    scheduled.schedule_enabled, scheduled.schedule_held = False, False
    scheduled.status = 'PENDING'
    scheduled.error_message = ''

    # Use a second scene to verify scene activation and restoration.
    other = scene.copy()
    other.name = 'Second Scene'
    add('second', other.name)
    check(len(scene.objects) == 3 and scene.camera is not None, 'factory cube, camera, light only')
    check(all(obj.type != 'VOLUME' and not obj.modifiers for obj in scene.objects), 'no heavy modifiers or volumes')
    for render_scene in (scene, other):
        check(render_scene.cycles.samples == 1 and render_scene.cycles.device == 'CPU'
              and not render_scene.cycles.use_denoising and not render_scene.use_nodes,
              'CPU, one sample, no denoising or compositor')
    for item in store.jobs:
        errors, _ = executor.validate(item, bpy.data.scenes.keys())
        check(not errors and item.resolution_x <= 320 and item.resolution_y <= 240
              and item.resolution_percentage <= 100 and item.frame_start == item.frame_end == 1,
              'preflight: tiny one-frame valid job')
    bpy.ops.renderease.action(action='QUEUE')
    scheduler.tick()  # render first, synchronous background invocation
    check(store.jobs[0].status == 'RENDERING', 'first job enters rendering')
    scheduler.tick()  # finalize first and render second
    check(store.jobs[0].status == 'COMPLETED' and store.jobs[1].status == 'RENDERING', 'queue continues')
    scheduler.tick()  # finalize second, stop queue
    check(all(j.status == 'COMPLETED' and j.completed_at for j in store.jobs), 'both completion callbacks recorded')
    check(not runtime.running and not runtime.active_id, 'queue stops cleanly')
    check(all((Path(temporary) / (name + '.png')).is_file() for name in ('first', 'second')), 'both PNG outputs exist')
    check(scene.render.filepath == original_path and bpy.context.window.scene == scene,
          'render settings and active scene restored')
    # History capacity without additional renders.
    for _ in range(52):
        executor.record(store.jobs[0])
    check(len(store.history) == 50, 'history bounded to 50')

    renderease.unregister()
    renderease.unregister()
    check(not bpy.app.timers.is_registered(scheduler.tick), 'timer removed')
    check(all(callback not in getattr(bpy.app.handlers, name) for name, callback in handlers.HANDLERS), 'handlers removed')
    renderease.register()
    check(len(properties.get_store().jobs) == 2, 'data survives disable and enable')
    renderease.unregister()
    # Release the temporary blend before TemporaryDirectory cleanup.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    renderease.register()
    check(properties.get_store() is None, 'file without add-on data loads safely')
    renderease.unregister()

print('INTEGRATION OK | Blender', bpy.app.version_string,
      '| actual renders=2 | 32x24 | 1 frame each | CYCLES CPU | GPU rendering=no', flush=True)
