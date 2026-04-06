class VulkanShader:
    def __init__(self, vert_path=None, frag_path=None):
        # placeholder: store paths for future pipeline creation
        self.vert_path = vert_path
        self.frag_path = frag_path

    def find_uniform(self, name):
        return 0

    def uniform_matrix(self, location, matrix):
        pass

    def use(self):
        pass

    def stop(self):
        pass

    def __del__(self):
        pass
