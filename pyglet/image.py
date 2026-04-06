from PIL import Image


class _ImageData:
    def __init__(self, pil_image):
        self.width = pil_image.width
        self.height = pil_image.height
        self._data = pil_image.tobytes("raw", "RGBA")

    def get_data(self, fmt, pitch):
        # The code expects raw bytes in RGBA order
        return self._data


class _Loader:
    def __init__(self, pil_image):
        self._img = _ImageData(pil_image)

    def get_image_data(self):
        return self._img


def load(path):
    img = Image.open(path).convert("RGBA")
    return _Loader(img)
