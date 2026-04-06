import platform
import ctypes
import logging
import random
import time
import os
from collections import deque

import sys
try:
	import glfw
	GLFW_IMPORT_ERROR = None
except Exception as exc:
	glfw = None
	GLFW_IMPORT_ERROR = exc

STARTUP_IMPORT_ERROR = None
try:
	import pyglet.gl as gl
	from src.renderer.vulkan_renderer import VulkanRenderer
	from src.renderer.vulkan_shader import VulkanShader
	from src.renderer.vulkan_texture import VulkanTextureManager

	from src.music import MusicPlayer

	from src.renderer.shader import Shader
	from src.renderer.texture_manager import TextureManager
	from src.world import World
	from src.entity.player import Player
	from src.controllers.joystick import JoystickController
	from src.controllers.keyboard_mouse import KeyboardMouseController

	import src.options as options
except Exception as exc:
	STARTUP_IMPORT_ERROR = exc


class InternalConfig:
	def __init__(self, options):
		self.RENDER_DISTANCE = options.RENDER_DISTANCE
		self.FOV = options.FOV
		self.INDIRECT_RENDERING = options.INDIRECT_RENDERING
		self.ADVANCED_OPENGL = options.ADVANCED_OPENGL
		self.CHUNK_UPDATES = options.CHUNK_UPDATES
		self.VSYNC = options.VSYNC
		self.MAX_CPU_AHEAD_FRAMES = options.MAX_CPU_AHEAD_FRAMES
		self.SMOOTH_FPS = options.SMOOTH_FPS
		self.SMOOTH_LIGHTING = options.SMOOTH_LIGHTING
		self.FANCY_TRANSLUCENCY = options.FANCY_TRANSLUCENCY
		self.MIPMAP_TYPE = options.MIPMAP_TYPE
		self.COLORED_LIGHTING = options.COLORED_LIGHTING
		self.ANTIALIASING = options.ANTIALIASING


class Window:
	"""Window wrapper that uses GLFW for windowing and PyOpenGL for GL calls.

	This keeps the existing renderer code (which talks to `pyglet.gl`) working
	while moving windowing and input to GLFW. Full Vulkan migration is a
	separate follow-up task — this scaffolds that work.
	"""

	def __init__(self, width=852, height=480, title="Minecraft clone", vsync=True):
		self.width = width
		self.height = height
		self.title = title
		self.mouse_captured = False

		# Options
		self.options = InternalConfig(options)

		# Initialize GLFW
		if not glfw.init():
			raise RuntimeError("Failed to initialize GLFW")

		# Determine whether to try Vulkan: user can request with --vulkan or env PMCM_USE_VULKAN=1
		use_vulkan = (os.environ.get("PMCM_USE_VULKAN") == "1") or ("--vulkan" in sys.argv)

		self.vulkan = None
		has_vulkan = False

		if use_vulkan:
			# Try to create a Vulkan (NO_API) window and initialize VulkanRenderer
			glfw.window_hint(glfw.CLIENT_API, glfw.NO_API)
			self._glfw_window = glfw.create_window(self.width, self.height, self.title, None, None)
			if self._glfw_window:
				try:
					self.vulkan = VulkanRenderer(self._glfw_window, self.width, self.height)
					has_vulkan = True
				except Exception as e:
					logging.warning(f"Vulkan initialization failed, falling back to OpenGL: {e}")
					# destroy the window and fall back
					try:
						glfw.destroy_window(self._glfw_window)
					except Exception:
						pass

		# If Vulkan not used (or failed), create an OpenGL context window
		if not has_vulkan:
			# Request an OpenGL 3.3 core profile context
			glfw.window_hint(glfw.CLIENT_API, glfw.OPENGL_API)
			glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
			glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
			glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)

			self._glfw_window = glfw.create_window(self.width, self.height, self.title, None, None)
			if not self._glfw_window:
				glfw.terminate()
				raise RuntimeError("Failed to create GLFW window")

			glfw.make_context_current(self._glfw_window)
			glfw.swap_interval(1 if vsync else 0)

		# If we reached here and have Vulkan, initialize Vulkan-side placeholders
		if has_vulkan:
			logging.info("Running with Vulkan renderer (scaffold)")

			# create minimal shader/texture manager compatible with World and Player
			self.shader = VulkanShader("shaders/alpha_lighting/vert.glsl", "shaders/alpha_lighting/frag.glsl")
			self.texture_manager = VulkanTextureManager(16, 16, 256)

			# create world and player structures (no GL calls)
			logging.info("Creating World (Vulkan path)")
			self.world = World(self.shader, None, self.texture_manager, self.options)
			logging.info("Setting up player & camera (Vulkan path)")
			self.player = Player(self.world, self.shader, self.width, self.height)
			self.world.player = self.player
			spawn_position = self.world.find_spawn_position(0, 0)
			self.player.teleport(spawn_position)

			# schedule-like behaviour
			self._scheduled = []

			# Vulkan renderer may want access to textures raw bytes for GPU upload
			if getattr(self, "vulkan", None):
				raw_images = self.texture_manager.get_raw_images()
				try:
					# try the real upload if implemented
					if hasattr(self.vulkan, "upload_textures_real"):
						self.vulkan.upload_textures_real(raw_images, self.texture_manager.texture_width, self.texture_manager.texture_height)
					else:
						self.vulkan.upload_textures(raw_images, self.texture_manager.texture_width, self.texture_manager.texture_height)
				except Exception:
					pass

			logging.info(
				"Vulkan init summary: chunks=%d player_pos=%s",
				len(self.world.chunks),
				tuple(round(v, 2) for v in self.player.position),
			)

			# skip GL-specific initialization below
			return

		# F3 debug placeholder
		self.show_f3 = False
		self.f3 = type("F3", (), {"text": "", "draw": lambda self=None: None})()

		self.system_info = f"""Python: {platform.python_implementation()} {platform.python_version()}
System: {platform.machine()} {platform.system()} {platform.release()} {platform.version()}
CPU: {platform.processor()}
Display: {gl.gl_info.get_renderer()} 
{gl.gl_info.get_version()}"""

		logging.info(f"System Info: {self.system_info}")

		# create shader
		logging.info("Compiling Shaders")
		if not self.options.COLORED_LIGHTING:
			self.shader = Shader("shaders/alpha_lighting/vert.glsl", "shaders/alpha_lighting/frag.glsl")
		else:
			self.shader = Shader("shaders/colored_lighting/vert.glsl", "shaders/colored_lighting/frag.glsl")
		self.shader_sampler_location = self.shader.find_uniform(b"u_TextureArraySampler")
		self.shader.use()

		# create textures
		logging.info("Creating Texture Array")
		self.texture_manager = TextureManager(16, 16, 256)

		# create world
		self.world = World(self.shader, None, self.texture_manager, self.options)
		logging.info("World initialized: chunks=%d", len(self.world.chunks))

		# player stuff
		logging.info("Setting up player & camera")
		self.player = Player(self.world, self.shader, self.width, self.height)
		self.world.player = self.player
		spawn_position = self.world.find_spawn_position(0, 0)
		self.player.teleport(spawn_position)
		logging.info("Player initialized at %s", tuple(round(v, 2) for v in self.player.position))

		# schedule-like behaviour: we'll call these in the main loop
		self._scheduled = []

		# misc
		self.holding = 50

		# bind textures
		gl.glActiveTexture(gl.GL_TEXTURE0)
		gl.glBindTexture(gl.GL_TEXTURE_2D_ARRAY, self.world.texture_manager.texture_array)
		gl.glUniform1i(self.shader_sampler_location, 0)

		# enable common GL features
		gl.glEnable(gl.GL_DEPTH_TEST)
		gl.glEnable(gl.GL_CULL_FACE)
		gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

		if self.options.ANTIALIASING:
			gl.glEnable(gl.GL_MULTISAMPLE)
			gl.glEnable(gl.GL_SAMPLE_ALPHA_TO_COVERAGE)
			gl.glSampleCoverage(0.5, gl.GL_TRUE)

		# controls
		self.controls = [0, 0, 0]

		# joystick + keyboard controllers
		self.joystick_controller = JoystickController(self)
		self.keyboard_mouse = KeyboardMouseController(self)

		# music (stubbed)
		logging.info("Loading audio")
		try:
			self.music = [
				os.path.join("audio/music", file)
				for file in os.listdir("audio/music")
				if os.path.isfile(os.path.join("audio/music", file))
			]
		except FileNotFoundError:
			self.music = []

		self.media_player = MusicPlayer()
		self.media_player.volume = 0.5

		if len(self.music) > 0:
			self.media_player.queue(random.choice(self.music))
			self.media_player.play()
		else:
			self.media_player.standby = True

		# GPU syncs
		self.fences = deque()

		# input bookkeeping
		self._last_cursor = None

		# install GLFW callbacks
		glfw.set_key_callback(self._glfw_window, self._on_key)
		glfw.set_mouse_button_callback(self._glfw_window, self._on_mouse_button)
		glfw.set_cursor_pos_callback(self._glfw_window, self._on_cursor_pos)
		glfw.set_window_size_callback(self._glfw_window, self._on_resize)
		glfw.set_window_close_callback(self._glfw_window, self._on_close)

	# Compatibility helpers used by controllers
	def set_exclusive_mouse(self, value: bool):
		if value:
			glfw.set_input_mode(self._glfw_window, glfw.CURSOR, glfw.CURSOR_DISABLED)
			self.mouse_captured = True
		else:
			glfw.set_input_mode(self._glfw_window, glfw.CURSOR, glfw.CURSOR_NORMAL)
			self.mouse_captured = False

	def toggle_fullscreen(self):
		# simple toggle: not preserving previous monitor/state
		if glfw.get_window_monitor(self._glfw_window):
			glfw.set_window_monitor(self._glfw_window, None, 100, 100, self.width, self.height, 0)
		else:
			monitor = glfw.get_primary_monitor()
			mode = glfw.get_video_mode(monitor)
			glfw.set_window_monitor(self._glfw_window, monitor, 0, 0, mode.size.width, mode.size.height, mode.refresh_rate)

	def clear(self):
		# No-op for Vulkan path; GL path would clear here
		if not getattr(self, "vulkan", None):
			gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

	# Internal GLFW callbacks that forward to the same-named handlers set by controllers
	def _on_key(self, win, key, scancode, action, mods):
		if action == glfw.PRESS:
			if hasattr(self, "on_key_press"):
				self.on_key_press(key, mods)
		elif action == glfw.RELEASE:
			if hasattr(self, "on_key_release"):
				self.on_key_release(key, mods)

	def _on_mouse_button(self, win, button, action, mods):
		x, y = glfw.get_cursor_pos(win)
		if action == glfw.PRESS:
			if hasattr(self, "on_mouse_press"):
				self.on_mouse_press(int(x), int(y), button, mods)
		elif action == glfw.RELEASE:
			if hasattr(self, "on_mouse_release"):
				self.on_mouse_release(int(x), int(y), button, mods)

	def _on_cursor_pos(self, win, x, y):
		if self._last_cursor is None:
			self._last_cursor = (x, y)
			return

		dx = x - self._last_cursor[0]
		dy = y - self._last_cursor[1]
		self._last_cursor = (x, y)

		if hasattr(self, "on_mouse_motion"):
			self.on_mouse_motion(int(x), int(y), dx, dy)

	def _on_resize(self, win, width, height):
		self.width = width
		self.height = height
		if hasattr(self, "on_resize"):
			self.on_resize(width, height)

	def _on_close(self, win):
		if hasattr(self, "on_close"):
			self.on_close()

	def update_f3(self, delta_time):
		"""Safe F3 updater for debug text."""
		if not hasattr(self, "f3"):
			return

		try:
			self.f3.text = (
				f"dt={delta_time:.4f} "
				f"pos={tuple(round(v, 2) for v in self.player.position)} "
				f"chunks={len(self.world.chunks)} visible={len(self.world.visible_chunks)}"
			)
		except Exception:
			pass

	# Scheduler helpers
	def schedule(self, func):
		self._scheduled.append({"func": func, "interval": 0.0, "elapsed": 0.0})

	def schedule_interval(self, func, interval):
		self._scheduled.append({"func": func, "interval": float(interval), "elapsed": 0.0})

	# Main per-tick update/draw kept similar to original
	def update(self, delta_time):
		if self.show_f3:
			self.update_f3(delta_time)

		if not self.media_player.source and len(self.music) > 0:
			if not self.media_player.standby:
				self.media_player.standby = True
				self.media_player.next_time = round(time.time()) + random.randint(240, 360)
			elif time.time() >= self.media_player.next_time:
				self.media_player.standby = False
				self.media_player.queue(random.choice(self.music))
				self.media_player.play()

		if not self.mouse_captured:
			self.player.input = [0, 0, 0]

		self.joystick_controller.update_controller()
		self.player.update(delta_time)

		self.world.tick(delta_time)

		if self.world.time % 120 == 0:
			logging.info(
				"Tick diagnostics: time=%d chunks=%d visible=%d pending_updates=%d built_queue=%d player=%s",
				self.world.time,
				len(self.world.chunks),
				len(self.world.visible_chunks),
				self.world.pending_chunk_update_count,
				len(self.world.chunk_building_queue),
				tuple(round(v, 2) for v in self.player.position),
			)

	def on_draw(self):
		# If Vulkan renderer is available, delegate drawing to it.
		if getattr(self, "vulkan", None):
			self.vulkan.draw()
			return

		# Fallback to OpenGL path
		gl.glEnable(gl.GL_DEPTH_TEST)
		self.shader.use()
		self.player.update_matrices()

		while len(self.fences) > self.options.MAX_CPU_AHEAD_FRAMES:
			fence = self.fences.popleft()
			try:
				gl.glClientWaitSync(fence, gl.GL_SYNC_FLUSH_COMMANDS_BIT, 2147483647)
				gl.glDeleteSync(fence)
			except Exception:
				break

		self.clear()
		self.world.prepare_rendering()
		self.world.draw()

		if self.show_f3:
			self.f3.draw()

		if not self.options.SMOOTH_FPS:
			pass
		else:
			gl.glFinish()


class Game:
	def __init__(self):
		self.window = Window(width=852, height=480, title="Minecraft clone", vsync=options.VSYNC)

		# schedule player interpolation and main update (only if player exists)
		if getattr(self.window, "player", None):
			self.window.schedule(self.window.player.update_interpolation)
		self.window.schedule_interval(self.window.update, 1 / 60)

	def run(self):
		last = time.time()
		while not glfw.window_should_close(self.window._glfw_window):
			now = time.time()
			delta = now - last
			last = now

			# call scheduled functions
			for scheduled in list(self.window._scheduled):
				func = scheduled["func"]
				interval = scheduled["interval"]
				try:
					if interval == 0:
						func(delta)
					else:
						scheduled["elapsed"] += delta
						if scheduled["elapsed"] < interval:
							continue
						scheduled["elapsed"] -= interval
						func(interval)
				except TypeError:
					try:
						func()
					except Exception:
						logging.exception("Scheduled function %s failed (no-arg fallback)", getattr(func, "__name__", repr(func)))
				except Exception:
					logging.exception("Scheduled function %s failed", getattr(func, "__name__", repr(func)))

			# per-frame draw
			try:
				self.window.on_draw()
			except Exception:
				logging.exception("Draw call failed")
				raise

			# With Vulkan (NO_API) we should not call swap_buffers; the renderer presents.
			if getattr(self.window, "vulkan", None) is None:
				glfw.swap_buffers(self.window._glfw_window)
			glfw.poll_events()

		# cleanup
		glfw.terminate()


def init_logger():
	log_folder = "logs"
	log_filename = f"{time.time()}.log"
	log_path = os.path.join(log_folder, log_filename)

	if not os.path.isdir(log_folder):
		os.mkdir(log_folder)

	with open(log_path, "x") as file:
		file.write("[LOGS]\n")

	class _SyncedConsole:
		def __init__(self, original_stream, mirror_path):
			self.original_stream = original_stream
			self.mirror_path = mirror_path

		def write(self, message):
			self.original_stream.write(message)
			self.original_stream.flush()
			with open(self.mirror_path, "a", encoding="utf-8", errors="replace") as mirror:
				mirror.write(message)

		def flush(self):
			self.original_stream.flush()

	logging.basicConfig(
		level=logging.INFO,
		format="[%(asctime)s] [%(processName)s/%(threadName)s/%(levelname)s] (%(module)s.py/%(funcName)s) %(message)s",
		handlers=[logging.FileHandler(log_path), logging.StreamHandler(sys.__stdout__)],
		force=True,
	)

	# Sync raw console output (prints/tracebacks) into logs/<timestamp>.log too.
	sys.stdout = _SyncedConsole(sys.__stdout__, log_path)
	sys.stderr = _SyncedConsole(sys.__stderr__, log_path)

	def _log_uncaught(exc_type, exc_value, exc_traceback):
		if issubclass(exc_type, KeyboardInterrupt):
			sys.__excepthook__(exc_type, exc_value, exc_traceback)
			return
		logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

	sys.excepthook = _log_uncaught
	logging.info("Logger initialized at %s", log_path)


def main():
	init_logger()

	if STARTUP_IMPORT_ERROR is not None:
		logging.critical("Startup imports failed: %s", STARTUP_IMPORT_ERROR)
		logging.critical("Common fix: install runtime dependencies from pyproject/poetry (e.g. glfw, PyOpenGL).")
		return

	if glfw is None:
		logging.critical("GLFW import failed during startup: %s", GLFW_IMPORT_ERROR)
		logging.critical("Install glfw with: pip install glfw")
		return

	game = Game()
	game.run()


if __name__ == "__main__":
	main()
