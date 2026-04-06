import glfw

glfw.init()
glfw.window_hint(glfw.CLIENT_API, glfw.NO_API)

window = glfw.create_window(800, 600, "Pure Vulkan Python", None, None)

while not glfw.window_should_close(window):
    glfw.poll_events()

glfw.terminate()