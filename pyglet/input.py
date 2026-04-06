"""Minimal `pyglet.input` shim using GLFW joystick APIs.

Exports `get_joysticks()` which returns a list of `Joystick` objects.
Each `Joystick` has a `.device.name`, `.open(exclusive=True)`, and
callback attributes: `on_joybutton_press`, `on_joybutton_release`,
`on_joyaxis_motion(joystick, axis_name, value)`.

This module polls joystick state in a background thread and emits callbacks
to emulate pyglet.input behaviour sufficiently for the project.
"""

import glfw
import threading
import time

_POLL_INTERVAL = 1 / 60.0


class Device:
    def __init__(self, name):
        self.name = name or "Unknown"


class Joystick:
    def __init__(self, jid):
        self.id = jid
        self.device = Device(glfw.get_joystick_name(jid))
        self.on_joybutton_press = None
        self.on_joybutton_release = None
        self.on_joyaxis_motion = None
        self._opened = False

    def open(self, exclusive=False):
        self._opened = True

    def close(self):
        self._opened = False


_joysticks = {}
_callbacks_thread = None
_stop = False


def _axis_name_for_index(i):
    # Common mapping for typical dual-stick controllers
    mapping = {0: "x", 1: "y", 2: "z", 3: "rx", 4: "ry", 5: "rz"}
    return mapping.get(i, str(i))


def _poll_loop():
    prev_axes = {}
    prev_buttons = {}
    global _stop
    while not _stop:
        for jid in range(glfw.JOYSTICK_1, glfw.JOYSTICK_LAST + 1):
            if not glfw.joystick_present(jid):
                if jid in _joysticks:
                    del _joysticks[jid]
                continue

            # ensure joystick object exists
            if jid not in _joysticks:
                _joysticks[jid] = Joystick(jid)

            js = _joysticks[jid]

            axes = glfw.get_joystick_axes(jid) or []
            buttons = glfw.get_joystick_buttons(jid) or []

            # axes
            prev_a = prev_axes.get(jid, [0.0] * len(axes))
            for i, v in enumerate(axes):
                pv = prev_a[i] if i < len(prev_a) else 0.0
                if abs(v - pv) > 0.01:
                    name = _axis_name_for_index(i)
                    if js.on_joyaxis_motion:
                        try:
                            js.on_joyaxis_motion(js, name, v)
                        except Exception:
                            pass

            prev_axes[jid] = list(axes)

            # buttons
            prev_b = prev_buttons.get(jid, [0] * len(buttons))
            for i, b in enumerate(buttons):
                pb = prev_b[i] if i < len(prev_b) else 0
                if b and not pb:
                    if js.on_joybutton_press:
                        try:
                            js.on_joybutton_press(js, i)
                        except Exception:
                            pass
                elif not b and pb:
                    if js.on_joybutton_release:
                        try:
                            js.on_joybutton_release(js, i)
                        except Exception:
                            pass

            prev_buttons[jid] = list(buttons)

        time.sleep(_POLL_INTERVAL)


def _ensure_thread():
    global _callbacks_thread
    if _callbacks_thread and _callbacks_thread.is_alive():
        return
    _callbacks_thread = threading.Thread(target=_poll_loop, daemon=True, name="pyglet_input_poller")
    _callbacks_thread.start()


def get_joysticks():
    """Return a list of Joystick objects for all present joysticks.

    The objects remain live and will receive callbacks when the poller
    detects button/axis changes.
    """
    _ensure_thread()
    # Build list from current _joysticks and present ones
    js_list = []
    for jid in range(glfw.JOYSTICK_1, glfw.JOYSTICK_LAST + 1):
        if glfw.joystick_present(jid):
            if jid not in _joysticks:
                _joysticks[jid] = Joystick(jid)
            js_list.append(_joysticks[jid])
    return js_list


def shutdown():
    global _stop
    _stop = True
