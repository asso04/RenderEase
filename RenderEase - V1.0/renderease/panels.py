"""Compact Blender-native sidebar, with read-only persisted job details."""
import bpy
from .properties import get_store
from .operators import selected, busy, draw_definition
from .queue_manager import runtime


def button(layout, text, action, enabled=True, icon='NONE'):
    row = layout.row(align=True)
    row.enabled = enabled
    row.operator('renderease.action', text=text, icon=icon).action = action


class RE_UL_jobs(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.name, icon='TIME' if item.schedule_enabled else 'RENDER_STILL')
        row.label(text=item.scene_name)
        row.label(text='HELD' if item.schedule_held else item.status)


class RE_PT_main(bpy.types.Panel):
    bl_label = 'RenderEase'
    bl_idname = 'RE_PT_main'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RenderEase'

    def draw(self, context):
        layout = self.layout
        store, job = get_store(), selected()
        idle = not busy()
        editable = idle and not runtime.running
        row = layout.row(align=True)
        row.enabled = editable
        row.operator('renderease.edit', text='Add Job', icon='ADD').job_id = ''
        row = layout.row(align=True)
        button(row, 'Run Queue', 'QUEUE', idle and bool(store and store.jobs))
        button(row, 'Run Next', 'NEXT', idle and bool(store and store.jobs))
        button(layout, 'Cancel Queue', 'CANCEL', not runtime.paused)
        if runtime.paused:
            button(layout, 'Resume Scheduling', 'RESUME', idle)
        if store is None or not store.jobs:
            layout.label(text='Add a job to queue your first render.', icon='INFO')
        else:
            layout.template_list('RE_UL_jobs', '', store, 'jobs', store, 'selected', rows=4)
        if job:
            row = layout.row(align=True)
            button(row, 'Run Now', 'RUN', idle and job.status in ('PENDING', 'SCHEDULED'))
            edit = row.row()
            edit.enabled = editable and job.status in ('PENDING', 'SCHEDULED')
            edit.operator('renderease.edit', text='Edit').job_id = job.id
            button(row, '', 'DUPLICATE', editable, 'DUPLICATE')
            row = layout.row(align=True)
            button(row, '', 'UP', editable and store.selected > 0, 'TRIA_UP')
            button(row, '', 'DOWN', editable and store.selected < len(store.jobs) - 1, 'TRIA_DOWN')
            button(row, 'Remove', 'REMOVE', editable, 'X')
            button(row, 'Reset', 'RESET', editable and job.status in ('FAILED', 'COMPLETED', 'CANCELLED'))
            box = layout.box()
            box.label(text='Job details (use Edit to change)')
            details = box.column()
            details.enabled = False
            draw_definition(details, job)
            for key in ('created_at', 'started_at', 'completed_at'):
                value = getattr(job, key)
                if value:
                    box.label(text=f'{key.replace("_at", "").title()}: {value}')
            if job.error_message:
                box.label(text=job.error_message, icon='ERROR')
        box = layout.box()
        box.label(text='Queue running' if runtime.running else 'Queue not running')
        box.label(text=runtime.message, icon='INFO')
        if runtime.active_id and store:
            active = next((j for j in store.jobs if j.id == runtime.active_id), None)
            if active:
                box.label(text=f'Rendering: {active.name}', icon='RENDER_STILL')
        if store:
            scheduled = [j for j in store.jobs if j.status == 'SCHEDULED' and not j.schedule_held]
            if scheduled:
                upcoming = min(scheduled, key=lambda j: j.scheduled_at)
                box.label(text=f'Next schedule: {upcoming.name} · {upcoming.scheduled_at}')
        if runtime.last_error:
            box.label(text=runtime.last_error, icon='ERROR')


class RE_PT_history(bpy.types.Panel):
    bl_label = 'Render History (last 50)'
    bl_idname = 'RE_PT_history'
    bl_parent_id = 'RE_PT_main'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RenderEase'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        store = get_store()
        if store is None or not store.history:
            self.layout.label(text='No render history yet.')
            return
        for entry in reversed(list(store.history)):
            box = self.layout.box()
            box.label(text=f'{entry.name} · {entry.status}')
            box.label(text=f'{entry.started_at} → {entry.completed_at}')
            if entry.error_message:
                box.label(text=entry.error_message, icon='ERROR')


CLASSES = (RE_UL_jobs, RE_PT_main, RE_PT_history)
