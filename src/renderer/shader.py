import ctypes
import pyglet.gl as gl

import glm


class ShaderError(Exception): ...


def create_shader(target, source_path):
	# read shader source
	with open(source_path, "r", encoding="utf-8") as source_file:
		source = source_file.read()

	# Use PyOpenGL helper which accepts Python strings
	try:
		gl.glShaderSource(target, source)
		gl.glCompileShader(target)
	except Exception as e:
		raise ShaderError(f"Shader compile failure: {e}")

	# check compile status and retrieve info log if any
	try:
		status = gl.glGetShaderiv(target, gl.GL_COMPILE_STATUS)
	except Exception:
		status = None

	info_log = ""
	try:
		info_log = gl.glGetShaderInfoLog(target)
		if isinstance(info_log, bytes):
			info_log = info_log.decode(errors="ignore")
	except Exception:
		info_log = ""

	if status is None or (isinstance(status, int) and status == 0):
		raise ShaderError(info_log or "Unknown shader compile error")


class Shader:
	def __init__(self, vert_path, frag_path):
		self.program = gl.glCreateProgram()

		# create vertex shader

		self.vert_shader = gl.glCreateShader(gl.GL_VERTEX_SHADER)
		create_shader(self.vert_shader, vert_path)
		gl.glAttachShader(self.program, self.vert_shader)

		# create fragment shader

		self.frag_shader = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
		create_shader(self.frag_shader, frag_path)
		gl.glAttachShader(self.program, self.frag_shader)

		# link program and clean up

		gl.glLinkProgram(self.program)

		gl.glDeleteShader(self.vert_shader)
		gl.glDeleteShader(self.frag_shader)

	def __del__(self):
		if hasattr(self, "program") and self.program:
			try:
				gl.glDeleteProgram(self.program)
			except Exception:
				pass

	def find_uniform(self, name):
		return gl.glGetUniformLocation(self.program, ctypes.create_string_buffer(name))

	def uniform_matrix(self, location, matrix):
		gl.glUniformMatrix4fv(location, 1, gl.GL_FALSE, glm.value_ptr(matrix))

	def use(self):
		gl.glUseProgram(self.program)

	def stop(self):
		gl.glUseProgram(0)
