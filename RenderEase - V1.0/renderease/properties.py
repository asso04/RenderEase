"""File data lives in native properties on a dedicated Text datablock."""
import bpy
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty, CollectionProperty

STATES = ('PENDING', 'SCHEDULED', 'RENDERING', 'COMPLETED', 'FAILED', 'CANCELLED')
FIELDS = ('name', 'scene_name', 'render_type', 'frame_start', 'frame_end',
          'resolution_x', 'resolution_y', 'resolution_percentage', 'output_path',
          'schedule_enabled', 'scheduled_at')


def definition_properties():
    return dict(
        name=StringProperty(name="Job name", default="Render job"),
        scene_name=StringProperty(name="Scene"),
        render_type=EnumProperty(name="Render", items=[(v, v.title(), '') for v in ('STILL', 'ANIMATION')]),
        frame_start=IntProperty(name="Start / still frame", default=1, min=0, max=1048574),
        frame_end=IntProperty(name="End", default=1, min=0, max=1048574),
        resolution_x=IntProperty(name="Width", default=1920, min=4, max=65536),
        resolution_y=IntProperty(name="Height", default=1080, min=4, max=65536),
        resolution_percentage=IntProperty(name="Scale %", default=100, min=1, max=100),
        output_path=StringProperty(name="Output", subtype='FILE_PATH', description="Blender output filename or animation prefix; directories are created at render start"),
        schedule_enabled=BoolProperty(name="Schedule", description="Starts only while Blender is open; local computer time"),
        scheduled_at=StringProperty(name="Local date/time", description="YYYY-MM-DD HH:MM:SS, without timezone offset"),
    )


class RenderJob(bpy.types.PropertyGroup):
    __annotations__ = definition_properties()
    id: StringProperty()
    status: EnumProperty(items=[(s, s.title(), '') for s in STATES], default='PENDING')
    created_at: StringProperty()
    started_at: StringProperty()
    completed_at: StringProperty()
    error_message: StringProperty()
    schedule_held: BoolProperty(default=False)


class HistoryEntry(bpy.types.PropertyGroup):
    job_id: StringProperty()
    name: StringProperty()
    status: StringProperty()
    started_at: StringProperty()
    completed_at: StringProperty()
    error_message: StringProperty()


class QueueData(bpy.types.PropertyGroup):
    owner: BoolProperty(default=False)
    jobs: CollectionProperty(type=RenderJob)
    selected: IntProperty(default=0)
    history: CollectionProperty(type=HistoryEntry)


def get_store(create=False):
    for text in bpy.data.texts:
        if text.renderease.owner:
            return text.renderease
    if create:
        text = bpy.data.texts.new('.RenderEase Queue')
        text.use_fake_user = True
        text.renderease.owner = True
        return text.renderease
    return None


CLASSES = (RenderJob, HistoryEntry, QueueData)
