"""End-to-end: fake camera + fake vision drive the real engine, pipeline and backend."""

import dataclasses
import time

import numpy as np

from gesture_racer.config import Config
from gesture_racer.controller import Hotkeys, KeyboardBackend, _resolve_key
from gesture_racer.engine import Engine
from gesture_racer.models import PAUSED, RUN, Pt, VisionFrame

CFG = dataclasses.replace(Config(), calibration_seconds=0.4, start_delay=0.2,
                          calib_min_samples=5, watchdog_seconds=0.5)


class FakeStream:
    dead = False

    def __init__(self):
        self._frame = np.zeros((480, 640, 3), np.uint8)

    def read(self, last_seq, timeout=0.5):
        time.sleep(1 / 60)
        return self._frame, last_seq + 1, time.monotonic()


class FakeVision:
    """Scripted pose: `lean` shifts nose and shoulders right (in image fractions)."""
    lean = 0.0
    visible = True

    def __init__(self, cfg):
        pass

    def process(self, rgb, run_hands):
        pose = None
        if FakeVision.visible:
            pose = [Pt(0, 0, 0, 0.0)] * 33
            pose = list(pose)
            dx = FakeVision.lean
            pose[0] = Pt(0.5 + dx, 0.3, 0, 1.0)
            pose[11] = Pt(0.4 + dx, 0.6, 0, 1.0)
            pose[12] = Pt(0.6 + dx, 0.6, 0, 1.0)
        return VisionFrame(pose, [], run_hands, 5.0, 2.0)

    def close(self):
        pass


class FakeCtl:
    def __init__(self):
        self.down = set()

    def press(self, k):
        self.down.add(k)

    def release(self, k):
        self.down.discard(k)


def wait_for(cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def build():
    FakeVision.lean, FakeVision.visible = 0.0, True
    ctl = FakeCtl()
    backend = KeyboardBackend(CFG, ctl)
    hotkeys = Hotkeys(listen=False)
    engine = Engine(CFG, {}, FakeStream(), backend, hotkeys, vision_factory=FakeVision)
    engine.start()
    return engine, backend, hotkeys, ctl


def test_calibrates_runs_steers_and_cleans_up():
    engine, backend, hotkeys, ctl = build()
    try:
        assert wait_for(lambda: engine.snapshot().state == RUN), engine.snapshot().state
        assert wait_for(lambda: _resolve_key("up") in ctl.down)          # auto gas

        FakeVision.lean = 0.08                                           # ~0.1 shoulder widths... lean right
        assert wait_for(lambda: engine.snapshot().cmd.steer > 0.5)
        assert wait_for(lambda: _resolve_key("right") in ctl.down or
                        engine.snapshot().cmd.steer > 0.5)

        FakeVision.lean = -0.2                                           # hard left
        assert wait_for(lambda: engine.snapshot().cmd.steer < -0.9)
        assert engine.snapshot().latency_ms >= 0
    finally:
        engine.stop()
        backend.close()
    assert not ctl.down                                                   # nothing left pressed


def test_pause_releases_everything_and_resume_restarts_cleanly():
    engine, backend, hotkeys, ctl = build()
    try:
        assert wait_for(lambda: engine.snapshot().state == RUN)
        FakeVision.lean = 0.2
        assert wait_for(lambda: engine.snapshot().cmd.steer > 0.9)
        hotkeys.press("toggle")
        assert wait_for(lambda: engine.snapshot().state == PAUSED)
        assert wait_for(lambda: not ctl.down)
        FakeVision.lean = 0.0
        hotkeys.press("toggle")
        assert wait_for(lambda: engine.snapshot().state == RUN)
        assert engine.snapshot().cmd.steer < 0.5                          # no stale steering
    finally:
        engine.stop()
        backend.close()


def test_tracking_loss_releases_controls():
    engine, backend, hotkeys, ctl = build()
    try:
        assert wait_for(lambda: engine.snapshot().state == RUN)
        assert wait_for(lambda: _resolve_key("up") in ctl.down)
        FakeVision.visible = False
        assert wait_for(lambda: not engine.snapshot().tracking_ok, 2.0)
        assert wait_for(lambda: not ctl.down, 2.0)
    finally:
        engine.stop()
        backend.close()


def test_sensitivity_hotkeys_and_quit():
    engine, backend, hotkeys, ctl = build()
    try:
        assert wait_for(lambda: engine.snapshot().state == RUN)
        before = engine.sensitivity
        hotkeys.press("sensitivity_up")
        assert wait_for(lambda: engine.sensitivity > before)
        assert "Sensitivity" in (wait_for(lambda: engine.snapshot().toast != "") and engine.snapshot().toast)
        hotkeys.press("quit")
        assert wait_for(lambda: not engine.running)
    finally:
        engine.stop()
        backend.close()
    assert engine.error is None
