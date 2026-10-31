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
from mathutils import Matrix, Vector, geometry
from .utilities import AXES, align_to_matrix, resolve_axes


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
        bmesh.ops.convex_hull(bm, input=bm.verts)
        # Reading the hull back through a mesh is much faster than looping over its bm elements
        bm.to_mesh(mesh)
        co = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        corners = np.empty(len(mesh.loops), dtype=np.int32)
        normals = np.empty(len(mesh.polygons) * 3, dtype=np.float32)
        areas = np.empty(len(mesh.polygons), dtype=np.float32)
        mesh.vertices.foreach_get("co", co)
        mesh.loops.foreach_get("vertex_index", corners)
        mesh.polygons.foreach_get("normal", normals)
        mesh.polygons.foreach_get("area", areas)
    finally:
        bm.free()
        bpy.data.meshes.remove(mesh)

    hull = co.reshape(-1, 3)[np.unique(corners)]
    normals = normals.reshape(-1, 3)
    valid = (areas > 0) & (np.linalg.norm(normals, axis=1) > 0.5)
    normals, areas = normals[valid], areas[valid]
    if not len(normals):
        return hull, normals

    # Opposite faces fit the same box and flat sides of the hull are split into tris, so normals repeat
    largest = np.abs(normals).argmax(axis=1)
    normals *= np.sign(normals[np.arange(len(normals)), largest])[:, None]
    keys = np.round(normals * 1e4).astype(np.int64) + 10000
    keys = keys[:, 0] << 30 | keys[:, 1] << 15 | keys[:, 2]
    _, first, groups = np.unique(keys, return_index=True, return_inverse=True)
    normals, areas = normals[first], np.bincount(groups.ravel(), weights=areas)

    max_normals = 1000
    if len(normals) > max_normals:
        # Dense hulls are simplified by splitting the directions into a grid of regions
        # and keeping the normal that covers the most area in each one.
        # Octahedral mapping unfolds the sphere of directions into a square.
        flat = normals[:, :2] / np.abs(normals).sum(axis=1)[:, None]
        lower = normals[:, 2] < 0
        flat[lower] = (1 - np.abs(flat[lower][:, ::-1])) * np.where(flat[lower] < 0, -1, 1)
        largest_first = np.argsort(-areas, kind='stable')
        # Opposite normals were merged so about half of the cells are used
        grid = int(np.sqrt(2 * max_normals)) + 1
        keep = largest_first
        while len(keep) > max_normals:
            grid -= 1
            cells = np.clip(((flat + 1) / 2 * grid).astype(np.int64), 0, grid - 1)
            cells = cells[:, 0] * grid + cells[:, 1]
            _, first = np.unique(cells[largest_first], return_index=True)
            keep = largest_first[np.sort(first)]
        normals = normals[keep]

    return hull, normals


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


def rough_sizes(points, normals, scale):
    ''' Estimates the size of the smallest box along each normal by
    trying a fixed set of rotations around each normal '''
    rotations = 16
    normals = np.array(normals)
    # Any vector that isn't parallel to a normal gives a direction across it
    helpers = np.where(np.abs(normals[:, :1]) < 0.9, [[1.0, 0.0, 0.0]], [[0.0, 1.0, 0.0]])
    u = np.cross(normals, helpers)
    u /= np.linalg.norm(u, axis=1)[:, None]
    v = np.cross(normals, u)
    # Half turn of directions, so each one has another at right angles to it
    angles = np.arange(2 * rotations) * np.pi / (2 * rotations)
    directions = np.cos(angles)[None, :, None] * u[:, None] + np.sin(angles)[None, :, None] * v[:, None]
    directions = directions.astype(np.float32)
    points = points.astype(np.float32)
    widths = np.empty((len(normals), 2 * rotations), dtype=np.float32)
    # Chunks keep the array of every point measured along every direction small
    for start in range(0, len(normals), 128):
        chunk = directions[start:start + 128]
        reach = points @ chunk.reshape(-1, 3).T
        widths[start:start + 128] = np.ptp(reach, axis=0).reshape(len(chunk), -1)
    best = (widths[:, :rotations] * widths[:, rotations:]).argmin(axis=1)
    rows = np.arange(len(normals))
    depths = np.ptp(points @ normals.T.astype(np.float32), axis=0)
    dimensions = np.stack([widths[rows, best], widths[rows, best + rotations], depths])
    # Surface area breaks ties
    return dimensions.prod(axis=0) + (dimensions * np.roll(dimensions, 1, axis=0)).sum(axis=0) * scale * 1e-6


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

    # Fitting every candidate exactly is slow, so they're narrowed down in stages:
    # 1. A rough fit of all of them to a sample of the points
    # 2. An exact fit of the best ones to the sample
    # 3. An exact fit to every point
    sample_size, shortlist, finalists = 1000, 64, 8
    sample = points[::len(points) // sample_size + 1]
    if len(candidates) > shortlist:
        sizes = rough_sizes(sample, candidates, scale)
        candidates = [candidates[i] for i in np.argsort(sizes, kind='stable')[:shortlist]]
    if len(points) > len(sample):
        candidates.sort(key=lambda normal: fit_box(sample, normal, scale)[0])
        candidates = candidates[:finalists]

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
        # Redo starts from the same geo so reuse it. Blender keeps this operator instance for redo.
        if not self.options.is_repeat or not hasattr(self, "fits"):
            self.fits = {}

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

    def fit(self, name, points):
        if name not in self.fits:
            self.fits[name] = best_fit_axes(points())
        return self.fits[name]

    def orient_objects(self, context):
        view_layer = context.view_layer
        active = view_layer.objects.active
        selected = context.selected_objects

        matrices = {}
        for obj in selected:
            if obj.type != 'MESH':
                continue
            axes = self.fit(obj.name, lambda: object_points(context, obj))
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

        axes = self.fit(obj.name, lambda: np.concatenate([
            selected_points(edit_obj) for edit_obj in context.objects_in_mode if edit_obj.type == 'MESH'
        ]))
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
