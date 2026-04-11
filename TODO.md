# Vulkan World Rendering Fix TODO

## Status: 0/12 [Start]

1. [x] Install glslangValidator if missing (check PATH).
2. [x] Update src/renderer/vulkan_shader.py: GLSL->SPIR-V compile, pipeline layout, full VkPipeline creation.
3. [x] Update src/renderer/vulkan_renderer.py: Texture 2D_ARRAY upload.
4. [ ] src/renderer/vulkan_renderer.py: Add graphics pipeline integration, descriptor sets, UBO, VBO upload, draw calls.
5. [ ] Add descriptor set layout/bindings: UBO (bind0, uniform buffer dynamic), sampler2DArray (bind1).
6. [ ] Create UBO buffer (sizeof(mat4+ivec2+float pad); dynamic offsets).
7. [ ] Per-frame: world.prepare_rendering(), alloc transient cmd buf for uploads.
8. [ ] Upload chunk VBOs (flat floats->staging buffer->VkBuffer), IBO shared? Per-chunk or single big.
9. [ ] Record cmds: beginRP(clear sky), bind pipeline+desc(vkCmdBindDescriptorSets dynamicUBO), per-chunk: vkCmdBindVertexBuffers/IBO, pushConstants chunk_pos/daylight or UBO update, vkCmdDrawIndexed(quads*6).
10. [ ] main.py: Pass world/player to VulkanRenderer, call prepare(world) before draw().
11. [ ] Test single chunk textured quad, then full.
12. [ ] Cleanup resources.

## Progress Tracking
Update after each step.

Run: PMCM_USE_VULKAN=1 python main.py
