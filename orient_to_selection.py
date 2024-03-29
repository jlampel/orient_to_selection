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
from bpy.types import (Operator)
from bpy.props import (BoolProperty)

class OBJECT_OT_orient_to_selection(Operator):
    bl_label = "Orient to Selected"
    bl_idname = "object.orient_to_selection"
    bl_description = "Aligns the object's local axes with the normals of the selected mesh"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bpy.context.scene.transform_orientation_slots[0].type == 'LOCAL'
            
    def execute(self, context):
        obj = bpy.context.edit_object
        orientation = bpy.context.scene.transform_orientation_slots[0].type
        edit_origin = bpy.context.scene.tool_settings.use_transform_data_origin
        affect_children =   bpy.context.scene.tool_settings.use_transform_skip_children
        auto_keying = bpy.context.scene.tool_settings.use_keyframe_insert_auto


        bpy.context.scene.transform_orientation_slots[0].type = 'NORMAL'
        try: 
            bpy.ops.transform.create_orientation(name="SELECTION", use=True)
        except:
            bpy.context.scene.transform_orientation_slots[0].type = orientation
            self.report({'WARNING'}, 
                    "No orientation could be created because the normals of the selected items exactly cancel each other out"
                )
            return {'CANCELLED'}
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.context.scene.tool_settings.use_transform_skip_children = True
        bpy.context.scene.tool_settings.use_transform_data_origin = True
        bpy.context.scene.tool_settings.use_keyframe_insert_auto = False

        bpy.context.view_layer.objects.active = obj
        bpy.ops.transform.transform(mode='ALIGN', orient_type='SELECTION', orient_matrix_type='SELECTION')
        
        bpy.context.scene.tool_settings.use_transform_skip_children = affect_children
        bpy.context.scene.tool_settings.use_transform_data_origin = edit_origin
        bpy.context.scene.tool_settings.use_keyframe_insert_auto = auto_keying
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.transform.delete_orientation()
        bpy.context.scene.transform_orientation_slots[0].type = orientation

        if obj.animation_data:
            self.report({'WARNING'}, 
                "This object has keyframes. Changing the local orientation will alter any animated rotation"
            )

        return {'FINISHED'}

def draw_menu(self, context):
    if (bpy.context.scene.transform_orientation_slots[0].type == 'LOCAL' and bpy.context.edit_object):
        self.layout.separator()
        self.layout.operator(OBJECT_OT_orient_to_selection.bl_idname, icon="ORIENTATION_NORMAL")

def register():
    bpy.utils.register_class(OBJECT_OT_orient_to_selection)
    bpy.types.VIEW3D_PT_transform_orientations.append(draw_menu)
    
def unregister():
    bpy.utils.unregister_class(OBJECT_OT_orient_to_selection)
    bpy.types.VIEW3D_PT_transform_orientations.remove(draw_menu)

