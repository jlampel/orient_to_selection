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


PIVOT_ICONS = {
    'BOUNDING_BOX_CENTER': 'PIVOT_BOUNDBOX',
    'CURSOR': 'PIVOT_CURSOR',
    'INDIVIDUAL_ORIGINS': 'PIVOT_MEDIAN',
    'MEDIAN_POINT': 'PIVOT_MEDIAN',
    'ACTIVE_ELEMENT': 'PIVOT_ACTIVE',
}


def snap_cursor_to_pivot(context):
    pivot_point = context.scene.tool_settings.transform_pivot_point
    if pivot_point == 'CURSOR':
        return {'FINISHED'}
    if pivot_point == 'ACTIVE_ELEMENT':
        # Falls back to the median when there is no active element
        result = bpy.ops.view3d.snap_cursor_to_active()
        if 'FINISHED' in result:
            return result
    return bpy.ops.view3d.snap_cursor_to_selected()


class OBJECT_OT_active_origin_to_pivot(Operator):
    bl_label = "Active Origin to Pivot Point"
    bl_idname = "object.active_origin_to_pivot"
    bl_description = "Moves the active object's origin to the current transform pivot point"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not (
            obj is not None
            and obj.select_get()
            and context.mode == 'OBJECT'
            and context.area is not None
            and context.area.type == 'VIEW_3D'
        ):
            return False

        # The active element is already at the active object's origin
        if context.scene.tool_settings.transform_pivot_point == 'ACTIVE_ELEMENT':
            cls.poll_message_set("Pivot Point can't be Active Element")
            return False

        return True

    def execute(self, context):
        obj = context.active_object
        cursor = context.scene.cursor
        cursor_location = cursor.location.copy()
        others = [selected for selected in context.selected_objects if selected != obj]

        try:
            result = snap_cursor_to_pivot(context)
            if 'FINISHED' not in result:
                return {'CANCELLED'}

            try:
                for selected in others:
                    selected.select_set(False)
                result = bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
            finally:
                for selected in others:
                    selected.select_set(True)
        finally:
            cursor.location = cursor_location

        if 'FINISHED' not in result:
            return {'CANCELLED'}

        return {'FINISHED'}

def draw_menu(self, context):
    if context.mode == 'OBJECT':
        pivot_point = context.scene.tool_settings.transform_pivot_point
        self.layout.operator(OBJECT_OT_active_origin_to_pivot.bl_idname, icon=PIVOT_ICONS[pivot_point])

def register():
    bpy.utils.register_class(OBJECT_OT_active_origin_to_pivot)
    bpy.types.VIEW3D_MT_snap.append(draw_menu)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_active_origin_to_pivot)
    bpy.types.VIEW3D_MT_snap.remove(draw_menu)
