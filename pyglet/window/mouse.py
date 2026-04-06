import glfw


class _Mouse:
    LEFT = glfw.MOUSE_BUTTON_LEFT
    RIGHT = glfw.MOUSE_BUTTON_RIGHT
    MIDDLE = glfw.MOUSE_BUTTON_MIDDLE


mouse = _Mouse()

# Expose constants at module level for code that expects `pyglet.window.mouse.RIGHT`
LEFT = mouse.LEFT
RIGHT = mouse.RIGHT
MIDDLE = mouse.MIDDLE
