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
    "version": (1, 2),
    "blender": (3, 0, 0),
    "location": "3D View > Edit Mode > Transform Orientations > Local",
    "description": "Aligns the object's orientation to the normal direction of your selection",
    "warning": "",
    "wiki_url": "",
    "category": "3D View",
}

from . import orient_to_selection, origin_to_selection

def register():
    orient_to_selection.register()
    origin_to_selection.register()

def unregister():
    orient_to_selection.unregister()
    origin_to_selection.unregister()

if __name__ == "__main__":
    register() 