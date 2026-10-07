"""All tunable settings in one place, plus tiny on-disk preferences."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PREFS_PATH = Path.home() / ".gesture_racer.json"


@dataclass(frozen=True)
class Config:
    # --- camera ---
    camera_index: int = 0
    frame_w: int = 640
    frame_h: int = 480
    camera_fail_limit: int = 60       # consecutive failed reads before giving up
    preview_scale: float = 1.0

    # --- vision ---
    pose_complexity: int = 0          # 0 = lite (fastest), 1 = full (more accurate)
    hands_every_n: int = 2            # run hand detection every N frames

    # --- game key bindings (names from pynput.keyboard.Key, or a single character) ---
    key_left: str = "left"
    key_right: str = "right"
    key_gas: str = "up"
    key_brake: str = "down"
    key_nitro: str = "shift"

    # --- calibration ---
    calibration_seconds: float = 4.0
    calib_min_samples: int = 20
    calib_max_jitter: float = 0.08    # max sway (fraction of shoulder width) while calibrating
    start_delay: float = 5.0          # time to click the game window after calibration

    # --- steering: small lean = strong turn, bigger lean = full lock ---
    dead_zone: float = 0.04           # lean below this is ignored
    max_lean: float = 0.22            # lean (in shoulder widths) that gives full lock
    steer_curve: float = 0.60         # <1 boosts small leans, 1 = linear
    steer_sensitivity: float = 1.0
    sensitivity_step: float = 0.1
    sensitivity_min: float = 0.4
    sensitivity_max: float = 1.8
    steer_slew_per_sec: float = 30.0  # how fast the wheel may move (1.0 = full lock)
    pwm_period: float = 0.10          # analog steering is faked by pulsing the arrow key

    # --- gas / brake (shoulder-width ratio, 1.0 = calibration posture) ---
    gas_on_ratio: float = 0.91
    gas_off_ratio: float = 0.95
    brake_on_ratio: float = 1.12
    brake_off_ratio: float = 1.08
    auto_gas: bool = True
    use_z_compensation: bool = False  # experimental: undo shoulder shrink when torso twists

    # --- nitro: one pinch = one fixed-length tap ---
    pinch_on: float = 0.42            # thumb-index distance / hand size
    pinch_off: float = 0.56
    pinch_lost_reset: float = 0.4     # forget a held pinch if hands vanish this long
    nitro_hold: float = 1.5
    nitro_cooldown: float = 0.8

    # --- smoothing / safety ---
    smooth_tau: float = 0.02          # EMA time constant (seconds); lower = snappier
    failsafe_seconds: float = 0.5     # release controls after tracking is lost
    watchdog_seconds: float = 0.5     # backend releases keys if the engine stops sending
    backend_sleep: float = 0.004
    toast_seconds: float = 1.5


def load_prefs() -> dict:
    try:
        return json.loads(PREFS_PATH.read_text())
    except (OSError, ValueError):
        return {}


def save_prefs(sensitivity: float, auto_gas: bool) -> None:
    try:
        PREFS_PATH.write_text(json.dumps(
            {"sensitivity": round(sensitivity, 2), "auto_gas": auto_gas}, indent=2))
    except OSError:
        pass
