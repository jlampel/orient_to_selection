'''
Copyright (C) 2020-2026 Orange Turbine
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
from .utilities import align_to_matrix


class OBJECT_OT_orient_to_active(Operator):
    bl_label = "Orient Local to Active"
    bl_idname = "object.orient_to_active"
    bl_description = (
        "Aligns the local axes of the selected objects with the active object and switches to Local orientation"
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (
            obj is not None
            and context.mode == 'OBJECT'
            and any(selected != obj for selected in context.selected_objects)
            and context.area is not None
            and context.area.type == 'VIEW_3D'
        )

    def execute(self, context):
        active = context.active_object
        # Redo runs right after an undo, before matrix_world has been re-evaluated
        context.evaluated_depsgraph_get()

        # Quaternion conversion drops scale and shear from the active obj's world matrix
        result = align_to_matrix(context, active.matrix_world.to_quaternion().to_matrix())

        if 'FINISHED' not in result:
            return {'CANCELLED'}

        context.scene.transform_orientation_slots[0].type = 'LOCAL'

        if any(obj.animation_data for obj in context.selected_objects if obj != active):
            self.report({'WARNING'},
                "Some selected objects have keyframes. Changing the local orientation will alter any animated rotation"
            )

        return {'FINISHED'}

def draw_menu(self, context):
    if context.mode == 'OBJECT':
        self.layout.separator()
        self.layout.operator(OBJECT_OT_orient_to_active.bl_idname, icon="ORIENTATION_LOCAL")


def register():
    bpy.utils.register_class(OBJECT_OT_orient_to_active)
    bpy.types.VIEW3D_PT_transform_orientations.append(draw_menu)
    bpy.types.VIEW3D_MT_snap.append(draw_menu)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_orient_to_active)
    bpy.types.VIEW3D_PT_transform_orientations.remove(draw_menu)
    bpy.types.VIEW3D_MT_snap.remove(draw_menu)
