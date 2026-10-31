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


def align_to_matrix(context, matrix):
    # Aligns the local axes of the selected objects with the matrix without moving their geometry
    slot = context.scene.transform_orientation_slots[0]
    orientation = slot.type
    settings = context.scene.tool_settings
    edit_origin = settings.use_transform_data_origin
    skip_children = settings.use_transform_skip_children
    auto_keying = settings.use_keyframe_insert_auto

    # Before Blender 5.0, ALIGN ignores orient_matrix, so the matrix goes through a temporary custom orientation.
    # In Object Mode it's created from the active obj, then overwritten.
    if 'FINISHED' not in bpy.ops.transform.create_orientation(name="ALIGN", use=True):
        return {'CANCELLED'}

    try:
        slot.custom_orientation.matrix = matrix
        settings.use_transform_skip_children = True
        settings.use_transform_data_origin = True
        settings.use_keyframe_insert_auto = False

        return bpy.ops.transform.transform(
            mode='ALIGN',
            orient_type=slot.custom_orientation.name,
            orient_matrix_type=slot.custom_orientation.name,
        )
    finally:
        settings.use_transform_skip_children = skip_children
        settings.use_transform_data_origin = edit_origin
        settings.use_keyframe_insert_auto = auto_keying
        try:
            bpy.ops.transform.delete_orientation()
        finally:
            slot.type = orientation
