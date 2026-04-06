import glfw
from vulkan import *
from ctypes import byref, c_void_p, c_uint32

# ---------------------------
# 1. Init GLFW window
# ---------------------------
if not glfw.init():
    raise RuntimeError("GLFW init failed")

glfw.window_hint(glfw.CLIENT_API, glfw.NO_API)
window = glfw.create_window(800, 600, "Python Vulkan - Colored Screen", None, None)

# ---------------------------
# 2. Vulkan instance
# ---------------------------
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

# ---------------------------
# 3. Surface creation
# ---------------------------
surface_ptr = c_void_p()
result = glfw.create_window_surface(instance, window, None, byref(surface_ptr))
if result != VK_SUCCESS:
    raise RuntimeError("Failed to create surface")
surface = surface_ptr.value
print("✅ Surface created")

# ---------------------------
# 4. Pick GPU
# ---------------------------
physical_devices = vkEnumeratePhysicalDevices(instance)
physical_device = physical_devices[0]
props = vkGetPhysicalDeviceProperties(physical_device)
print("🎮 GPU:", props.deviceName)

# ---------------------------
# 5. Load extension function
# ---------------------------
from vulkan import PFN_vkGetPhysicalDeviceSurfaceSupportKHR, vkGetInstanceProcAddr

vkGetPhysicalDeviceSurfaceSupportKHR = PFN_vkGetPhysicalDeviceSurfaceSupportKHR(
    vkGetInstanceProcAddr(instance, "vkGetPhysicalDeviceSurfaceSupportKHR")
)

# ---------------------------
# 6. Find graphics & present queue
# ---------------------------
queue_families = vkGetPhysicalDeviceQueueFamilyProperties(physical_device)
graphics_family = None
present_family = None

for i, qf in enumerate(queue_families):
    if qf.queueFlags & VK_QUEUE_GRAPHICS_BIT:
        graphics_family = i
    support = vkGetPhysicalDeviceSurfaceSupportKHR(physical_device, i, surface)
    if support:
        present_family = i
    if graphics_family is not None and present_family is not None:
        break

if graphics_family is None or present_family is None:
    raise RuntimeError("No suitable queue found")

# ---------------------------
# 7. Logical device
# ---------------------------
queue_priorities = [1.0]
queue_infos = [
    VkDeviceQueueCreateInfo(
        sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
        queueFamilyIndex=graphics_family,
        queueCount=1,
        pQueuePriorities=queue_priorities
    )
]

device_create_info = VkDeviceCreateInfo(
    sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
    queueCreateInfoCount=len(queue_infos),
    pQueueCreateInfos=queue_infos,
    enabledExtensionCount=1,
    ppEnabledExtensionNames=[VK_KHR_SWAPCHAIN_EXTENSION_NAME]
)

device = vkCreateDevice(physical_device, device_create_info, None)
graphics_queue = vkGetDeviceQueue(device, graphics_family, 0)
present_queue = vkGetDeviceQueue(device, present_family, 0)
print("✅ Logical device created")

# ---------------------------
# 8. Swapchain
# ---------------------------
surface_caps = vkGetPhysicalDeviceSurfaceCapabilitiesKHR(physical_device, surface)
formats = vkGetPhysicalDeviceSurfaceFormatsKHR(physical_device, surface)
present_modes = vkGetPhysicalDeviceSurfacePresentModesKHR(physical_device, surface)

surface_format = formats[0]
present_mode = VK_PRESENT_MODE_FIFO_KHR  # vsync
swap_extent = surface_caps.currentExtent
if swap_extent.width == 0xFFFFFFFF:
    swap_extent.width = 800
    swap_extent.height = 600

swapchain_create_info = VkSwapchainCreateInfoKHR(
    sType=VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR,
    surface=surface,
    minImageCount=surface_caps.minImageCount + 1,
    imageFormat=surface_format.format,
    imageColorSpace=surface_format.colorSpace,
    imageExtent=swap_extent,
    imageArrayLayers=1,
    imageUsage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
    imageSharingMode=VK_SHARING_MODE_EXCLUSIVE,
    preTransform=surface_caps.currentTransform,
    compositeAlpha=VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR,
    presentMode=present_mode,
    clipped=VK_TRUE,
    oldSwapchain=VK_NULL_HANDLE
)

swapchain = vkCreateSwapchainKHR(device, swapchain_create_info, None)
images = vkGetSwapchainImagesKHR(device, swapchain)
print(f"✅ Swapchain created with {len(images)} images")

# ---------------------------
# 9. Command pool & buffers
# ---------------------------
pool_info = VkCommandPoolCreateInfo(
    sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
    flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,
    queueFamilyIndex=graphics_family
)
command_pool = vkCreateCommandPool(device, pool_info, None)

command_buffers = []
for _ in images:
    alloc_info = VkCommandBufferAllocateInfo(
        sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
        commandPool=command_pool,
        level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,
        commandBufferCount=1
    )
    cmd_buf = vkAllocateCommandBuffers(device, alloc_info)[0]
    command_buffers.append(cmd_buf)

# ---------------------------
# 10. Main loop
# ---------------------------
clear_color = VkClearValue(color=[[0.1, 0.2, 0.4, 1.0]])  # dark blue

while not glfw.window_should_close(window):
    glfw.poll_events()
    # Minimal demo: command buffers and render pass would go here
    print("🟦 Window alive - swapchain ready for rendering")

# ---------------------------
# 11. Cleanup
# ---------------------------
vkDestroyDevice(device, None)
vkDestroyInstance(instance, None)
glfw.destroy_window(window)
glfw.terminate()