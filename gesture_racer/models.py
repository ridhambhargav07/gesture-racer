"""Plain data types shared between modules (no OpenCV / MediaPipe imports here)."""

from __future__ import annotations

from typing import NamedTuple, Optional

CALIBRATING, GET_READY, RUN, PAUSED = "CALIBRATING", "GET_READY", "RUN", "PAUSED"


class Pt(NamedTuple):
    """A normalized landmark (0..1 in image space) with a visibility score."""
    x: float
    y: float
    z: float = 0.0
    v: float = 1.0


class Hand(NamedTuple):
    label: str            # "Left" / "Right" (as the user sees themselves in the mirror)
    score: float
    pts: list             # 21 Pt


class VisionFrame(NamedTuple):
    pose: Optional[list]  # 33 Pt or None
    hands: list           # list[Hand]
    hands_ran: bool
    pose_ms: float
    hands_ms: float


class Command(NamedTuple):
    steer: float = 0.0
    gas: bool = False
    brake: bool = False
    nitro: bool = False
    lean: Optional[float] = None
    ratio: Optional[float] = None


class Snapshot(NamedTuple):
    """Everything the UI needs to draw one frame; produced by the engine thread."""
    state: str = CALIBRATING
    cmd: Command = Command()
    pose: Optional[list] = None
    hands: tuple = ()
    pinched: bool = False
    tracking_ok: bool = True
    has_pose: bool = False
    calib_left: float = 0.0
    calib_samples: int = 0
    calib_msg: str = ""
    ready_left: float = 0.0
    sensitivity: float = 1.0
    auto_gas: bool = True
    toast: str = ""
    fps: float = 0.0
    pose_ms: float = 0.0
    hands_ms: float = 0.0
    latency_ms: float = 0.0
