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
from bpy.props import EnumProperty
from mathutils import Matrix


AXES = [
    ('POS_X', "X", ""),
    ('POS_Y', "Y", ""),
    ('POS_Z', "Z", ""),
    ('NEG_X', "-X", ""),
    ('NEG_Y', "-Y", ""),
    ('NEG_Z', "-Z", ""),
]


def resolve_axes(self, changed, other):
    # Makes sure the two settings don't use the same axis
    changed_axis = getattr(self, changed)
    other_axis = getattr(self, other)
    if changed_axis[-1] == other_axis[-1]:
        free_axis = "XYZ"[("XYZ".index(changed_axis[-1]) + 1) % 3]
        setattr(self, other, other_axis[:-1] + free_axis)


class OBJECT_OT_orient_to_selection(Operator):
    bl_label = "Orient to Selected"
    bl_idname = "object.orient_to_selection"
    bl_description = "Aligns the object's local axes with the normals of the selected mesh"
    bl_options = {'REGISTER', 'UNDO'}

    normal_axis: EnumProperty(
        name="Normal Axis",
        description="Local axis to align with the normal of the selection",
        items=AXES,
        default='POS_Z',
        update=lambda self, context: resolve_axes(self, "normal_axis", "tangent_axis"),
    )
    tangent_axis: EnumProperty(
        name="Tangent Axis",
        description="Local axis to align with the tangent of the selection",
        items=AXES,
        default='POS_Y',
        update=lambda self, context: resolve_axes(self, "tangent_axis", "normal_axis"),
    )

    @classmethod
    def poll(cls, context):
        # Redo on Blender versions before 5.3 starts from the Object Mode undo checkpoint
        obj = context.active_object
        return (
            obj is not None
            and obj.type == 'MESH'
            and context.mode in {'EDIT_MESH', 'OBJECT'}
            and context.area is not None
            and context.area.type == 'VIEW_3D'
            and context.scene.transform_orientation_slots[0].type == 'LOCAL'
        )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "normal_axis")
        layout.prop(self, "tangent_axis")

    def axis_matrix(self, matrix):
        tangent, normal = matrix.col[1].copy(), matrix.col[2].copy()
        columns = [None, None, None]
        for axis, vector in ((self.normal_axis, normal), (self.tangent_axis, tangent)):
            columns["XYZ".index(axis[-1])] = -vector if axis.startswith('NEG') else vector
        remaining = 3 - "XYZ".index(self.normal_axis[-1]) - "XYZ".index(self.tangent_axis[-1])
        columns[remaining] = columns[(remaining + 1) % 3].cross(columns[(remaining + 2) % 3])
        return Matrix(columns).transposed()

    def selection_matrix(self, context):
        slot = context.scene.transform_orientation_slots[0]
        orientation = slot.type

        try:
            result = bpy.ops.transform.create_orientation(name="SELECTION", use=True)
        except RuntimeError as error:
            self.report({'WARNING'}, f"Could not create an orientation from the selection: {error}")
            return None

        if 'FINISHED' not in result:
            self.report({'WARNING'}, "Could not create an orientation from the selection")
            return None

        try:
            return slot.custom_orientation.matrix.copy()
        finally:
            try:
                bpy.ops.transform.delete_orientation()
            finally:
                slot.type = orientation

    def execute(self, context):
        obj = context.active_object
        settings = context.scene.tool_settings
        edit_origin = settings.use_transform_data_origin
        skip_children = settings.use_transform_skip_children
        auto_keying = settings.use_keyframe_insert_auto
        # Older Blender versions need an Object Mode checkpoint to restore both the object
        # transform and mesh. Redo already starts from that checkpoint, so only record it once.
        record_checkpoint = bpy.app.version < (5, 3, 0) and not self.options.is_repeat

        if obj.mode != 'EDIT':
            if not self.options.is_repeat:
                return {'CANCELLED'}
            bpy.ops.object.mode_set(mode='EDIT')

        # Update callbacks don't run for arguments passed to the operator from a script
        resolve_axes(self, "normal_axis", "tangent_axis")

        try:
            matrix = self.selection_matrix(context)
            if matrix is None:
                return {'CANCELLED'}

            bpy.ops.object.mode_set(mode='OBJECT')
            if record_checkpoint:
                bpy.ops.ed.undo_push(message=self.bl_label)

            try:
                settings.use_transform_skip_children = True
                settings.use_transform_data_origin = True
                settings.use_keyframe_insert_auto = False

                result = bpy.ops.transform.transform(
                    mode='ALIGN',
                    orient_type='GLOBAL',
                    orient_matrix=self.axis_matrix(matrix),
                    orient_matrix_type='GLOBAL',
                )
            finally:
                settings.use_transform_skip_children = skip_children
                settings.use_transform_data_origin = edit_origin
                settings.use_keyframe_insert_auto = auto_keying

            if 'FINISHED' not in result:
                return {'CANCELLED'}
        finally:
            if obj.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')

        if obj.animation_data:
            self.report({'WARNING'},
                "This object has keyframes. Changing the local orientation will alter any animated rotation"
            )

        return {'FINISHED'}

def draw_menu(self, context):
    if context.mode == 'EDIT_MESH' and OBJECT_OT_orient_to_selection.poll(context):
        self.layout.separator()
        self.layout.operator(OBJECT_OT_orient_to_selection.bl_idname, icon="ORIENTATION_NORMAL")

def register():
    bpy.utils.register_class(OBJECT_OT_orient_to_selection)
    bpy.types.VIEW3D_PT_transform_orientations.append(draw_menu)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_orient_to_selection)
    bpy.types.VIEW3D_PT_transform_orientations.remove(draw_menu)
