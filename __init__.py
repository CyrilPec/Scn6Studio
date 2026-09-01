"""
SCN6 Nodes Addon
"""

bl_info = {
    "name": "SCN6 Nodes",
    "author": "SCN6",
    "version": (4, 0, 0),
    "blender": (3, 6, 0),
    "location": "Node Editor > Shift+A > SCN6",
    "description": "SCN6 Blender controller nodes",
    "category": "Node",
}


from . import bridge_node
from . import scn6_node_v4


# If you have addon_tools.py:
try:
    from . import addon_tools
except ImportError:
    addon_tools = None


def register():

    # ------------------------------------------------------------------------
    # Bridge
    # ------------------------------------------------------------------------

    bridge_node.register()

    # ------------------------------------------------------------------------
    # SCN6 node
    # ------------------------------------------------------------------------

    scn6_node_v4.register()

    # ------------------------------------------------------------------------
    # Development tools
    # ------------------------------------------------------------------------

    if addon_tools is not None:

        try:
            addon_tools.register()

        except Exception as exc:

            print(
                "[SCN6] addon_tools registration error:",
                exc,
            )


def unregister():

    # ------------------------------------------------------------------------
    # Development tools
    # ------------------------------------------------------------------------

    if addon_tools is not None:

        try:
            addon_tools.unregister()

        except Exception:
            pass

    # ------------------------------------------------------------------------
    # SCN6 node
    # ------------------------------------------------------------------------

    try:
        scn6_node_v4.unregister()

    except Exception:
        pass

    # ------------------------------------------------------------------------
    # Bridge
    # ------------------------------------------------------------------------

    try:
        bridge_node.unregister()

    except Exception:
        pass


if __name__ == "__main__":
    register()
