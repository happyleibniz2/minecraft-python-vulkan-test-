"""Minimal pyglet compatibility shim for this project.

Provides: `options` dict and exposes submodules `gl` and `window`.
This is a small shim that forwards GL calls to PyOpenGL and maps
keyboard/mouse constants to GLFW so the rest of the codebase can remain
mostly unchanged while we migrate windowing to GLFW and plan a Vulkan
renderer replacement.
"""

options = {}

from . import gl  # exposes GL functions via PyOpenGL
from . import window  # exposes key/mouse constants mapped to glfw
from . import image  # minimal image loader (Pillow)
from . import input  # joystick/input shim

__all__ = ["options", "gl", "window", "image", "input"]
