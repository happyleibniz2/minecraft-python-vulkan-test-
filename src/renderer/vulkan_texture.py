from PIL import Image


class VulkanTextureManager:
    def __init__(self, texture_width, texture_height, max_textures):
        self.texture_width = texture_width
        self.texture_height = texture_height
        self.max_textures = max_textures

        # list of texture names (for compatibility)
        self.textures = []

        # store raw image bytes for later upload by VulkanRenderer
        self._images = []

        # placeholder for compatibility
        self.texture_array = None

    def generate_mipmaps(self):
        # no-op for now; Vulkan upload code will handle mipmaps if implemented
        pass

    def add_texture(self, texture_name):
        # Load image from textures/<name>.png using Pillow
        path = f"textures/{texture_name}.png"
        try:
            img = Image.open(path).convert("RGBA")
        except FileNotFoundError:
            # create a small magenta placeholder
            img = Image.new("RGBA", (self.texture_width, self.texture_height), (255, 0, 255, 255))

        # ensure size
        img = img.resize((self.texture_width, self.texture_height))
        raw = img.tobytes("raw", "RGBA")

        if texture_name not in self.textures:
            self.textures.append(texture_name)
            self._images.append(raw)

    # helper for VulkanRenderer to retrieve raw image bytes
    def get_raw_images(self):
        return list(self._images)
