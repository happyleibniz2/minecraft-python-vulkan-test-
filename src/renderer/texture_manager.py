import pyglet
import logging
import ctypes

from OpenGL import GL as gl

import src.options as options


class TextureManager:
	def __init__(self, texture_width, texture_height, max_textures):
		self.texture_width = texture_width
		self.texture_height = texture_height

		self.max_textures = max_textures

		self.textures = []

		self.texture_array = gl.GLuint(0)
		gl.glGenTextures(1, self.texture_array)
		gl.glBindTexture(gl.GL_TEXTURE_2D_ARRAY, self.texture_array)

		gl.glTexParameteri(gl.GL_TEXTURE_2D_ARRAY, gl.GL_TEXTURE_MIN_FILTER, options.MIPMAP_TYPE)
		gl.glTexParameteri(gl.GL_TEXTURE_2D_ARRAY, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)

		gl.glTexImage3D(
			gl.GL_TEXTURE_2D_ARRAY,
			0,
			gl.GL_RGBA,
			self.texture_width,
			self.texture_height,
			self.max_textures,
			0,
			gl.GL_RGBA,
			gl.GL_UNSIGNED_BYTE,
			None,
		)

		# Initialize all layers with a solid opaque magenta placeholder so
		# missing textures won't sample fully transparent and cause geometry
		# to be discarded by the fragment shader.
		placeholder = (ctypes.c_ubyte * (self.texture_width * self.texture_height * 4))()
		for i in range(0, self.texture_width * self.texture_height * 4, 4):
			placeholder[i] = 255  # R
			placeholder[i + 1] = 0  # G
			placeholder[i + 2] = 255  # B
			placeholder[i + 3] = 255  # A

		for layer in range(self.max_textures):
			gl.glTexSubImage3D(
				gl.GL_TEXTURE_2D_ARRAY,
				0,
				0,
				0,
				layer,
				self.texture_width,
				self.texture_height,
				1,
				gl.GL_RGBA,
				gl.GL_UNSIGNED_BYTE,
				placeholder,
			)

	def generate_mipmaps(self):
		logging.debug(f"Generating Mipmaps, using mipmap type {options.MIPMAP_TYPE}")
		gl.glGenerateMipmap(gl.GL_TEXTURE_2D_ARRAY)

	def add_texture(self, texture):
		logging.debug(f"Loading texture textures/{texture}.png")

		if texture not in self.textures:
			self.textures.append(texture)

			texture_image = pyglet.image.load(f"textures/{texture}.png").get_image_data()
			gl.glBindTexture(gl.GL_TEXTURE_2D_ARRAY, self.texture_array)

			gl.glTexSubImage3D(
				gl.GL_TEXTURE_2D_ARRAY,
				0,
				0,
				0,
				self.textures.index(texture),
				self.texture_width,
				self.texture_height,
				1,
				gl.GL_RGBA,
				gl.GL_UNSIGNED_BYTE,
				texture_image.get_data("RGBA", texture_image.width * 4),
			)
