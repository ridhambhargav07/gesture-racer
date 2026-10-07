"""Status text, steering bar and control chips (ASCII only: Hershey fonts lack Unicode)."""

from __future__ import annotations

import cv2

from .models import CALIBRATING, GET_READY, PAUSED, RUN, Snapshot

FONT = cv2.FONT_HERSHEY_SIMPLEX
AA = cv2.LINE_AA
WHITE, RED, GOLD = (255, 255, 255), (0, 0, 255), (0, 255, 255)


def put(frame, text, y, scale=0.5, color=WHITE, thick=1, x=18):
    cv2.putText(frame, text, (x, y), FONT, scale, color, thick, AA)


def _steer_bar(frame, steer: float) -> None:
    h, w = frame.shape[:2]
    bw, y = int(w * 0.5), h - 26
    x0, cx = (w - bw) // 2, w // 2
    cv2.rectangle(frame, (x0, y), (x0 + bw, y + 8), (45, 45, 45), -1)
    x1 = cx + int(steer * bw / 2)
    color = (60, 140, 255) if steer > 0 else (120, 255, 80)
    cv2.rectangle(frame, (min(cx, x1), y), (max(cx, x1), y + 8), color, -1)
    cv2.line(frame, (cx, y - 4), (cx, y + 12), WHITE, 1, AA)


def _chips(frame, cmd) -> None:
    h = frame.shape[0]
    x = 18
    for name, on, color in (("GAS", cmd.gas, (120, 255, 80)),
                            ("BRAKE", cmd.brake, (80, 80, 255)),
                            ("NITRO", cmd.nitro, (0, 215, 255))):
        put(frame, name, h - 18, 0.55, color if on else (110, 110, 110), 2 if on else 1, x)
        x += 72 if name != "BRAKE" else 82


def draw_hud(frame, snap: Snapshot, debug: bool = False, ui_fps: float = 0.0) -> None:
    state = snap.state

    if state == CALIBRATING:
        put(frame, "CALIBRATING", 28, 0.75, GOLD, 2)
        put(frame, f"{snap.calib_left:.1f}s left  |  samples {snap.calib_samples}", 58)
        if not snap.has_pose:
            put(frame, "Face camera + shoulders visible", 84, 0.48, RED)
        elif snap.calib_msg:
            put(frame, snap.calib_msg, 84, 0.48, RED)
        return
    if state == GET_READY:
        put(frame, "READY", 28, 0.8, (0, 200, 255), 2)
        put(frame, f"Click the game window - {snap.ready_left:.0f}s", 58)
        return
    if state == PAUSED:
        put(frame, "PAUSED", 28, 0.8, (0, 165, 255), 2)
        return
    if state == RUN and not snap.tracking_ok:
        put(frame, "TRACKING LOST", 28, 0.75, RED, 2)
        return

    y = 28
    if snap.toast:
        put(frame, snap.toast, y, 0.6, GOLD, 2)
        y += 26
    _steer_bar(frame, snap.cmd.steer)
    _chips(frame, snap.cmd)
    if debug:
        put(frame, f"steer {snap.cmd.steer:+.2f}  sens {snap.sensitivity:.2f}  "
                   f"autogas {'on' if snap.auto_gas else 'off'}", y, 0.5, (0, 255, 0))
        put(frame, f"pose {snap.pose_ms:.0f}ms  hands {snap.hands_ms:.0f}ms  "
                   f"lag {snap.latency_ms:.0f}ms", y + 20, 0.5, (0, 255, 0))
        put(frame, f"engine {snap.fps:.0f}fps  preview {ui_fps:.0f}fps", y + 40, 0.5, (0, 255, 0))
