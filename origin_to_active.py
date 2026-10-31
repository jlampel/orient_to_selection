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


class OBJECT_OT_origin_to_active(Operator):
    bl_label = "Object Origins to Active"
    bl_idname = "object.origin_to_active"
    bl_description = "Moves the origins of the selected objects to the active object's origin without moving their geometry"
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
        cursor = context.scene.cursor
        cursor_location = cursor.location.copy()

        try:
            cursor.location = context.active_object.matrix_world.translation
            result = bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
        finally:
            cursor.location = cursor_location

        if 'FINISHED' not in result:
            return {'CANCELLED'}

        return {'FINISHED'}

def draw_menu(self, context):
    if context.mode == 'OBJECT':
        self.layout.operator(OBJECT_OT_origin_to_active.bl_idname, icon="PIVOT_ACTIVE")

def register():
    bpy.utils.register_class(OBJECT_OT_origin_to_active)
    bpy.types.VIEW3D_MT_snap.append(draw_menu)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_origin_to_active)
    bpy.types.VIEW3D_MT_snap.remove(draw_menu)
