import glfw


class _Key:
    D = glfw.KEY_D
    A = glfw.KEY_A
    W = glfw.KEY_W
    S = glfw.KEY_S
    SPACE = glfw.KEY_SPACE
    LSHIFT = glfw.KEY_LEFT_SHIFT
    LCTRL = glfw.KEY_LEFT_CONTROL
    F = glfw.KEY_F
    G = glfw.KEY_G
    O = glfw.KEY_O
    R = glfw.KEY_R
    ESCAPE = glfw.KEY_ESCAPE
    F6 = glfw.KEY_F6
    F11 = glfw.KEY_F11
    F3 = glfw.KEY_F3
    F10 = glfw.KEY_F10


key = _Key()

# Expose constants at module level for code that expects `pyglet.window.key.D`
D = key.D
A = key.A
W = key.W
S = key.S
SPACE = key.SPACE
LSHIFT = key.LSHIFT
LCTRL = key.LCTRL
F = key.F
G = key.G
O = key.O
R = key.R
ESCAPE = key.ESCAPE
F6 = key.F6
F11 = key.F11
F3 = key.F3
F10 = key.F10
