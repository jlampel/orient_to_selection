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
import numpy as np
from bpy.types import Operator
from bpy.props import EnumProperty
from mathutils import Vector


def mesh_batches(co, tris, matrices):
    ''' The evaluated mesh plus the mesh of any instances, batched for better memory usage.
    Yields the points as an (instances, points, 3) array, and +1 or -1 to denote mirroring. '''
    size = max(1, (1 << 20) // max(len(co), 3 * len(tris) if tris is not None else 0, 1))
    for start in range(0, len(matrices), size):
        batch = matrices[start:start + size]
        points = np.einsum('kij,nj->kni', batch[:, :3, :3], co) + batch[:, None, :3, 3]
        yield points, np.sign(np.linalg.det(batch[:, :3, :3]))


def mesh_arrays(obj, with_tris):
    ''' Returns the vert positions and tris of the obj's evaluated mesh, or None '''
    try:
        mesh = obj.to_mesh()
    except RuntimeError: return None
    if mesh is None: return None
    try:
        co = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", co)
        tris = None
        if with_tris:
            mesh.calc_loop_triangles()
            tris = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
            mesh.loop_triangles.foreach_get("vertices", tris)
            tris = tris.reshape(-1, 3)
    finally:
        obj.to_mesh_clear()
    return co.reshape(-1, 3).astype(np.float64), tris


def visual_geometry(context, objects, with_tris):
    ''' Collects the final geo each obj displays, in local space. Returns {obj: [(co, tris, matrices)]}. '''
    depsgraph = context.evaluated_depsgraph_get()
    inverses = {}
    for obj in objects:
        try:
            inverses[obj] = np.linalg.inv(np.array(obj.evaluated_get(depsgraph).matrix_world))
        except np.linalg.LinAlgError:
            pass

    meshes = {}
    geometry = {obj: {} for obj in inverses}
    for instance in depsgraph.object_instances:
        if instance.is_instance:
            owner = instance.parent.original if instance.parent else None
        else:
            owner = instance.object.original if instance.show_self else None
        if owner not in geometry:
            continue

        data = instance.object.data
        if data is None:
            continue
        key = data.as_pointer()
        if key not in meshes:
            meshes[key] = mesh_arrays(instance.object, with_tris)
        if meshes[key] is None or not len(meshes[key][0]):
            continue
        geometry[owner].setdefault(key, []).append(inverses[owner] @ np.array(instance.matrix_world))

    return {
        obj: [(*meshes[key], np.array(matrices)) for key, matrices in found.items()]
        for obj, found in geometry.items() if found
    }


def median_center(geometry):
    total, count = np.zeros(3), 0
    for co, _, matrices in geometry:
        total += np.einsum('kij,j->i', matrices[:, :3, :3], co.sum(axis=0))
        total += len(co) * matrices[:, :3, 3].sum(axis=0)
        count += len(co) * len(matrices)
    return total / count


def bounds(geometry):
    low, high = np.full(3, np.inf), np.full(3, -np.inf)
    for geo in geometry:
        for points, _ in mesh_batches(*geo):
            low = np.minimum(low, points.min(axis=(0, 1)))
            high = np.maximum(high, points.max(axis=(0, 1)))
    return low, high


def bounds_center(geometry):
    low, high = bounds(geometry)
    return (low + high) / 2


def mass_center(geometry):
    ''' Same as Blender's Origin to Center of Mass (Surface) '''
    total, area = np.zeros(3), 0.0
    for geo in geometry:
        tris = geo[1]
        if not len(tris):
            continue
        for points, _ in mesh_batches(*geo):
            corners = points[:, tris]
            areas = np.linalg.norm(np.cross(corners[:, :, 1] - corners[:, :, 0], corners[:, :, 2] - corners[:, :, 0]), axis=-1)
            total += np.einsum('kt,ktj->j', areas, corners.sum(axis=2)) / 3
            area += areas.sum()
    if area <= 0:
        return median_center(geometry)
    return total / area


def volume_center(geometry):
    ''' Same as Blender's Origin to Center of Mass (Volume) '''
    # Measuring from near the geometry avoids precision issues when it's far from the origin
    reference = median_center(geometry)
    total, volume = np.zeros(3), 0.0
    for geo in geometry:
        tris = geo[1]
        if not len(tris):
            continue
        for points, signs in mesh_batches(*geo):
            corners = points[:, tris] - reference
            # Six times the volume. Mirrored copies have flipped normals, so their sign is flipped back.
            volumes = np.einsum('ktj,ktj->kt', corners[:, :, 0], np.cross(corners[:, :, 1], corners[:, :, 2]))
            volumes *= signs[:, None]
            total += np.einsum('kt,ktj->j', volumes, corners.sum(axis=2))
            volume += volumes.sum()

    # No volume so fall back to the median
    low, high = bounds(geometry)
    if abs(volume) <= 1e-9 * np.ptp([low, high], axis=0).max() ** 3:
        return reference
    return reference + total / (4 * volume)




class OBJECT_OT_origin_to_visual_geometry(Operator):
    bl_label = "Origin to Visual Geometry"
    bl_idname = "object.origin_to_visual_geometry"
    bl_description = (
        "Moves the origins of the selected objects to the center of their geometry as it's shown in the viewport, "
        "including modifiers and instances"
    )
    bl_options = {'REGISTER', 'UNDO'}

    center: EnumProperty(
        name="Center",
        items=[
            ('MEDIAN', "Median Center", "Average position of the vertices"),
            ('BOUNDS', "Bounds Center", "Center of the local bounding box"),
            ('MASS', "Center of Mass", "Calculate the center of mass from the surface area"),
            ('VOLUME', "Center of Volume", (
                "Calculate the center of mass from the volume "
                "(must be manifold geometry with consistent normals)"
            )),
        ],
        default='MEDIAN',
    )

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'OBJECT'
            and context.area is not None
            and context.area.type == 'VIEW_3D'
            and any(obj.data is not None for obj in context.selected_objects)
        )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "center")

    def execute(self, context):
        # Redo runs right after an undo, before matrix_world has been re-evaluated
        context.evaluated_depsgraph_get()

        # Like Origin to Geometry, the center starts as Bounds when that's the pivot point
        if not self.properties.is_property_set("center"):
            if context.scene.tool_settings.transform_pivot_point == 'BOUNDING_BOX_CENTER':
                self.center = 'BOUNDS'

        # Redo starts from the same geometry. Blender keeps this operator instance for redo.
        if not self.options.is_repeat or not hasattr(self, "centers"):
            self.centers = {}

        CENTER_FUNCTIONS = {
            'MEDIAN': median_center,
            'BOUNDS': bounds_center,
            'MASS': mass_center,
            'VOLUME': volume_center,
        }

        selected = context.selected_objects
        objects = [obj for obj in selected if obj.data is not None and obj.library is None]
        missing = [obj for obj in objects if (obj.name, self.center) not in self.centers]
        if missing:
            geometry = visual_geometry(context, missing, self.center in {'MASS', 'VOLUME'})
            for obj in missing:
                center = None
                if obj in geometry:
                    local = CENTER_FUNCTIONS[self.center](geometry[obj])
                    center = obj.matrix_world @ Vector(local)
                self.centers[(obj.name, self.center)] = center

        # Objects with linked data have the same origin
        groups = {}
        for obj in [context.active_object, *objects]:
            if obj in objects and self.centers[(obj.name, self.center)] is not None:
                groups.setdefault(obj.data, (self.centers[(obj.name, self.center)], []))
        for obj in objects:
            if obj.data in groups:
                groups[obj.data][1].append(obj)
        if not groups:
            self.report({'WARNING'}, "The selected objects have no visible geometry")
            return {'CANCELLED'}

        # For unique objects, set one at a time. For linked objects, do it all at once.
        cursor = context.scene.cursor
        cursor_location = cursor.location.copy()
        result = {'CANCELLED'}
        try:
            for obj in selected:
                obj.select_set(False)
            for center, users in groups.values():
                for obj in users:
                    obj.select_set(True)
                cursor.location = center
                if 'FINISHED' in bpy.ops.object.origin_set(type='ORIGIN_CURSOR'):
                    result = {'FINISHED'}
                for obj in users:
                    obj.select_set(False)
        finally:
            for obj in selected:
                obj.select_set(True)
            cursor.location = cursor_location

        return result


def draw_menu(self, context):
    if context.mode == 'OBJECT':
        self.layout.separator()
        self.layout.operator(OBJECT_OT_origin_to_visual_geometry.bl_idname, icon="OBJECT_DATA")


def register():
    bpy.utils.register_class(OBJECT_OT_origin_to_visual_geometry)
    bpy.types.VIEW3D_MT_snap.append(draw_menu)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_origin_to_visual_geometry)
    bpy.types.VIEW3D_MT_snap.remove(draw_menu)
