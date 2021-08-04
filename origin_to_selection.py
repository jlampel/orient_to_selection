import bpy
from bpy.types import (Operator)

class OBJECT_OT_origin_to_selection(Operator):
    bl_label = "Origin to Selected"
    bl_idname = "object.origin_to_selection"
    bl_description = "Snaps the object's origin to the selected components in Edit Mode"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cursor = bpy.context.scene.cursor.location
        cursor_location = [cursor[0], cursor[1], cursor[2]]
        
        bpy.ops.view3d.snap_cursor_to_selected()
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.context.scene.cursor.location = cursor_location

        return {'FINISHED'}

def draw_menu(self, context):
    if bpy.context.edit_object:
        self.layout.separator()
        self.layout.operator(OBJECT_OT_origin_to_selection.bl_idname)

def register():
    bpy.utils.register_class(OBJECT_OT_origin_to_selection)
    bpy.types.VIEW3D_MT_snap.append(draw_menu)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_origin_to_selection)
    bpy.types.VIEW3D_MT_snap.remove(draw_menu)