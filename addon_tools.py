"""
addon_tools.py

Blender-side development tools for SCN6 Controller.

Contains the safe hot-reload operator used while developing
the Blender addon.
"""

import bpy
import importlib


def _reload_addon():

    try:
        import SCN6_Controller

        print("[SCN6] ========================================")
        print("[SCN6] Reloading SCN6 Controller addon...")
        print("[SCN6] ========================================")

        # --------------------------------------------------------------
        # Stop/unregister currently registered addon classes.
        # --------------------------------------------------------------

        try:
            SCN6_Controller.unregister()
        except Exception as exc:
            print(
                "[SCN6] unregister warning:",
                exc,
            )

        # --------------------------------------------------------------
        # Reload child modules first.
        # --------------------------------------------------------------

        importlib.reload(
            SCN6_Controller.bridge_node
        )

        importlib.reload(
            SCN6_Controller.scn6_node_v4
        )

        # If these modules exist, reload them too.
        try:
            importlib.reload(
                SCN6_Controller.addon_tools
            )
        except Exception as exc:
            print(
                "[SCN6] addon_tools reload warning:",
                exc,
            )

        try:
            import SCN6_Controller.server_node

            importlib.reload(
                SCN6_Controller.server_node
            )

        except ModuleNotFoundError:
            pass

        # --------------------------------------------------------------
        # Reload main addon.
        # --------------------------------------------------------------

        importlib.reload(
            SCN6_Controller
        )

        # --------------------------------------------------------------
        # Register updated classes.
        # --------------------------------------------------------------

        SCN6_Controller.register()

        print(
            "[SCN6] Controller reloaded successfully!"
        )

    except Exception as exc:

        print(
            "[SCN6 ERROR] Addon reload failed:"
        )

        import traceback

        traceback.print_exc()

    return None


class SCN6_OT_ReloadAddon(
    bpy.types.Operator
):

    bl_idname = "scn6.reload_addon"

    bl_label = "Reload SCN6 Addon"

    bl_description = (
        "Reload SCN6 Blender addon modules without restarting Blender"
    )

    def execute(
        self,
        context,
    ):

        print(
            "[SCN6] Reload requested..."
        )

        # --------------------------------------------------------------
        # Important:
        #
        # Do NOT reload immediately while this operator is executing.
        #
        # Schedule it for the next Blender timer tick.
        # --------------------------------------------------------------

        bpy.app.timers.register(
            _reload_addon,
            first_interval=0.1,
        )

        self.report(
            {"INFO"},
            "SCN6 addon reload scheduled.",
        )

        return {"FINISHED"}


classes = (
    SCN6_OT_ReloadAddon,
)


def register():

    for cls in classes:

        bpy.utils.register_class(
            cls
        )


def unregister():

    for cls in reversed(classes):

        try:

            bpy.utils.unregister_class(
                cls
            )

        except Exception:

            pass
