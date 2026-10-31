# Orient to Selection
 A small Blender addon for changing an object's local orientation while in edit mode.

In mesh Edit Mode, use **Mesh > Snap > Orient to Selected**. The operator switches the transform orientation to **Local** so the updated axes are visible. It is also available under **Transform Orientations > Local**.

![uQhSN61npy](https://user-images.githubusercontent.com/12982300/127409850-6f22147a-0145-4229-aa50-e18ceb57171a.gif)

There's also an **Object Origin to Pivot Point** operator in the Edit Mode -> Mesh -> Snap menu. It moves the object's origin to the current pivot point of the selected components. Individual Origins falls back to Median Point, as does Active Element when there's no active element.

![origin-to-selected](https://user-images.githubusercontent.com/12982300/207934047-48733cd3-e4c7-4008-b1e8-d82facf6d9e5.gif)

In Object Mode, use **Object > Snap > Orient to Active** to give all selected objects the same local orientation as the active object. It is also available in the Transform Orientations dropdown.

**Object > Snap > Active Origin to Pivot Point** moves the active object's origin to the current pivot point. Individual Origins falls back to Median Point.

**Object > Snap > Origin to Active** moves the origins of all selected objects to the active object's origin.

If you'd like to support development of this and similar add-ons, please consider purchasing the add-on from our website or the Blender Market:

[blendermarket.com/products/orient-and-origin-to-selected](https://blendermarket.com/products/orient-and-origin-to-selected)

[orangeturbine.com/downloads/orient-and-origin-to-selected](https://orangeturbine.com/downloads/orient-and-origin-to-selected)
