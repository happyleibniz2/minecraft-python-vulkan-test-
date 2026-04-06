"""Minimal Vulkan renderer scaffold.

This file provides a `VulkanRenderer` class that initializes a Vulkan
instance, selects a physical device, creates a logical device and queue,
and creates a surface from a GLFW window. It's a lightweight starting
point for porting the OpenGL renderer to Vulkan.

The implementation is intentionally minimal and defensive: it will raise
clear errors if the environment or Python Vulkan bindings are missing.
"""


import logging
try:
    import vulkan as vk
except Exception:
    vk = None

import glfw
import ctypes


class VulkanError(RuntimeError):
    pass


class VulkanRenderer:
    """Basic Vulkan renderer with swapchain, render pass and simple clear shader.

    This is a minimal implementation that attempts to create a Vulkan instance,
    surface, swapchain, image views, a simple render pass and framebuffers,
    command buffers and synchronization objects so the app can acquire-present
    frames. It is defensive: any failure will raise a `VulkanError` so callers
    can fall back to GL.
    """

    def __init__(self, window_handle, width, height, max_frames_in_flight=2):
        if vk is None:
            raise VulkanError("Vulkan bindings are not installed")

        self.window = window_handle
        self.width = width
        self.height = height
        self.max_frames_in_flight = max_frames_in_flight

        self.instance = None
        self.surface = None
        self.physical_device = None
        self.device = None
        self.graphics_queue = None
        self.present_queue = None

        self.swapchain = None
        self.swapchain_images = []
        self.swapchain_image_views = []
        self.swapchain_image_format = None
        self.swapchain_extent = None

        self.render_pass = None
        self.framebuffers = []

        self.command_pool = None
        self.command_buffers = []

        self.image_available_semaphores = []
        self.render_finished_semaphores = []
        self.in_flight_fences = []
        self.current_frame = 0

        # Initialize
        self._create_instance()
        self._create_surface()
        self._pick_physical_device()
        self._create_logical_device()
        self._create_swapchain()
        self._create_image_views()
        self._create_render_pass()
        self._create_framebuffers()
        self._create_command_pool()
        self._create_command_buffers()
        self._create_sync_objects()

    def _create_instance(self):
        app_info = vk.VkApplicationInfo(
            sType=vk.VK_STRUCTURE_TYPE_APPLICATION_INFO,
            pApplicationName=b"pmcm",
            applicationVersion=vk.VK_MAKE_VERSION(0, 1, 0),
            pEngineName=b"pmcm-engine",
            engineVersion=vk.VK_MAKE_VERSION(0, 1, 0),
            apiVersion=vk.VK_API_VERSION_1_0,
        )

        # Required extensions from GLFW
        ext_names = []
        try:
            glfw_exts = glfw.get_required_instance_extensions()
            if glfw_exts:
                ext_names = [e.encode() for e in glfw_exts]
        except Exception:
            pass

        create_info = vk.VkInstanceCreateInfo(
            sType=vk.VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
            pApplicationInfo=app_info,
            enabledExtensionCount=len(ext_names),
            ppEnabledExtensionNames=ext_names if ext_names else None,
        )

        try:
            self.instance = vk.vkCreateInstance(create_info, None)
        except Exception as e:
            logging.error("vkCreateInstance failed: %s", e)
            raise VulkanError("Failed to create Vulkan instance")

    def _create_surface(self):
        # glfw.create_window_surface is provided by the glfw Vulkan bindings
        try:
            self.surface = glfw.create_window_surface(self.instance, self.window, None)
        except Exception as e:
            logging.error("Failed to create window surface: %s", e)
            raise VulkanError("Failed to create Vulkan surface")

    def _pick_physical_device(self):
        devices = vk.vkEnumeratePhysicalDevices(self.instance)
        if not devices:
            raise VulkanError("No Vulkan physical devices found")

        # Prefer discrete GPU
        chosen = None
        for dev in devices:
            props = vk.vkGetPhysicalDeviceProperties(dev)
            if props.deviceType == vk.VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU:
                chosen = dev
                break

        if chosen is None:
            chosen = devices[0]

        self.physical_device = chosen

    def _find_queue_families(self):
        families = vk.vkGetPhysicalDeviceQueueFamilyProperties(self.physical_device)
        graphics_index = None
        present_index = None

        for i, f in enumerate(families):
            # graphics
            if f.queueFlags & vk.VK_QUEUE_GRAPHICS_BIT:
                if graphics_index is None:
                    graphics_index = i

            # present support
            present_support = vk.vkGetPhysicalDeviceSurfaceSupportKHR(self.physical_device, i, self.surface)
            if present_support:
                if present_index is None:
                    present_index = i

            if graphics_index is not None and present_index is not None:
                break

        return graphics_index, present_index

    def _create_logical_device(self):
        graphics_index, present_index = self._find_queue_families()
        if graphics_index is None:
            raise VulkanError("No graphics queue found")

        unique_indices = {graphics_index}
        if present_index is not None:
            unique_indices.add(present_index)

        queue_create_infos = []
        for idx in unique_indices:
            qi = vk.VkDeviceQueueCreateInfo(
                sType=vk.VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
                queueFamilyIndex=idx,
                queueCount=1,
                pQueuePriorities=[1.0],
            )
            queue_create_infos.append(qi)

        device_features = vk.VkPhysicalDeviceFeatures()

        create_info = vk.VkDeviceCreateInfo(
            sType=vk.VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
            queueCreateInfoCount=len(queue_create_infos),
            pQueueCreateInfos=queue_create_infos,
            pEnabledFeatures=device_features,
        )

        try:
            self.device = vk.vkCreateDevice(self.physical_device, create_info, None)
        except Exception as e:
            logging.error("vkCreateDevice failed: %s", e)
            raise VulkanError("Failed to create logical device")

        self.graphics_queue = vk.vkGetDeviceQueue(self.device, graphics_index, 0)
        if present_index is None:
            self.present_queue = self.graphics_queue
        else:
            self.present_queue = vk.vkGetDeviceQueue(self.device, present_index, 0)

    def _create_swapchain(self):
        # Query surface capabilities
        caps = vk.vkGetPhysicalDeviceSurfaceCapabilitiesKHR(self.physical_device, self.surface)
        formats = vk.vkGetPhysicalDeviceSurfaceFormatsKHR(self.physical_device, self.surface)
        present_modes = vk.vkGetPhysicalDeviceSurfacePresentModesKHR(self.physical_device, self.surface)

        # Choose format
        surface_format = formats[0]
        for f in formats:
            if f.format == vk.VK_FORMAT_B8G8R8A8_UNORM and f.colorSpace == vk.VK_COLOR_SPACE_SRGB_NONLINEAR_KHR:
                surface_format = f
                break

        present_mode = vk.VK_PRESENT_MODE_FIFO_KHR
        if vk.VK_PRESENT_MODE_MAILBOX_KHR in present_modes:
            present_mode = vk.VK_PRESENT_MODE_MAILBOX_KHR

        extent = caps.currentExtent
        if extent.width == 4294967295:  # VK_MAX_UINT32 indicates that extent is variable
            extent = vk.VkExtent2D(width=self.width, height=self.height)

        image_count = caps.minImageCount + 1
        if caps.maxImageCount > 0 and image_count > caps.maxImageCount:
            image_count = caps.maxImageCount

        swapchain_info = vk.VkSwapchainCreateInfoKHR(
            sType=vk.VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR,
            surface=self.surface,
            minImageCount=image_count,
            imageFormat=surface_format.format,
            imageColorSpace=surface_format.colorSpace,
            imageExtent=extent,
            imageArrayLayers=1,
            imageUsage=vk.VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
            imageSharingMode=vk.VK_SHARING_MODE_EXCLUSIVE,
            preTransform=caps.currentTransform,
            compositeAlpha=vk.VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR,
            presentMode=present_mode,
            clipped=vk.VK_TRUE,
            oldSwapchain=vk.VK_NULL_HANDLE,
        )

        try:
            self.swapchain = vk.vkCreateSwapchainKHR(self.device, swapchain_info, None)
        except Exception as e:
            logging.error("vkCreateSwapchainKHR failed: %s", e)
            raise VulkanError("Failed to create swapchain")

        self.swapchain_images = vk.vkGetSwapchainImagesKHR(self.device, self.swapchain)
        self.swapchain_image_format = surface_format.format
        self.swapchain_extent = extent

    def _create_image_views(self):
        for image in self.swapchain_images:
            create_info = vk.VkImageViewCreateInfo(
                sType=vk.VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,
                image=image,
                viewType=vk.VK_IMAGE_VIEW_TYPE_2D,
                format=self.swapchain_image_format,
                components=vk.VkComponentMapping(),
                subresourceRange=vk.VkImageSubresourceRange(
                    aspectMask=vk.VK_IMAGE_ASPECT_COLOR_BIT, baseMipLevel=0, levelCount=1, baseArrayLayer=0, layerCount=1
                ),
            )
            try:
                iv = vk.vkCreateImageView(self.device, create_info, None)
                self.swapchain_image_views.append(iv)
            except Exception as e:
                logging.error("vkCreateImageView failed: %s", e)
                raise VulkanError("Failed to create image views")

    def _create_render_pass(self):
        color_attachment = vk.VkAttachmentDescription(
            format=self.swapchain_image_format,
            samples=vk.VK_SAMPLE_COUNT_1_BIT,
            loadOp=vk.VK_ATTACHMENT_LOAD_OP_CLEAR,
            storeOp=vk.VK_ATTACHMENT_STORE_OP_STORE,
            stencilLoadOp=vk.VK_ATTACHMENT_LOAD_OP_DONT_CARE,
            stencilStoreOp=vk.VK_ATTACHMENT_STORE_OP_DONT_CARE,
            initialLayout=vk.VK_IMAGE_LAYOUT_UNDEFINED,
            finalLayout=vk.VK_IMAGE_LAYOUT_PRESENT_SRC_KHR,
        )

        color_ref = vk.VkAttachmentReference(attachment=0, layout=vk.VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL)

        subpass = vk.VkSubpassDescription(
            pipelineBindPoint=vk.VK_PIPELINE_BIND_POINT_GRAPHICS,
            colorAttachmentCount=1,
            pColorAttachments=[color_ref],
        )

        rp_info = vk.VkRenderPassCreateInfo(
            sType=vk.VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO,
            attachmentCount=1,
            pAttachments=[color_attachment],
            subpassCount=1,
            pSubpasses=[subpass],
        )

        try:
            self.render_pass = vk.vkCreateRenderPass(self.device, rp_info, None)
        except Exception as e:
            logging.error("vkCreateRenderPass failed: %s", e)
            raise VulkanError("Failed to create render pass")

    def _create_framebuffers(self):
        for iv in self.swapchain_image_views:
            fb_info = vk.VkFramebufferCreateInfo(
                sType=vk.VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO,
                renderPass=self.render_pass,
                attachmentCount=1,
                pAttachments=[iv],
                width=self.swapchain_extent.width,
                height=self.swapchain_extent.height,
                layers=1,
            )
            try:
                fb = vk.vkCreateFramebuffer(self.device, fb_info, None)
                self.framebuffers.append(fb)
            except Exception as e:
                logging.error("vkCreateFramebuffer failed: %s", e)
                raise VulkanError("Failed to create framebuffer")

    def _create_command_pool(self):
        graphics_index, _ = self._find_queue_families()
        pool_info = vk.VkCommandPoolCreateInfo(sType=vk.VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, queueFamilyIndex=graphics_index)
        try:
            self.command_pool = vk.vkCreateCommandPool(self.device, pool_info, None)
        except Exception as e:
            logging.error("vkCreateCommandPool failed: %s", e)
            raise VulkanError("Failed to create command pool")

    def _create_command_buffers(self):
        alloc_info = vk.VkCommandBufferAllocateInfo(
            sType=vk.VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO, commandPool=self.command_pool, level=vk.VK_COMMAND_BUFFER_LEVEL_PRIMARY, commandBufferCount=len(self.framebuffers)
        )
        try:
            self.command_buffers = vk.vkAllocateCommandBuffers(self.device, alloc_info)
        except Exception as e:
            logging.error("vkAllocateCommandBuffers failed: %s", e)
            raise VulkanError("Failed to allocate command buffers")

        # Record simple command buffers that begin and end a render pass (clear to a color)
        for i, cb in enumerate(self.command_buffers):
            begin_info = vk.VkCommandBufferBeginInfo(sType=vk.VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO)
            vk.vkBeginCommandBuffer(cb, begin_info)

            clear_color = vk.VkClearValue(color=vk.VkClearColorValue(float32=[0.0, 0.0, 0.0, 1.0]))

            rp_begin = vk.VkRenderPassBeginInfo(
                sType=vk.VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO,
                renderPass=self.render_pass,
                framebuffer=self.framebuffers[i],
                renderArea=vk.VkRect2D(offset=vk.VkOffset2D(x=0, y=0), extent=self.swapchain_extent),
                clearValueCount=1,
                pClearValues=[clear_color],
            )

            vk.vkCmdBeginRenderPass(cb, rp_begin, vk.VK_SUBPASS_CONTENTS_INLINE)
            # no actual draw commands yet
            vk.vkCmdEndRenderPass(cb)
            try:
                vk.vkEndCommandBuffer(cb)
            except Exception as e:
                logging.error("vkEndCommandBuffer failed: %s", e)
                raise VulkanError("Failed to finalize command buffer")

    def _create_sync_objects(self):
        for _ in range(self.max_frames_in_flight):
            image_avail = vk.vkCreateSemaphore(self.device, vk.VkSemaphoreCreateInfo(sType=vk.VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO), None)
            render_fin = vk.vkCreateSemaphore(self.device, vk.VkSemaphoreCreateInfo(sType=vk.VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO), None)
            fence = vk.vkCreateFence(self.device, vk.VkFenceCreateInfo(sType=vk.VK_STRUCTURE_TYPE_FENCE_CREATE_INFO, flags=vk.VK_FENCE_CREATE_SIGNALED_BIT), None)
            self.image_available_semaphores.append(image_avail)
            self.render_finished_semaphores.append(render_fin)
            self.in_flight_fences.append(fence)

    def draw(self):
        # Acquire next image
        try:
            vk.vkWaitForFences(self.device, 1, [self.in_flight_fences[self.current_frame]], vk.VK_TRUE, 0xFFFFFFFFFFFFFFFF)
            vk.vkResetFences(self.device, 1, [self.in_flight_fences[self.current_frame]])

            img_index = vk.vkAcquireNextImageKHR(self.device, self.swapchain, 0xFFFFFFFFFFFFFFFF, self.image_available_semaphores[self.current_frame], vk.VK_NULL_HANDLE)

            submit_info = vk.VkSubmitInfo(
                sType=vk.VK_STRUCTURE_TYPE_SUBMIT_INFO,
                waitSemaphoreCount=1,
                pWaitSemaphores=[self.image_available_semaphores[self.current_frame]],
                pWaitDstStageMask=[vk.VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT],
                commandBufferCount=1,
                pCommandBuffers=[self.command_buffers[img_index]],
                signalSemaphoreCount=1,
                pSignalSemaphores=[self.render_finished_semaphores[self.current_frame]],
            )

            vk.vkQueueSubmit(self.graphics_queue, 1, [submit_info], self.in_flight_fences[self.current_frame])

            present_info = vk.VkPresentInfoKHR(
                sType=vk.VK_STRUCTURE_TYPE_PRESENT_INFO_KHR,
                waitSemaphoreCount=1,
                pWaitSemaphores=[self.render_finished_semaphores[self.current_frame]],
                swapchainCount=1,
                pSwapchains=[self.swapchain],
                pImageIndices=[img_index],
            )

            vk.vkQueuePresentKHR(self.present_queue, present_info)

            self.current_frame = (self.current_frame + 1) % self.max_frames_in_flight
        except Exception as e:
            logging.warning("Vulkan draw/present failed: %s", e)

    def upload_textures(self, raw_images, width=None, height=None):
        """Placeholder for texture upload. Currently stores images for later use.

        A full implementation would create staging buffers, VkImage objects,
        transition image layouts, copy buffer->image, generate mipmaps and
        create an image array or sampler. For now we keep the raw bytes in
        memory so the feature can be implemented incrementally.
        """
        try:
            self._uploaded_images = []
            for img in raw_images:
                # store tuple (bytes, width, height)
                self._uploaded_images.append((img, width or self.swapchain_extent.width, height or self.swapchain_extent.height))
            logging.info("Stored %d textures for later Vulkan upload", len(self._uploaded_images))
        except Exception as e:
            logging.warning("Failed to store textures: %s", e)

    # --- Helpers for real texture upload ---
    def _find_memory_type(self, type_filter, properties):
        mem_props = vk.vkGetPhysicalDeviceMemoryProperties(self.physical_device)
        for i in range(mem_props.memoryTypeCount):
            if (type_filter & (1 << i)) and (mem_props.memoryTypes[i].propertyFlags & properties) == properties:
                return i
        raise VulkanError("Failed to find suitable memory type")

    def _create_buffer(self, size, usage, properties):
        buf_info = vk.VkBufferCreateInfo(sType=vk.VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, size=size, usage=usage, sharingMode=vk.VK_SHARING_MODE_EXCLUSIVE)
        buffer = vk.vkCreateBuffer(self.device, buf_info, None)

        mem_reqs = vk.vkGetBufferMemoryRequirements(self.device, buffer)
        alloc_info = vk.VkMemoryAllocateInfo(sType=vk.VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, allocationSize=mem_reqs.size, memoryTypeIndex=self._find_memory_type(mem_reqs.memoryTypeBits, properties))
        buffer_memory = vk.vkAllocateMemory(self.device, alloc_info, None)
        vk.vkBindBufferMemory(self.device, buffer, buffer_memory, 0)

        return buffer, buffer_memory

    def _begin_single_time_commands(self):
        alloc_info = vk.VkCommandBufferAllocateInfo(sType=vk.VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO, commandPool=self.command_pool, level=vk.VK_COMMAND_BUFFER_LEVEL_PRIMARY, commandBufferCount=1)
        cmd_buf = vk.vkAllocateCommandBuffers(self.device, alloc_info)[0]
        begin_info = vk.VkCommandBufferBeginInfo(sType=vk.VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO, flags=vk.VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT)
        vk.vkBeginCommandBuffer(cmd_buf, begin_info)
        return cmd_buf

    def _end_single_time_commands(self, cmd_buf):
        vk.vkEndCommandBuffer(cmd_buf)
        submit_info = vk.VkSubmitInfo(sType=vk.VK_STRUCTURE_TYPE_SUBMIT_INFO, commandBufferCount=1, pCommandBuffers=[cmd_buf])
        vk.vkQueueSubmit(self.graphics_queue, 1, [submit_info], vk.VK_NULL_HANDLE)
        vk.vkQueueWaitIdle(self.graphics_queue)
        vk.vkFreeCommandBuffers(self.device, self.command_pool, 1, [cmd_buf])

    def _create_image(self, width, height, format=vk.VK_FORMAT_R8G8B8A8_UNORM, tiling=vk.VK_IMAGE_TILING_OPTIMAL, usage=vk.VK_IMAGE_USAGE_TRANSFER_DST_BIT | vk.VK_IMAGE_USAGE_SAMPLED_BIT, properties=vk.VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT):
        image_info = vk.VkImageCreateInfo(
            sType=vk.VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,
            imageType=vk.VK_IMAGE_TYPE_2D,
            extent=vk.VkExtent3D(width=width, height=height, depth=1),
            mipLevels=1,
            arrayLayers=1,
            format=format,
            tiling=tiling,
            initialLayout=vk.VK_IMAGE_LAYOUT_UNDEFINED,
            usage=usage,
            samples=vk.VK_SAMPLE_COUNT_1_BIT,
            sharingMode=vk.VK_SHARING_MODE_EXCLUSIVE,
        )
        image = vk.vkCreateImage(self.device, image_info, None)
        mem_reqs = vk.vkGetImageMemoryRequirements(self.device, image)
        alloc_info = vk.VkMemoryAllocateInfo(sType=vk.VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, allocationSize=mem_reqs.size, memoryTypeIndex=self._find_memory_type(mem_reqs.memoryTypeBits, properties))
        image_memory = vk.vkAllocateMemory(self.device, alloc_info, None)
        vk.vkBindImageMemory(self.device, image, image_memory, 0)
        return image, image_memory

    def _transition_image_layout(self, image, old_layout, new_layout):
        cmd_buf = self._begin_single_time_commands()

        barrier = vk.VkImageMemoryBarrier(
            sType=vk.VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
            oldLayout=old_layout,
            newLayout=new_layout,
            srcQueueFamilyIndex=vk.VK_QUEUE_FAMILY_IGNORED,
            dstQueueFamilyIndex=vk.VK_QUEUE_FAMILY_IGNORED,
            image=image,
            subresourceRange=vk.VkImageSubresourceRange(aspectMask=vk.VK_IMAGE_ASPECT_COLOR_BIT, baseMipLevel=0, levelCount=1, baseArrayLayer=0, layerCount=1),
        )

        src_stage = vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT
        dst_stage = vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT

        if old_layout == vk.VK_IMAGE_LAYOUT_UNDEFINED and new_layout == vk.VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL:
            barrier.srcAccessMask = 0
            barrier.dstAccessMask = vk.VK_ACCESS_TRANSFER_WRITE_BIT
            src_stage = vk.VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT
            dst_stage = vk.VK_PIPELINE_STAGE_TRANSFER_BIT
        elif old_layout == vk.VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL and new_layout == vk.VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL:
            barrier.srcAccessMask = vk.VK_ACCESS_TRANSFER_WRITE_BIT
            barrier.dstAccessMask = vk.VK_ACCESS_SHADER_READ_BIT
            src_stage = vk.VK_PIPELINE_STAGE_TRANSFER_BIT
            dst_stage = vk.VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT
        else:
            # handle other transitions if needed
            barrier.srcAccessMask = 0
            barrier.dstAccessMask = 0

        vk.vkCmdPipelineBarrier(cmd_buf, src_stage, dst_stage, 0, 0, None, 0, None, 1, [barrier])

        self._end_single_time_commands(cmd_buf)

    def _copy_buffer_to_image(self, buffer, image, width, height):
        cmd_buf = self._begin_single_time_commands()

        region = vk.VkBufferImageCopy(bufferOffset=0, bufferRowLength=0, bufferImageHeight=0, imageSubresource=vk.VkImageSubresourceLayers(aspectMask=vk.VK_IMAGE_ASPECT_COLOR_BIT, mipLevel=0, baseArrayLayer=0, layerCount=1), imageOffset=vk.VkOffset3D(x=0, y=0, z=0), imageExtent=vk.VkExtent3D(width=width, height=height, depth=1))
        vk.vkCmdCopyBufferToImage(cmd_buf, buffer, image, vk.VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, [region])

        self._end_single_time_commands(cmd_buf)

    def _create_image_view(self, image, format=vk.VK_FORMAT_R8G8B8A8_UNORM):
        view_info = vk.VkImageViewCreateInfo(sType=vk.VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO, image=image, viewType=vk.VK_IMAGE_VIEW_TYPE_2D, format=format, components=vk.VkComponentMapping(), subresourceRange=vk.VkImageSubresourceRange(aspectMask=vk.VK_IMAGE_ASPECT_COLOR_BIT, baseMipLevel=0, levelCount=1, baseArrayLayer=0, layerCount=1))
        view = vk.vkCreateImageView(self.device, view_info, None)
        return view

    def _create_sampler(self):
        info = vk.VkSamplerCreateInfo(sType=vk.VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO, magFilter=vk.VK_FILTER_NEAREST, minFilter=vk.VK_FILTER_NEAREST, addressModeU=vk.VK_SAMPLER_ADDRESS_MODE_REPEAT, addressModeV=vk.VK_SAMPLER_ADDRESS_MODE_REPEAT, addressModeW=vk.VK_SAMPLER_ADDRESS_MODE_REPEAT, anisotropyEnable=vk.VK_FALSE, maxAnisotropy=1.0, borderColor=vk.VK_BORDER_COLOR_INT_OPAQUE_BLACK, unnormalizedCoordinates=vk.VK_FALSE, compareEnable=vk.VK_FALSE, compareOp=vk.VK_COMPARE_OP_ALWAYS, mipmapMode=vk.VK_SAMPLER_MIPMAP_MODE_LINEAR, mipLodBias=0.0, minLod=0.0, maxLod=0.0)
        sampler = vk.vkCreateSampler(self.device, info, None)
        return sampler

    def upload_textures_real(self, raw_images, width, height):
        """Perform staging buffer uploads and create VkImage, VkImageView and VkSampler for each image."""
        resources = []
        for img_bytes in raw_images:
            size = len(img_bytes)

            # create staging buffer
            try:
                staging_buf, staging_mem = self._create_buffer(size, vk.VK_BUFFER_USAGE_TRANSFER_SRC_BIT, vk.VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | vk.VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)

                # map and copy
                data_ptr = vk.vkMapMemory(self.device, staging_mem, 0, size, 0)
                # data_ptr is a c_void_p, copy bytes
                ctypes.memmove(data_ptr, img_bytes, size)
                vk.vkUnmapMemory(self.device, staging_mem)

                # create image
                image, image_mem = self._create_image(width, height)

                # transition, copy, transition
                self._transition_image_layout(image, vk.VK_IMAGE_LAYOUT_UNDEFINED, vk.VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL)
                self._copy_buffer_to_image(staging_buf, image, width, height)
                self._transition_image_layout(image, vk.VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, vk.VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL)

                # create view and sampler
                view = self._create_image_view(image)
                sampler = self._create_sampler()

                # cleanup staging
                try:
                    vk.vkDestroyBuffer(self.device, staging_buf, None)
                except Exception:
                    pass
                try:
                    vk.vkFreeMemory(self.device, staging_mem, None)
                except Exception:
                    pass

                resources.append({"image": image, "memory": image_mem, "view": view, "sampler": sampler})
            except Exception as e:
                logging.warning("Failed to upload texture: %s", e)

        self._texture_resources = resources
        logging.info("Uploaded %d textures to Vulkan (placeholder resources)", len(resources))

    def cleanup(self):
        try:
            vk.vkDeviceWaitIdle(self.device)
        except Exception:
            pass

        # Destroy sync objects
        for fence in self.in_flight_fences:
            try:
                vk.vkDestroyFence(self.device, fence, None)
            except Exception:
                pass
        for sem in self.image_available_semaphores:
            try:
                vk.vkDestroySemaphore(self.device, sem, None)
            except Exception:
                pass
        for sem in self.render_finished_semaphores:
            try:
                vk.vkDestroySemaphore(self.device, sem, None)
            except Exception:
                pass

        # Free command buffers and pool
        try:
            if self.command_pool and self.command_buffers:
                vk.vkFreeCommandBuffers(self.device, self.command_pool, len(self.command_buffers), self.command_buffers)
        except Exception:
            pass
        try:
            if self.command_pool:
                vk.vkDestroyCommandPool(self.device, self.command_pool, None)
        except Exception:
            pass

        # Destroy framebuffers
        for fb in self.framebuffers:
            try:
                vk.vkDestroyFramebuffer(self.device, fb, None)
            except Exception:
                pass

        # Destroy image views
        for iv in self.swapchain_image_views:
            try:
                vk.vkDestroyImageView(self.device, iv, None)
            except Exception:
                pass

        # Destroy swapchain
        try:
            if self.swapchain:
                vk.vkDestroySwapchainKHR(self.device, self.swapchain, None)
        except Exception:
            pass

        # Destroy device
        try:
            if self.device:
                vk.vkDestroyDevice(self.device, None)
        except Exception:
            pass

        # Destroy surface
        try:
            if self.surface:
                vk.vkDestroySurfaceKHR(self.instance, self.surface, None)
        except Exception:
            pass

        # Destroy instance
        try:
            if self.instance:
                vk.vkDestroyInstance(self.instance, None)
        except Exception:
            pass

