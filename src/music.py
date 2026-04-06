"""Minimal audio stub to remove the pyglet.media dependency.

This keeps the same minimal interface used by `main.py` but does not
actually play audio. Replace with a real audio backend if desired.
"""

class MusicPlayer:
	def __init__(self):
		self.standby = False
		self.next_time = 0
		self.volume = 1.0
		self.source = None

	def queue(self, src):
		self.source = src

	def play(self):
		# stub: mark as playing by setting source
		pass

	def delete(self):
		self.source = None

