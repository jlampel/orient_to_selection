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
from .origin_to_pivot import PIVOT_ICONS, snap_cursor_to_pivot


class OBJECT_OT_origin_to_selection(Operator):
    bl_label = "Object Origin to Pivot Point"
    bl_idname = "object.origin_to_selection"
    bl_description = "Moves the object's origin to the current transform pivot point in Edit Mode"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.edit_object is not None
            and context.area is not None
            and context.area.type == 'VIEW_3D'
        )

    def execute(self, context):
        obj = context.edit_object
        cursor = context.scene.cursor
        cursor_location = cursor.location.copy()

        try:
            try:
                result = snap_cursor_to_pivot(context)
                if 'FINISHED' not in result:
                    return {'CANCELLED'}

                bpy.ops.object.mode_set(mode='OBJECT')
                result = bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
            finally:
                cursor.location = cursor_location

            if 'FINISHED' not in result:
                return {'CANCELLED'}

            # Older Blender versions need an Object Mode checkpoint to restore both
            # the object transform and geometry. Restore the cursor before recording it.
            if bpy.app.version < (5, 3, 0):
                bpy.ops.ed.undo_push(message=self.bl_label)
        finally:
            if obj.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}

def draw_menu(self, context):
    if OBJECT_OT_origin_to_selection.poll(context):
        # self.layout.separator()
        pivot_point = context.scene.tool_settings.transform_pivot_point
        self.layout.operator(OBJECT_OT_origin_to_selection.bl_idname, icon=PIVOT_ICONS[pivot_point])

def register():
    bpy.utils.register_class(OBJECT_OT_origin_to_selection)
    bpy.types.VIEW3D_MT_snap.append(draw_menu)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_origin_to_selection)
    bpy.types.VIEW3D_MT_snap.remove(draw_menu)
