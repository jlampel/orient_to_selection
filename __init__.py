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

bl_info = {
    "name": "Orient to Selected",
    "author": "Jonathan Lampel",
    "version": (1, 3, 0),
    "blender": (3, 0, 0),
    "location": "3D View > Edit Mode > Mesh > Snap; 3D View > Object > Snap; Transform Orientations",
    "description": "Align object orientations and snap object origins to the selection",
    "warning": "",
    "wiki_url": "",
    "category": "3D View",
}

from . import orient_to_selection, orient_to_active, origin_to_pivot, origin_to_active, origin_to_selection

def register():
    orient_to_selection.register()
    orient_to_active.register()
    origin_to_active.register()
    origin_to_pivot.register()
    origin_to_selection.register()

def unregister():
    orient_to_selection.unregister()
    orient_to_active.unregister()
    origin_to_active.unregister()
    origin_to_pivot.unregister()
    origin_to_selection.unregister()

if __name__ == "__main__":
    register()
