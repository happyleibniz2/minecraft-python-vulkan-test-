from OpenGL import GL as gl


class OpenGLRenderer:
	"""Renderer backend that consumes prepared world render data."""

	def __init__(self, options):
		self.options = options

	def _draw_translucent(self, chunks):
		if self.options.FANCY_TRANSLUCENCY:
			gl.glDepthMask(gl.GL_FALSE)
			gl.glFrontFace(gl.GL_CW)
			gl.glEnable(gl.GL_BLEND)

			for render_chunk in chunks:
				render_chunk.draw_translucent(gl.GL_TRIANGLES)

			gl.glFrontFace(gl.GL_CCW)
			for render_chunk in chunks:
				render_chunk.draw_translucent(gl.GL_TRIANGLES)

			gl.glDisable(gl.GL_BLEND)
			gl.glDepthMask(gl.GL_TRUE)
		else:
			gl.glEnable(gl.GL_BLEND)
			gl.glDisable(gl.GL_CULL_FACE)
			gl.glDepthMask(gl.GL_FALSE)

			for render_chunk in chunks:
				render_chunk.draw_translucent(gl.GL_TRIANGLES)

			gl.glDepthMask(gl.GL_TRUE)
			gl.glDisable(gl.GL_BLEND)

	def draw(self, shader, world, render_data, clear_callback, debug_wireframe=False):
		gl.glClearColor(*render_data["clear_color"])
		gl.glUniform1f(world.shader_daylight_location, render_data["daylight_multiplier"])

		clear_callback()

		if debug_wireframe:
			gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_LINE)

		for render_chunk in render_data["opaque_chunks"]:
			render_chunk.draw(gl.GL_TRIANGLES)

		self._draw_translucent(render_data["translucent_chunks"])

		if debug_wireframe:
			gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)
