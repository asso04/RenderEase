"""Callbacks signal outcomes only: no scene mutation on render threads."""
import bpy
from bpy.app.handlers import persistent
from .queue_manager import runtime


@persistent
def complete(scene, *args):
    if runtime.active_id and runtime.snapshot and scene.name == runtime.snapshot['scene']:
        runtime.outcome = ('COMPLETED', '')


@persistent
def cancel(scene, *args):
    if runtime.active_id and runtime.snapshot and scene.name == runtime.snapshot['scene']:
        runtime.outcome = ('CANCELLED', 'Render cancelled in Blender.')


@persistent
def before_load(*args):
    from .render_executor import abandon
    abandon('File or undo state changed during a render.')


@persistent
def after_load(*args):
    from . import scheduler
    from .render_executor import recover
    recover()
    scheduler.recovery_pending = False


HANDLERS = [('render_complete', complete), ('render_cancel', cancel),
            ('load_pre', before_load), ('load_post', after_load),
            ('undo_pre', before_load), ('undo_post', after_load),
            ('redo_pre', before_load), ('redo_post', after_load)]


def register():
    for name, callback in HANDLERS:
        collection = getattr(bpy.app.handlers, name)
        if callback not in collection:
            collection.append(callback)


def unregister():
    for name, callback in HANDLERS:
        collection = getattr(bpy.app.handlers, name)
        while callback in collection:
            collection.remove(callback)
