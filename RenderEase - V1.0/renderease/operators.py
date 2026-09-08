"""Operators edit drafts and commit only validated definitions."""
from datetime import datetime, timedelta
from uuid import uuid4
import bpy
from bpy.props import StringProperty, EnumProperty
from .properties import get_store, definition_properties, FIELDS
from .queue_manager import runtime, next_job
from .state_machine import transition
from .validation import validate
from .utils import now_iso
from . import render_executor as executor


def busy():
    return bool(runtime.active_id) or bpy.app.is_job_running('RENDER')


def selected():
    store = get_store()
    if store and 0 <= store.selected < len(store.jobs):
        return store.jobs[store.selected]
    return None


def draw_definition(layout, draft):
    layout.prop(draft, 'name')
    layout.prop_search(draft, 'scene_name', bpy.data, 'scenes')
    layout.prop(draft, 'render_type', expand=True)
    row = layout.row(align=True)
    row.prop(draft, 'frame_start')
    if draft.render_type == 'ANIMATION':
        row.prop(draft, 'frame_end')
    row = layout.row(align=True)
    row.prop(draft, 'resolution_x')
    row.prop(draft, 'resolution_y')
    layout.prop(draft, 'resolution_percentage')
    layout.prop(draft, 'output_path')
    layout.prop(draft, 'schedule_enabled')
    if draft.schedule_enabled:
        layout.prop(draft, 'scheduled_at')
        layout.label(text='YYYY-MM-DD HH:MM:SS • Blender must stay open', icon='TIME')


class RE_OT_edit(bpy.types.Operator):
    bl_idname = 'renderease.edit'
    bl_label = 'Configure Render Job'
    bl_description = 'Create or edit a job; past schedules are saved on hold'
    __annotations__ = definition_properties()
    job_id: StringProperty(default='')

    @classmethod
    def poll(cls, context):
        return not busy() and not runtime.running

    def invoke(self, context, event):
        from .scheduler import ensure_ready
        ensure_ready()
        if self.job_id:
            store = get_store()
            job = next((j for j in store.jobs if j.id == self.job_id), None) if store else None
            if job is None or job.status not in ('PENDING', 'SCHEDULED'):
                self.report({'ERROR'}, 'Reset the job before editing it.')
                return {'CANCELLED'}
            for key in FIELDS:
                setattr(self, key, getattr(job, key))
        else:
            scene = context.scene
            self.scene_name = scene.name
            self.frame_start, self.frame_end = scene.frame_current, max(scene.frame_current, scene.frame_end)
            self.resolution_x, self.resolution_y = scene.render.resolution_x, scene.render.resolution_y
            self.resolution_percentage = min(scene.render.resolution_percentage, 100)
            self.output_path = scene.render.filepath
            self.scheduled_at = (datetime.now() + timedelta(hours=1)).isoformat(sep=' ', timespec='seconds')
        return context.window_manager.invoke_props_dialog(self, width=460)

    def draw(self, context):
        draw_definition(self.layout, self)
        errors, warnings = validate(self, bpy.data.scenes.keys(), saving=True)
        for message in errors + warnings:
            self.layout.label(text=message, icon='ERROR')

    def execute(self, context):
        from .scheduler import ensure_ready
        ensure_ready()
        if busy() or runtime.running:
            return {'CANCELLED'}
        if self.render_type == 'STILL':
            self.frame_end = self.frame_start
        errors, warnings = validate(self, bpy.data.scenes.keys(), saving=True)
        if errors:
            self.report({'ERROR'}, ' '.join(errors))
            return {'CANCELLED'}
        store = get_store(create=True)
        job = next((j for j in store.jobs if j.id == self.job_id), None)
        if self.job_id and (job is None or job.status not in ('PENDING', 'SCHEDULED')):
            self.report({'ERROR'}, 'Job changed; reopen the editor.')
            return {'CANCELLED'}
        if job is None:
            job = store.jobs.add()
            job.id, job.created_at = str(uuid4()), now_iso()
            store.selected = len(store.jobs) - 1
        for key in FIELDS:
            setattr(job, key, getattr(self, key))
        target = 'SCHEDULED' if job.schedule_enabled else 'PENDING'
        if job.status != target:
            transition(job, target)
        job.schedule_held = bool(warnings)
        job.error_message = ' '.join(warnings)
        if warnings:
            self.report({'WARNING'}, job.error_message)
        return {'FINISHED'}


class RE_OT_action(bpy.types.Operator):
    bl_idname = 'renderease.action'
    bl_label = 'RenderEase Queue Action'
    bl_description = 'Run, reorder or manage the selected job; cancel stops future jobs, Esc stops the active render'
    action: EnumProperty(items=[(x, x.title(), '') for x in
        ('RUN', 'NEXT', 'QUEUE', 'CANCEL', 'RESUME', 'REMOVE', 'DUPLICATE', 'UP', 'DOWN', 'RESET')])

    def execute(self, context):
        from .scheduler import ensure_ready
        ensure_ready()
        store, job = get_store(), selected()
        if self.action == 'CANCEL':
            runtime.stop()
            executor.notify('Queue cancelled. Use Esc in Blender to cancel the active render.')
            self.report({'INFO'}, runtime.message)
            return {'FINISHED'}
        if busy():
            self.report({'WARNING'}, 'Wait for the active render to finish.')
            return {'CANCELLED'}
        if self.action == 'RESUME':
            runtime.paused = False
            executor.notify('Automatic scheduling resumed.')
            return {'FINISHED'}
        if self.action in ('QUEUE', 'NEXT', 'RUN'):
            if self.action == 'QUEUE':
                runtime.running, runtime.paused = True, False
                executor.notify('Queue started.')
                self.report({'INFO'}, runtime.message)
                return {'FINISHED'}
            candidate = job if self.action == 'RUN' else next_job(store.jobs) if store else None
            if candidate is None or candidate.status not in ('PENDING', 'SCHEDULED'):
                self.report({'WARNING'}, 'No eligible job. Reset finished jobs before running again.')
                return {'CANCELLED'}
            runtime.running = False
            executor.start(candidate)
            self.report({'INFO'}, runtime.message)
            return {'FINISHED'}
        if runtime.running or job is None:
            return {'CANCELLED'}
        index = store.selected
        if self.action == 'REMOVE':
            store.jobs.remove(index)
            store.selected = max(0, min(index, len(store.jobs) - 1))
        elif self.action == 'DUPLICATE':
            copy = store.jobs.add()
            for key in FIELDS:
                setattr(copy, key, getattr(job, key))
            copy.name += ' copy'
            copy.id, copy.created_at = str(uuid4()), now_iso()
            # Duplicates require explicit scheduling to avoid surprise overnight renders.
            copy.schedule_enabled = False
            store.selected = len(store.jobs) - 1
        elif self.action in ('UP', 'DOWN'):
            target = index + (-1 if self.action == 'UP' else 1)
            if 0 <= target < len(store.jobs):
                store.jobs.move(index, target)
                store.selected = target
        elif self.action == 'RESET':
            if job.status not in ('COMPLETED', 'FAILED', 'CANCELLED'):
                return {'CANCELLED'}
            transition(job, 'PENDING')
            job.schedule_enabled, job.schedule_held = False, False
            job.started_at = job.completed_at = job.error_message = ''
        return {'FINISHED'}


CLASSES = (RE_OT_edit, RE_OT_action)
