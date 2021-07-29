# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name": "Orient to Selected",
    "author": "Jonathan Lampel",
    "version": (1, 0),
    "blender": (2, 93, 0),
    "location": "3D View > Edit Mode > Transform Orientations > Local",
    "description": "Aligns the object's orientation to the normal direction of your selection",
    "warning": "",
    "wiki_url": "",
    "category": "3D View",
}

from . import orient_to_selection

def register():
    orient_to_selection.register()

def unregister():
    orient_to_selection.unregister()

if __name__ == "__main__":
    register()