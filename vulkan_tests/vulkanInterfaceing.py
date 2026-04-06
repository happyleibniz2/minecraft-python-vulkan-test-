import glfw
from vulkan import *
from ctypes import byref, c_void_p

# 1. Init window
if not glfw.init():
    raise RuntimeError("GLFW init failed")

glfw.window_hint(glfw.CLIENT_API, glfw.NO_API)
window = glfw.create_window(800, 600, "Python Vulkan", None, None)

# 2. Vulkan instance
app_info = VkApplicationInfo(
    sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,
    pApplicationName="Python Vulkan",
    applicationVersion=VK_MAKE_VERSION(1, 0, 0),
    pEngineName="No Engine",
    engineVersion=VK_MAKE_VERSION(1, 0, 0),
    apiVersion=VK_API_VERSION_1_0,
)

extensions = glfw.get_required_instance_extensions()
create_info = VkInstanceCreateInfo(
    sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
    pApplicationInfo=app_info,
    enabledExtensionCount=len(extensions),
    ppEnabledExtensionNames=extensions,
)

instance = vkCreateInstance(create_info, None)
print("✅ Instance created")

# 3. Surface creation
surface_ptr = c_void_p()
result = glfw.create_window_surface(instance, window, None, byref(surface_ptr))
if result != VK_SUCCESS:
    raise RuntimeError("Failed to create surface")

# ✅ Get integer handle correctly
surface = surface_ptr.value
print("✅ Surface created:", surface)

# 4. Pick GPU
physical_devices = vkEnumeratePhysicalDevices(instance)
if not physical_devices:
    raise RuntimeError("No Vulkan GPU found")
physical_device = physical_devices[0]
props = vkGetPhysicalDeviceProperties(physical_device)
print("🎮 GPU:", props.deviceName)

# 5. Find graphics queue
queue_families = vkGetPhysicalDeviceQueueFamilyProperties(physical_device)
graphics_family_index = None
for i, qf in enumerate(queue_families):
    if qf.queueFlags & VK_QUEUE_GRAPHICS_BIT:
        graphics_family_index = i
        break
if graphics_family_index is None:
    raise RuntimeError("No graphics queue found")

# 6. Logical device
queue_priority = [1.0]
queue_create_info = VkDeviceQueueCreateInfo(
    sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
    queueFamilyIndex=graphics_family_index,
    queueCount=1,
    pQueuePriorities=queue_priority,
)
device_create_info = VkDeviceCreateInfo(
    sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
    queueCreateInfoCount=1,
    pQueueCreateInfos=[queue_create_info],
)
device = vkCreateDevice(physical_device, device_create_info, None)
print("✅ Logical device created")
graphics_queue = vkGetDeviceQueue(device, graphics_family_index, 0)

# 7. Main loop
while not glfw.window_should_close(window):
    glfw.poll_events()

# 8. Cleanup
vkDestroyDevice(device, None)
vkDestroySurfaceKHR_fn = vkGetInstanceProcAddr(instance, "vkDestroySurfaceKHR")
if vkDestroySurfaceKHR_fn:
    vkDestroySurfaceKHR_fn(instance, surface, None)
vkDestroyInstance(instance, None)

glfw.destroy_window(window)
glfw.terminate()