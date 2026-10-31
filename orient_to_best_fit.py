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
import bmesh
import numpy as np
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty
from itertools import permutations, product
from math import pi, radians
from mathutils import Matrix, Vector, geometry
from .utilities import AXES, align_to_matrix, resolve_axes


MAX_HULL_FACES = 1000
MAX_SAMPLE_POINTS = 2000
FINALISTS = 8

AUTO_AXES = [('AUTO', "Auto", "Use the local axis closest to the current orientation"), *AXES]


def world_points(obj, co):
    matrix = np.array(obj.matrix_world)
    return co.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]


def object_points(context, obj):
    evaluated = obj.evaluated_get(context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        co = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", co)
    finally:
        evaluated.to_mesh_clear()
    return world_points(obj, co)


def selected_points(obj):
    obj.update_from_editmode()
    vertices = obj.data.vertices
    co = np.empty(len(vertices) * 3, dtype=np.float32)
    selected = np.empty(len(vertices), dtype=bool)
    vertices.foreach_get("co", co)
    vertices.foreach_get("select", selected)
    return world_points(obj, co.reshape(-1, 3)[selected])


def convex_hull(points):
    ''' Returns the hull's verts and its face normals without duplicates '''
    mesh = bpy.data.meshes.new("Best Fit Hull")
    bm = bmesh.new()
    try:
        mesh.vertices.add(len(points))
        mesh.vertices.foreach_set("co", points.astype(np.float32).ravel())
        bm.from_mesh(mesh)
        geom = bmesh.ops.convex_hull(bm, input=bm.verts)['geom']
        hull = np.array([vert.co for vert in geom if isinstance(vert, bmesh.types.BMVert)])

        # Dense hulls are simplified by merging faces, flattest areas first
        # Their verts were already collected so the box still fits them all
        angle = radians(1)
        while len(bm.faces) > MAX_HULL_FACES and angle < pi:
            bmesh.ops.dissolve_limit(bm, angle_limit=angle, verts=[], edges=bm.edges[:])
            angle *= 2
        bm.normal_update()
        normals = np.array([face.normal for face in bm.faces]).reshape(-1, 3)
    finally:
        bm.free()
        bpy.data.meshes.remove(mesh)

    normals = normals[np.linalg.norm(normals, axis=1) > 0.5]
    if not len(normals):
        return hull, normals

    # Opposite faces fit the same box and flat sides of the hull are split into tris, so normals repeat
    largest = np.abs(normals).argmax(axis=1)
    normals *= np.sign(normals[np.arange(len(normals)), largest])[:, None]
    _, first = np.unique(np.round(normals, 4), axis=0, return_index=True)
    return hull, normals[np.sort(first)]


def fit_box(points, normal, scale):
    ''' Fits the smallest box with one axis along the normal. Returns its size and its axes as rows. '''
    normal = Vector(normal).normalized()
    u = normal.orthogonal().normalized()
    v = normal.cross(u)
    plane = np.array([u, v])
    # box_fit_2d returns the angle that rotates the points to fit an axis-aligned rectangle
    angle = geometry.box_fit_2d((points @ plane.T).tolist())
    cos, sin = np.cos(angle), np.sin(angle)
    axes = np.array([cos * plane[0] - sin * plane[1], sin * plane[0] + cos * plane[1], normal])
    dimensions = np.ptp(points @ axes.T, axis=0)
    volume = dimensions.prod()
    area = dimensions @ np.roll(dimensions, 1)
    # Surface area breaks ties between flat boxes with no volume
    return volume + area * scale * 1e-6, axes


def best_fit_axes(points):
    ''' Approximates the smallest box around the points by trying boxes with one face flush with each hull face,
    with the principal axes as a fallback. Returns the box axes as rows from longest to shortest side,
    or None if the points have no size. '''
    if len(points) < 2: return None
    points = points - (points.min(axis=0) + points.max(axis=0)) / 2
    scale = np.ptp(points, axis=0).max()
    if scale < 1e-6: return None

    candidates = list(np.linalg.eigh(np.cov(points.T))[1].T)
    if len(points) > 3:
        try:
            hull, normals = convex_hull(points)
        except (RuntimeError, ValueError):
            pass
        else:
            if len(hull) > 3:
                points = hull
            candidates += list(normals)

    # Fitting every candidate to a dense hull is slow, so a sample of its points narrows them down first
    if len(points) > MAX_SAMPLE_POINTS:
        sample = points[::len(points) // MAX_SAMPLE_POINTS + 1]
        candidates.sort(key=lambda normal: fit_box(sample, normal, scale)[0])
        candidates = candidates[:FINALISTS]

    axes = min((fit_box(points, normal, scale) for normal in candidates), key=lambda fit: fit[0])[1]
    axes = axes[np.argsort(-np.ptp(points @ axes.T, axis=0), kind='stable')]
    # A box side has no direction of its own, so each axis points the way of the world axis it's closest to
    return axes * np.sign(axes[np.arange(3), np.abs(axes).argmax(axis=1)])[:, None]


def closest_rotation(axes, matrix, main_axis='AUTO', secondary_axis='AUTO'):
    ''' Assigns the longest box axis to the main axis and the second longest to the secondary axis.
    Auto axes go to the local axis they're closest to, so the object rotates as little as possible. '''
    current = np.array(matrix.to_quaternion().to_matrix())
    fixed = {
        "XYZ".index(axis[-1]): (side, -1 if axis.startswith('NEG') else 1)
        for side, axis in enumerate((main_axis, secondary_axis)) if axis != 'AUTO'
    }
    best_columns, best_score = None, None
    for order, signs in product(permutations(range(3)), product((1, -1), repeat=3)):
        if any(order[local] != side or signs[local] != sign for local, (side, sign) in fixed.items()):
            continue
        columns = (axes[list(order)] * np.array(signs)[:, None]).T
        if np.linalg.det(columns) < 0:
            continue
        score = np.sum(columns * current)
        if best_score is None or score > best_score:
            best_columns, best_score = columns, score
    return Matrix(best_columns.tolist())


class OBJECT_OT_orient_to_best_fit(Operator):
    bl_label = "Orient Local to Best Fit"
    bl_idname = "object.orient_to_best_fit"
    bl_description = (
        "Aligns the local axes with the smallest box that fits each selected object, "
        "or the selected components in Edit Mode, and switches to Local orientation"
    )
    bl_options = {'REGISTER', 'UNDO'}

    main_axis: EnumProperty(
        name="Main Axis",
        description="Local axis to align with the longest side of the box",
        items=AUTO_AXES,
        default='AUTO',
        update=lambda self, context: resolve_axes(self, "main_axis", "secondary_axis"),
    )
    secondary_axis: EnumProperty(
        name="Secondary Axis",
        description="Local axis to align with the second longest side of the box",
        items=AUTO_AXES,
        default='AUTO',
        update=lambda self, context: resolve_axes(self, "secondary_axis", "main_axis"),
    )
    # Redo on Blender versions before 5.3 starts in Object Mode even when the operator ran in Edit Mode
    edit_mode: BoolProperty(options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        if context.area is None or context.area.type != 'VIEW_3D':
            return False
        if context.mode == 'EDIT_MESH':
            return True
        return context.mode == 'OBJECT' and any(obj.type == 'MESH' for obj in context.selected_objects)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "main_axis")
        layout.prop(self, "secondary_axis")

    def execute(self, context):
        # Redo runs right after an undo, before matrix_world has been re-evaluated
        context.evaluated_depsgraph_get()

        if not self.options.is_repeat:
            self.edit_mode = context.mode == 'EDIT_MESH'

        resolve_axes(self, "main_axis", "secondary_axis")

        if self.edit_mode:
            result = self.orient_edit_mode(context)
        else:
            result = self.orient_objects(context)

        if 'FINISHED' not in result:
            return {'CANCELLED'}

        context.scene.transform_orientation_slots[0].type = 'LOCAL'

        if any(obj.animation_data for obj in context.selected_objects):
            self.report({'WARNING'},
                "Some selected objects have keyframes. Changing the local orientation will alter any animated rotation"
            )

        return {'FINISHED'}

    def orient_objects(self, context):
        view_layer = context.view_layer
        active = view_layer.objects.active
        selected = context.selected_objects

        matrices = {}
        for obj in selected:
            if obj.type != 'MESH':
                continue
            axes = best_fit_axes(object_points(context, obj))
            if axes is not None:
                matrices[obj] = closest_rotation(axes, obj.matrix_world, self.main_axis, self.secondary_axis)

        if not matrices:
            self.report({'WARNING'}, "The selected objects have no size to fit a box to")
            return {'CANCELLED'}

        # Each object gets its own matrix, so they're aligned one at a time
        result = {'CANCELLED'}
        try:
            for obj in selected:
                obj.select_set(False)
            for obj, matrix in matrices.items():
                obj.select_set(True)
                view_layer.objects.active = obj
                if 'FINISHED' in align_to_matrix(context, matrix):
                    result = {'FINISHED'}
                obj.select_set(False)
        finally:
            for obj in selected:
                obj.select_set(True)
            view_layer.objects.active = active

        return result

    def orient_edit_mode(self, context):
        obj = context.active_object
        if obj.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

        points = np.concatenate([
            selected_points(edit_obj) for edit_obj in context.objects_in_mode if edit_obj.type == 'MESH'
        ])
        axes = best_fit_axes(points)
        if axes is None:
            self.report({'WARNING'}, "Select at least two vertices that aren't in the same place")
            return {'CANCELLED'}

        try:
            bpy.ops.object.mode_set(mode='OBJECT')
            # Older Blender versions need an Object Mode checkpoint to restore both the obj transform and mesh.
            # Redo starts from this checkpoint.
            if bpy.app.version < (5, 3, 0) and not self.options.is_repeat:
                bpy.ops.ed.undo_push(message=self.bl_label)

            matrix = closest_rotation(axes, obj.matrix_world, self.main_axis, self.secondary_axis)
            return align_to_matrix(context, matrix)
        finally:
            if obj.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')


def draw_menu(self, context):
    if context.mode in {'EDIT_MESH', 'OBJECT'}:
        self.layout.operator(OBJECT_OT_orient_to_best_fit.bl_idname, icon="SHADING_BBOX")


def register():
    bpy.utils.register_class(OBJECT_OT_orient_to_best_fit)
    bpy.types.VIEW3D_PT_transform_orientations.append(draw_menu)
    bpy.types.VIEW3D_MT_snap.append(draw_menu)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_orient_to_best_fit)
    bpy.types.VIEW3D_PT_transform_orientations.remove(draw_menu)
    bpy.types.VIEW3D_MT_snap.remove(draw_menu)
