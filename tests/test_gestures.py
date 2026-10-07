import dataclasses

import pytest

from gesture_racer.config import Config
from gesture_racer.gestures import (Calibrator, Ema, GesturePipeline, PinchDetector,
                                    pinch_ratio, pose_features, steer_from_lean)
from gesture_racer.models import Command, Hand, Pt

CFG = Config()
BASE = {"nose_x": 320.0, "mid_x": 320.0, "sw": 150.0}


# ---------- steering ----------
def test_dead_zone_and_full_lock():
    assert steer_from_lean(0.03, 1.0, CFG) == 0.0
    assert steer_from_lean(CFG.max_lean, 1.0, CFG) == 1.0
    assert steer_from_lean(-CFG.max_lean, 1.0, CFG) == -1.0


def test_small_lean_gives_strong_turn():
    # A lean of ~half of full lock should already steer well past half.
    assert steer_from_lean(0.15, 1.0, CFG) > 0.55
    assert steer_from_lean(0.10, 1.0, CFG) > 0.40


def test_steering_is_monotonic_and_symmetric():
    vals = [steer_from_lean(x / 100, 1.0, CFG) for x in range(0, 40)]
    assert vals == sorted(vals)
    assert steer_from_lean(-0.12, 1.0, CFG) == -steer_from_lean(0.12, 1.0, CFG)


def test_sensitivity_scales_turn():
    assert steer_from_lean(0.10, 1.5, CFG) > steer_from_lean(0.10, 0.5, CFG)


# ---------- smoothing ----------
def test_ema_is_frame_rate_independent():
    def run(fps):
        e = Ema(0.028)
        e.update(0.0, 1 / fps)
        for _ in range(int(fps * 0.1)):
            e.update(1.0, 1 / fps)
        return e.v
    assert run(10) == pytest.approx(run(50), abs=0.01)


# ---------- pose features ----------
def _pose(nose_x=0.5, vis=1.0, sw=0.2):
    p = [Pt(0, 0, 0, 0.0)] * 33
    p = list(p)
    p[0] = Pt(nose_x, 0.3, 0, vis)
    p[11] = Pt(0.5 - sw / 2, 0.6, 0, vis)
    p[12] = Pt(0.5 + sw / 2, 0.6, 0, vis)
    return p


def test_pose_features_values_and_rejection():
    f = pose_features(_pose(), 640, 480, CFG)
    assert f["sw"] == pytest.approx(128.0)
    assert f["mid_x"] == pytest.approx(320.0)
    assert pose_features(_pose(vis=0.2), 640, 480, CFG) is None
    assert pose_features(None, 640, 480, CFG) is None
    assert pose_features(_pose(sw=0.01), 640, 480, CFG) is None


# ---------- pinch / nitro ----------
def _hand(ratio):
    pts = [Pt(0.5, 0.5)] * 21
    pts = list(pts)
    pts[0], pts[9] = Pt(0.5, 0.9), Pt(0.5, 0.5)                       # hand size = 0.4 * h
    pts[4] = Pt(0.5, 0.3)
    pts[8] = Pt(0.5 + ratio * 0.4 * 480 / 640, 0.3)
    return Hand("Left", 0.99, pts)


def test_pinch_ratio_matches_construction():
    assert pinch_ratio(_hand(0.3), 640, 480) == pytest.approx(0.3, abs=1e-3)


def test_one_event_per_pinch_with_cooldown():
    p, t, events = PinchDetector(CFG), 0.0, []
    for r, dt in [(1, .1), (.2, .1), (.2, .1), (1, .1), (.2, .1), (1, 1.0), (.2, .1)]:
        t += dt
        events.append(p.update([_hand(r)], 640, 480, t))
    # 2nd pinch lands inside the cooldown, the last one after it.
    assert events == [False, True, False, False, False, False, True]


def test_pinch_forgotten_when_hands_vanish():
    p = PinchDetector(CFG)
    p.update([_hand(0.2)], 640, 480, 10.0)
    assert p.pinched
    p.update([], 640, 480, 10.2)
    assert p.pinched                      # brief dropout: keep state (no retrigger)
    p.update([], 640, 480, 10.6)
    assert not p.pinched                  # gone long enough: gesture is over


# ---------- pipeline ----------
def _feat(dx=0.0, sw=150.0):
    return {"nose_x": 320 + dx, "mid_x": 320 + dx, "sw": sw}


def _run(pl, feat, seconds=1.0, t0=0.0, **kw):
    t, c = t0, None
    for _ in range(int(seconds * 30)):
        t += 1 / 30
        c = pl.update(feat, kw.get("nitro", False), t, kw.get("ok", True), 1.0, kw.get("auto", True))
    return c, t


def test_small_lean_reaches_strong_steer_quickly():
    pl = GesturePipeline(CFG, BASE)
    c, _ = _run(pl, _feat(dx=0.15 * 150), seconds=0.25)       # lean 0.15, a quarter second
    assert c.steer > 0.55 and c.gas and not c.brake


def test_full_lean_hits_full_lock():
    c, _ = _run(GesturePipeline(CFG, BASE), _feat(dx=0.3 * 150))
    assert c.steer == pytest.approx(1.0, abs=0.01)


def test_brake_beats_gas_and_hysteresis_holds():
    pl = GesturePipeline(CFG, BASE)
    c, t = _run(pl, _feat(sw=180), 0.5)                       # ratio 1.2 -> brake
    assert c.brake and not c.gas
    c, t = _run(pl, _feat(sw=165), 0.5, t0=t)                 # ratio 1.10: inside hysteresis band
    assert c.brake
    c, _ = _run(pl, _feat(sw=150), 0.5, t0=t)
    assert not c.brake and c.gas


def test_nitro_lasts_fixed_time():
    pl = GesturePipeline(CFG, BASE)
    _, t = _run(pl, _feat(), 0.2)
    assert pl.update(_feat(), True, t + 0.03, True, 1.0, True).nitro
    assert pl.update(_feat(), False, t + 1.0, True, 1.0, True).nitro
    assert not pl.update(_feat(), False, t + 1.7, True, 1.0, True).nitro


def test_tracking_loss_resets_everything():
    pl = GesturePipeline(CFG, BASE)
    _run(pl, _feat(dx=40), 0.5)
    c = pl.update(None, False, 5.0, False, 1.0, True)
    assert c == Command() and pl.lean is None and pl.steer == 0.0


# ---------- calibration ----------
def _calibrate(feats_at):
    cal, base = Calibrator(CFG, 0.0), None
    for i in range(45):
        base = cal.update(feats_at(i), i * 0.1) or base
    return cal, base


def test_calibration_success_and_failures():
    _, base = _calibrate(lambda i: {"nose_x": 320.0, "mid_x": 320.0, "sw": 150.0})
    assert base == {"nose_x": 320.0, "mid_x": 320.0, "sw": 150.0}

    cal, base = _calibrate(lambda i: {"nose_x": 320 + 30 * (-1) ** i, "mid_x": 320.0, "sw": 150.0})
    assert base is None and "still" in cal.message

    cal, base = _calibrate(lambda i: None)
    assert base is None and "not visible" in cal.message
