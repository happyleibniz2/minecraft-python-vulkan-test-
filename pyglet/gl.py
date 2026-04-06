"""GL interface shim that forwards attribute access to PyOpenGL's GL module
and provides a small `gl_info` helper used by the codebase.
"""
from OpenGL import GL
from OpenGL.GL import *

_GL = GL

class _GLInfo:
    def get_renderer(self):
        try:
            return GL.glGetString(GL.GL_RENDERER).decode()
        except Exception:
            return "Unknown Renderer"

    def get_version(self):
        try:
            return GL.glGetString(GL.GL_VERSION).decode()
        except Exception:
            return "Unknown Version"

    def have_version(self, major, minor):
        ver = self.get_version()
        try:
            parts = ver.split()[0].split('.')
            return (int(parts[0]), int(parts[1])) >= (major, minor)
        except Exception:
            return False

gl_info = _GLInfo()

def __getattr__(name):
    return getattr(_GL, name)
