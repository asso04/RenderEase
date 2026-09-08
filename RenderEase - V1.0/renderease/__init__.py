"""RenderEase legacy add-on package (Blender 4.2+ target)."""
bl_info = {
    'name': 'RenderEase', 'author': 'RenderEase contributors',
    'version': (0, 1, 0), 'blender': (4, 2, 0),
    'location': '3D View > Sidebar > RenderEase',
    'description': 'Queue and schedule local renders without babysitting your machine',
    'category': 'Render',
}

_registered = False


def register():
    global _registered
    if _registered:
        return
    import bpy
    from . import properties, operators, panels, handlers, scheduler, render_executor
    classes = properties.CLASSES + operators.CLASSES + panels.CLASSES
    done = []
    try:
        for cls in classes:
            bpy.utils.register_class(cls)
            done.append(cls)
        bpy.types.Text.renderease = bpy.props.PointerProperty(type=properties.QueueData)
        handlers.register()
        scheduler.register()
        _registered = True
    except Exception:
        scheduler.unregister()
        handlers.unregister()
        if hasattr(bpy.types.Text, 'renderease'):
            del bpy.types.Text.renderease
        for cls in reversed(done):
            bpy.utils.unregister_class(cls)
        raise


def unregister():
    global _registered
    if not _registered:
        return
    import bpy
    from . import properties, operators, panels, handlers, scheduler, render_executor
    scheduler.unregister()
    handlers.unregister()
    render_executor.abandon('Add-on disabled during render; result was not tracked.')
    del bpy.types.Text.renderease
    for cls in reversed(properties.CLASSES + operators.CLASSES + panels.CLASSES):
        bpy.utils.unregister_class(cls)
    _registered = False
