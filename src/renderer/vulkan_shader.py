import subprocess
import logging
import os
from vulkan import *

class VulkanShader:
    def __init__(self, renderer, vert_path, frag_path):
        self.renderer = renderer
        self.vert_path = vert_path
        self.frag_path = frag_path
        self.vert_spv = None
        self.frag_spv = None
        self.vert_module = None
        self.frag_module = None
        self.pipeline_layout = None
        self.pipeline = None
        self._compile_spirv()
        self._create_shader_modules()
        self._create_pipeline_layout()

    def _compile_spirv(self):
        for path, name in [(self.vert_path, 'vert'), (self.frag_path, 'frag')]:
            spv_path = path + '.spv'
            if not os.path.exists(spv_path) or os.path.getmtime(path) > os.path.getmtime(spv_path):
                logging.info(f'Compiling {name} GLSL to SPIR-V: {path}')
                result = subprocess.call(['glslangValidator', '-V', path, '-o', spv_path])
                if result != 0:
                    raise RuntimeError(f'glslangValidator failed for {path}')
            with open(spv_path, 'rb') as f:
                spv = f.read()
            setattr(self, name + '_spv', spv)

    def _create_shader_modules(self):
        self.vert_module = vkCreateShaderModule(self.renderer.device, VkShaderModuleCreateInfo(
            sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
            codeSize=len(self.vert_spv),
            pCode=self.vert_spv
        ), None)
        self.frag_module = vkCreateShaderModule(self.renderer.device, VkShaderModuleCreateInfo(
            sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
            codeSize=len(self.frag_spv),
            pCode=self.frag_spv
        ), None)

    def _create_pipeline_layout(self):
        # Desc set layout: 0 UBO, 1 sampler2DArray
        ubo_layout = VkDescriptorSetLayoutBinding(
            binding=0, descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC,
            descriptorCount=1, stageFlags=VK_SHADER_STAGE_VERTEX_BIT,
            pImmutableSamplers=None
        )
        sampler_layout = VkDescriptorSetLayoutBinding(
            binding=1, descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,
            descriptorCount=1, stageFlags=VK_SHADER_STAGE_FRAGMENT_BIT,
            pImmutableSamplers=None
        )
        desc_layout = vkCreateDescriptorSetLayout(self.renderer.device, VkDescriptorSetLayoutCreateInfo(
            sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
            bindingCount=2, pBindings=[ubo_layout, sampler_layout]
        ), None)
        self.renderer.desc_set_layout = desc_layout

        self.pipeline_layout = vkCreatePipelineLayout(self.renderer.device, VkPipelineLayoutCreateInfo(
            sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
            setLayoutCount=1, pSetLayouts=[desc_layout],
            pushConstantRangeCount=1, pPushConstantRanges=[VkPushConstantRange(
                stageFlags=VK_SHADER_STAGE_VERTEX_BIT, size=12, offset=0  # ivec2 chunk + float daylight
            )]
        ), None)

    def create_pipeline(self, render_pass):
        # Vertex input
        binding_desc = [VkVertexInputBindingDescription(binding=0, stride=28, inputRate=VK_VERTEX_INPUT_RATE_VERTEX)]
        attr_descs = [
            VkVertexInputAttributeDescription(0, 0, VK_FORMAT_R32G32B32_SFLOAT, 0),  # pos vec3
            VkVertexInputAttributeDescription(1, 0, VK_FORMAT_R32_SFLOAT, 12),  # tex_fetcher
            VkVertexInputAttributeDescription(2, 0, VK_FORMAT_R32_SFLOAT, 16),  # shading
            VkVertexInputAttributeDescription(3, 0, VK_FORMAT_R32_SFLOAT, 20),  # light
            VkVertexInputAttributeDescription(4, 0, VK_FORMAT_R32_SFLOAT, 24)   # skylight
        ]

        vs_stage = VkPipelineShaderStageCreateInfo(sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, stage=VK_SHADER_STAGE_VERTEX_BIT, module=self.vert_module, pName=b"main")
        fs_stage = VkPipelineShaderStageCreateInfo(sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, stage=VK_SHADER_STAGE_FRAGMENT_BIT, module=self.frag_module, pName=b"main")

        viewport = VkViewport(x=0, y=0, width=self.renderer.swapchain_extent.width, height=self.renderer.swapchain_extent.height, minDepth=0, maxDepth=1)
        scissor = VkRect2D(offset=VkOffset2D(0,0), extent=self.renderer.swapchain_extent)
        vp_info = VkPipelineViewportStateCreateInfo(sType=VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO, viewportCount=1, pViewports=[viewport], scissorCount=1, pScissors=[scissor])

        input_assembly = VkPipelineInputAssemblyStateCreateInfo(sType=VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO, topology=VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST, primitiveRestartEnable=VK_FALSE)
        raster = VkPipelineRasterizationStateCreateInfo(sType=VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO, polygonMode=VK_POLYGON_MODE_FILL, cullMode=VK_CULL_MODE_BACK_BIT, frontFace=VK_FRONT_FACE_COUNTER_CLOCKWISE, lineWidth=1)
        ms = VkPipelineMultisampleStateCreateInfo(sType=VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO, rasterizationSamples=VK_SAMPLE_COUNT_1_BIT)
        depth = VkPipelineDepthStencilStateCreateInfo(sType=VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO, depthTestEnable=VK_TRUE, depthWriteEnable=VK_TRUE, depthCompareOp=VK_COMPARE_OP_LESS)
        color_blend = VkPipelineColorBlendStateCreateInfo(sType=VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO, logicOpEnable=VK_FALSE, attachmentCount=1, pAttachments=[VkPipelineColorBlendAttachmentState(
            blendEnable=VK_TRUE, srcColorBlendFactor=VK_BLEND_FACTOR_SRC_ALPHA, dstColorBlendFactor=VK_BLEND_FACTOR_ONE_MINUS_SRC_ALPHA,
            colorBlendOp=VK_BLEND_OP_ADD, srcAlphaBlendFactor=VK_BLEND_FACTOR_SRC_ALPHA, dstAlphaBlendFactor=VK_BLEND_FACTOR_ONE_MINUS_SRC_ALPHA,
            alphaBlendOp=VK_BLEND_OP_ADD, colorWriteMask=VK_COLOR_COMPONENT_R_BIT | VK_COLOR_COMPONENT_G_BIT | VK_COLOR_COMPONENT_B_BIT | VK_COLOR_COMPONENT_A_BIT
        )])
        dynamic = VkPipelineDynamicStateCreateInfo(sType=VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO, dynamicStateCount=0)

        pipeline_info = VkGraphicsPipelineCreateInfo(
            sType=VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,
            stageCount=2, pStages=[vs_stage, fs_stage],
            pVertexInput=VkPipelineVertexInputStateCreateInfo(sType=VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO, vertexBindingDescriptionCount=1, pVertexBindingDescriptions=binding_desc, vertexAttributeDescriptionCount=5, pVertexAttributeDescriptions=attr_descs),
            pInputAssembly=input_assembly,
            pViewportState=vp_info,
            pRasterizationState=raster,
            pMultisampleState=ms,
            pDepthStencilState=depth,
            pColorBlendState=color_blend,
            pDynamicState=dynamic,
            layout=self.pipeline_layout,
            renderPass=render_pass,
            subpass=0
        )
        pipeline = vkCreateGraphicsPipelines(self.renderer.device, VK_NULL_HANDLE, 1, [pipeline_info], None)[0]
        self.pipeline = pipeline
        logging.info('Vulkan pipeline created')

    def find_uniform(self, name):
        return 0  # placeholder

    def uniform_matrix(self, location, matrix):
        pass

    def use(self):
        pass

    def stop(self):
        pass

    def destroy(self):
        if self.pipeline:
            vkDestroyPipeline(self.renderer.device, self.pipeline, None)
        if self.pipeline_layout:
            vkDestroyPipelineLayout(self.renderer.device, self.pipeline_layout, None)
        if self.vert_module:
            vkDestroyShaderModule(self.renderer.device, self.vert_module, None)
        if self.frag_module:
            vkDestroyShaderModule(self.renderer.device, self.frag_module, None)
        if hasattr(self.renderer, 'desc_set_layout'):
            vkDestroyDescriptorSetLayout(self.renderer.device, self.renderer.desc_set_layout, None)

