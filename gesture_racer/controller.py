"""Keyboard output and global hotkeys (the only module that touches pynput)."""

from __future__ import annotations

import sys
import threading
import time
import ctypes

from pynput import keyboard as pk

from .config import Config


def _resolve_key(name: str):
    return getattr(pk.Key, name) if len(name) > 1 else name


# Windows sleeps in ~15 ms steps by default, which would wreck the steering PWM.
def _timer_resolution(begin: bool) -> None:
    if sys.platform != "win32":
        return
    try:
        winmm = ctypes.windll.winmm
        (winmm.timeBeginPeriod if begin else winmm.timeEndPeriod)(1)
    except Exception:
        pass


class KeyboardBackend:
    """
    Turns control values into key presses on a dedicated thread (~250 Hz).
    Keys are released automatically if the engine stalls or this thread fails.

    A gamepad backend can implement the same interface:
        set(steer, gas, brake, nitro), release_all(), close(), .error
    """

    def __init__(self, cfg: Config, controller=None):
        self.cfg = cfg
        self.kb = controller or pk.Controller()
        self.k_left, self.k_right = _resolve_key(cfg.key_left), _resolve_key(cfg.key_right)
        self.k_gas, self.k_brake = _resolve_key(cfg.key_gas), _resolve_key(cfg.key_brake)
        self.k_nitro = _resolve_key(cfg.key_nitro)
        self._cmd = (0.0, False, False, False)   # one tuple => atomic hand-off between threads
        self._stamp = time.monotonic()
        self._held: set = set()
        self._held_lock = threading.RLock()
        self._run = True
        self.error = None
        _timer_resolution(True)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def set(self, steer: float, gas: bool, brake: bool, nitro: bool) -> None:
        self._cmd = (steer, gas, brake, nitro)
        self._stamp = time.monotonic()

    def _set_key(self, key, down: bool) -> None:
        with self._held_lock:
            if down and key not in self._held:
                self.kb.press(key)
                self._held.add(key)
            elif not down and key in self._held:
                self.kb.release(key)
                self._held.discard(key)

    def _loop(self) -> None:
        cfg = self.cfg
        try:
            while self._run:
                now = time.monotonic()
                if now - self._stamp > cfg.watchdog_seconds:
                    steer, gas, brake, nitro = 0.0, False, False, False
                else:
                    steer, gas, brake, nitro = self._cmd
                a = abs(steer)
                on = a >= 0.97 or ((now % cfg.pwm_period) / cfg.pwm_period) < a
                self._set_key(self.k_left, on and steer < 0)
                self._set_key(self.k_right, on and steer > 0)
                self._set_key(self.k_gas, gas and not brake)
                self._set_key(self.k_brake, brake)
                self._set_key(self.k_nitro, nitro)
                time.sleep(cfg.backend_sleep)
        except Exception as exc:     # never leave a key stuck down
            self.error = exc
        finally:
            self.release_all()

    def release_all(self) -> None:
        with self._held_lock:
            for key in list(self._held):
                try:
                    self.kb.release(key)
                except Exception:
                    pass
            self._held.clear()

    def close(self) -> None:
        self._run = False
        self._thread.join(timeout=1.0)
        self.release_all()
        _timer_resolution(False)


HOTKEY_ACTIONS = {pk.Key.f5: "sensitivity_down", pk.Key.f6: "sensitivity_up",
                  pk.Key.f7: "auto_gas", pk.Key.f8: "toggle",
                  pk.Key.f9: "recalib", pk.Key.f10: "quit"}
ACTION_NAMES = tuple(HOTKEY_ACTIONS.values())


class Hotkeys:
    """Global hotkeys that work while the game is focused. The preview window's
    own keys feed the same flags through press(), so there is one code path."""

    def __init__(self, listen: bool = True):
        self.flags = {name: False for name in ACTION_NAMES}
        self._lock = threading.Lock()
        self.listener = None
        if listen:
            self.listener = pk.Listener(on_press=self._on_press)
            self.listener.start()

    def _on_press(self, key) -> None:
        action = HOTKEY_ACTIONS.get(key)
        if action:
            self.press(action)

    def press(self, action: str) -> None:
        with self._lock:
            self.flags[action] = True

    def pop(self, name: str) -> bool:
        with self._lock:
            value = self.flags[name]
            self.flags[name] = False
            return value

    def stop(self) -> None:
        if self.listener:
            self.listener.stop()
