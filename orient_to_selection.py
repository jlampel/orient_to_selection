'''
Copyright (C) 2020-2023 Orange Turbine
https://orangeturbine.com
orangeturbine@cgcookie.com

This file is part of Orient to Selection, created by Jonathan Lampel. 

All code distributed with this add-on is open source as described below. 

Orient to Selection is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 3
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, see <https://www.gnu.org/licenses/>.
'''


import bpy
from bpy.types import Operator


class OBJECT_OT_orient_to_selection(Operator):
    bl_label = "Orient to Selected"
    bl_idname = "object.orient_to_selection"
    bl_description = (
        "Aligns the object's local axes with the normals of the selected mesh and switches to Local orientation"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'EDIT_MESH' and context.area is not None and context.area.type == 'VIEW_3D'
        )

    def execute(self, context):
        obj = context.edit_object
        slot = context.scene.transform_orientation_slots[0]
        settings = context.scene.tool_settings
        orientation = slot.type
        edit_origin = settings.use_transform_data_origin
        skip_children = settings.use_transform_skip_children
        auto_keying = settings.use_keyframe_insert_auto

        try:
            result = bpy.ops.transform.create_orientation(name="SELECTION", use=True)
        except RuntimeError as error:
            self.report({'WARNING'}, f"Could not create an orientation from the selection: {error}")
            return {'CANCELLED'}

        if 'FINISHED' not in result:
            self.report({'WARNING'}, "Could not create an orientation from the selection")
            return {'CANCELLED'}

        selection_orientation = slot.custom_orientation.name
        try:
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
                settings.use_transform_skip_children = True
                settings.use_transform_data_origin = True
                settings.use_keyframe_insert_auto = False

                result = bpy.ops.transform.transform(mode='ALIGN', orient_type=selection_orientation)
            finally:
                settings.use_transform_skip_children = skip_children
                settings.use_transform_data_origin = edit_origin
                settings.use_keyframe_insert_auto = auto_keying
                try:
                    bpy.ops.transform.delete_orientation()
                finally:
                    slot.type = orientation

            if 'FINISHED' not in result:
                return {'CANCELLED'}

            # Show the updated axes, including when invoked from the Snap menu.
            slot.type = 'LOCAL'

            # Older Blender versions need an Object Mode checkpoint to restore both
            # the object transform and mesh. Record it after temporary settings are restored.
            if bpy.app.version < (5, 3, 0):
                bpy.ops.ed.undo_push(message=self.bl_label)
        finally:
            if obj.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')

        if obj.animation_data:
            self.report({'WARNING'}, 
                "This object has keyframes. Changing the local orientation will alter any animated rotation"
            )

        return {'FINISHED'}

def draw_menu(self, context):
    if OBJECT_OT_orient_to_selection.poll(context):
        self.layout.separator()
        self.layout.operator(OBJECT_OT_orient_to_selection.bl_idname, icon="ORIENTATION_NORMAL")

def draw_orientation_menu(self, context):
    if context.scene.transform_orientation_slots[0].type == 'LOCAL':
        draw_menu(self, context)


def register():
    bpy.utils.register_class(OBJECT_OT_orient_to_selection)
    bpy.types.VIEW3D_PT_transform_orientations.append(draw_orientation_menu)
    bpy.types.VIEW3D_MT_snap.append(draw_menu)
    
def unregister():
    bpy.utils.unregister_class(OBJECT_OT_orient_to_selection)
    bpy.types.VIEW3D_PT_transform_orientations.remove(draw_orientation_menu)
    bpy.types.VIEW3D_MT_snap.remove(draw_menu)

