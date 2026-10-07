"""Pure gesture logic: landmarks in, driving commands out.

Nothing here touches the camera, the keyboard or OpenCV, so it is fully unit-testable.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from .config import Config
from .models import Command, Hand, Pt


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


class Ema:
    """Time-based exponential moving average (same feel at any frame rate)."""

    def __init__(self, tau: float):
        self.tau = tau
        self.v: Optional[float] = None

    def update(self, x: float, dt: float) -> float:
        if self.v is None:
            self.v = x
        else:
            self.v += (1.0 - math.exp(-max(dt, 1e-6) / self.tau)) * (x - self.v)
        return self.v

    def reset(self) -> None:
        self.v = None


def steer_from_lean(lean: float, sensitivity: float, cfg: Config) -> float:
    """Lean -> steering in -1..+1. Small leans are boosted by a power curve."""
    a = abs(lean)
    if a <= cfg.dead_zone:
        return 0.0
    v = min(1.0, (a - cfg.dead_zone) / (cfg.max_lean - cfg.dead_zone))
    return math.copysign(min(1.0, (v ** cfg.steer_curve) * sensitivity), lean)


def pose_features(pose: Optional[list], w: int, h: int, cfg: Config) -> Optional[dict]:
    """Reduce 33 pose landmarks to the three numbers the controls need."""
    if not pose:
        return None
    nose, ls, rs = pose[0], pose[11], pose[12]
    if min(nose.v, ls.v, rs.v) < 0.5:
        return None
    lx, ly, rx, ry = ls.x * w, ls.y * h, rs.x * w, rs.y * h
    sw = math.hypot(rx - lx, ry - ly)
    if cfg.use_z_compensation:
        sw = math.hypot(sw, (ls.z - rs.z) * w)
    if sw < 20:
        return None
    return {"nose_x": nose.x * w, "mid_x": (lx + rx) / 2.0, "sw": sw}


def pinch_ratio(hand: Hand, w: int, h: int) -> float:
    """Thumb-tip to index-tip distance divided by hand size (wrist to middle knuckle)."""
    p = hand.pts

    def dist(a, b):
        return math.hypot((p[a].x - p[b].x) * w, (p[a].y - p[b].y) * h)

    return dist(4, 8) / (dist(0, 9) + 1e-6)


class PinchDetector:
    """One nitro event per pinch; an observed release rearms the gesture."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.reset()

    def reset(self) -> None:
        self.pinched = False
        self.last_trigger = -999.0
        self.last_seen = 0.0

    def update(self, hands: list, w: int, h: int, now: float) -> bool:
        cfg = self.cfg
        if not hands:
            # Hands left the frame mid-pinch: the gesture is over.
            if self.pinched and now - self.last_seen > cfg.pinch_lost_reset:
                self.pinched = False
            return False

        best = min(pinch_ratio(hd, w, h) for hd in hands)
        self.last_seen = now
        if not self.pinched and best < cfg.pinch_on:
            self.pinched = True
            if now - self.last_trigger > cfg.nitro_cooldown:
                self.last_trigger = now
                return True
        elif self.pinched and best > cfg.pinch_off:
            self.pinched = False
        return False


class Calibrator:
    """Collect still-posture samples; restart with a message if the data is poor."""

    def __init__(self, cfg: Config, now: float):
        self.cfg = cfg
        self.message = ""
        self.restart(now)

    def restart(self, now: float) -> None:
        self.start = now
        self.samples: list = []

    def left(self, now: float) -> float:
        return max(0.0, self.cfg.calibration_seconds - (now - self.start))

    def update(self, feat: Optional[dict], now: float) -> Optional[dict]:
        """Return the baseline once calibration succeeds, else None."""
        cfg = self.cfg
        if feat:
            self.samples.append(feat)
        if self.left(now) > 0:
            return None
        if len(self.samples) < cfg.calib_min_samples:
            self.message = "Shoulders not visible - sit back a bit"
            self.restart(now)
            return None
        base = {k: float(np.median([s[k] for s in self.samples]))
                for k in ("nose_x", "mid_x", "sw")}
        jitter = max(float(np.std([s["nose_x"] for s in self.samples])),
                     float(np.std([s["mid_x"] for s in self.samples]))) / base["sw"]
        if jitter > cfg.calib_max_jitter:
            self.message = "Hold still during calibration"
            self.restart(now)
            return None
        self.message = ""
        return base


class GesturePipeline:
    """Pose features -> filtered gestures -> shaped driving commands."""

    def __init__(self, cfg: Config, base: dict):
        self.cfg = cfg
        self.base = base
        self.lean_filter = Ema(cfg.smooth_tau)
        self.ratio_filter = Ema(cfg.smooth_tau)
        self.reset()

    def reset(self) -> None:
        """Forget all motion state (pause, recalibration, tracking loss)."""
        self.lean_filter.reset()
        self.ratio_filter.reset()
        self.lean: Optional[float] = None
        self.ratio: Optional[float] = None
        self.gas_active = False
        self.brake_active = False
        self.nitro_until = 0.0
        self.steer = 0.0
        self.last_update: Optional[float] = None

    def update(self, feat, nitro_event, now, tracking_ok, sensitivity, auto_gas) -> Command:
        cfg = self.cfg
        dt = 1.0 / 30.0 if self.last_update is None else min(now - self.last_update, 0.1)
        self.last_update = now

        if not tracking_ok:
            self.reset()
            self.last_update = now
            return Command()

        if feat:
            raw_lean = 0.5 * ((feat["nose_x"] - self.base["nose_x"])
                              + (feat["mid_x"] - self.base["mid_x"])) / self.base["sw"]
            self.lean = self.lean_filter.update(raw_lean, dt)
            self.ratio = self.ratio_filter.update(feat["sw"] / self.base["sw"], dt)

        target = steer_from_lean(self.lean, sensitivity, cfg) if self.lean is not None else 0.0
        max_change = cfg.steer_slew_per_sec * dt
        self.steer += clamp(target - self.steer, -max_change, max_change)

        if self.ratio is not None:
            self.brake_active = (self.ratio > cfg.brake_on_ratio
                                 or (self.brake_active and self.ratio > cfg.brake_off_ratio))
            self.gas_active = (self.ratio < cfg.gas_on_ratio
                               or (self.gas_active and self.ratio < cfg.gas_off_ratio))
        gas = (auto_gas or self.gas_active) and not self.brake_active
        if nitro_event:
            self.nitro_until = now + cfg.nitro_hold
        return Command(self.steer, gas, self.brake_active, now < self.nitro_until,
                       self.lean, self.ratio)
