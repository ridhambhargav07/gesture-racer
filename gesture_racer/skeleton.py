"""Full-body skeleton overlay: thin AA lines, round joint dots, per-part colors.

Style matches the classic MediaPipe demo (thin pink lines, dark dots, "Left 0.99"
labels) but every body part gets its own color so it pops on camera.
Colors are BGR (OpenCV order).
"""

from __future__ import annotations

import cv2

from .config import Config
from .gestures import pinch_ratio
from .models import Hand

AA = cv2.LINE_AA
LINE_THICKNESS = 2
DOT_RADIUS = 4
DOT_FILL = (70, 20, 60)               # dark joint core, colored ring on top
FONT = cv2.FONT_HERSHEY_SIMPLEX

PALETTE = {
    # body
    "face":      (0, 215, 255),       # gold
    "torso":     (255, 170, 40),      # sky blue (shoulders + hips)
    "left_arm":  (120, 255, 80),      # spring green
    "right_arm": (60, 140, 255),      # orange
    "left_leg":  (230, 255, 0),       # aqua
    "right_leg": (90, 90, 255),       # coral red
    # fingers
    "thumb":     (70, 70, 255),       # red
    "index":     (255, 0, 255),       # magenta (the classic MediaPipe pink)
    "middle":    (0, 230, 255),       # yellow
    "ring":      (0, 255, 110),       # green
    "pinky":     (255, 210, 0),       # cyan-blue
    "palm":      (210, 40, 200),      # purple-pink
}

POSE_LINKS = {
    "face":      [(8, 6), (6, 5), (5, 4), (4, 0), (0, 1), (1, 2), (2, 3), (3, 7), (10, 9)],
    "torso":     [(11, 12), (11, 23), (12, 24), (23, 24)],
    "left_arm":  [(11, 13), (13, 15)],
    "right_arm": [(12, 14), (14, 16)],
    "left_leg":  [(23, 25), (25, 27), (27, 29), (29, 31), (27, 31)],
    "right_leg": [(24, 26), (26, 28), (28, 30), (30, 32), (28, 32)],
}
POSE_DOTS = {
    "face":      range(0, 11),
    "torso":     (11, 12, 23, 24),
    "left_arm":  (13, 15),
    "right_arm": (14, 16),
    "left_leg":  (25, 27, 29, 31),
    "right_leg": (26, 28, 30, 32),
}

HAND_LINKS = {
    "palm":   [(0, 1), (0, 5), (5, 9), (9, 13), (13, 17), (0, 17)],
    "thumb":  [(1, 2), (2, 3), (3, 4)],
    "index":  [(5, 6), (6, 7), (7, 8)],
    "middle": [(9, 10), (10, 11), (11, 12)],
    "ring":   [(13, 14), (14, 15), (15, 16)],
    "pinky":  [(17, 18), (18, 19), (19, 20)],
}
HAND_DOTS = {
    "palm":   (0,),
    "thumb":  (1, 2, 3, 4),
    "index":  (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring":   (13, 14, 15, 16),
    "pinky":  (17, 18, 19, 20),
}


def _dot(img, p, color, radius=DOT_RADIUS):
    cv2.circle(img, p, radius, DOT_FILL, -1, AA)
    cv2.circle(img, p, radius, color, 1, AA)


def _px(p, w, h):
    return (int(max(-1e4, min(1e4, p.x * w))), int(max(-1e4, min(1e4, p.y * h))))


def draw_pose(img, pose, min_vis: float = 0.5) -> None:
    if not pose:
        return
    h, w = img.shape[:2]
    pts = {i: _px(p, w, h) for i, p in enumerate(pose) if p.v >= min_vis}
    for part, links in POSE_LINKS.items():
        for a, b in links:
            if a in pts and b in pts:
                cv2.line(img, pts[a], pts[b], PALETTE[part], LINE_THICKNESS, AA)
    for part, idxs in POSE_DOTS.items():
        for i in idxs:
            if i in pts:
                _dot(img, pts[i], PALETTE[part], 3 if part == "face" else DOT_RADIUS)
    if 0 in pts and 11 in pts and 12 in pts:
        conf = (pose[0].v + pose[11].v + pose[12].v) / 3.0
        x, y = pts[0]
        cv2.putText(img, f"Body {conf:.2f}", (x + 28, y - 26), FONT, 0.6,
                    PALETTE["torso"], 2, AA)


def draw_hands(img, hands, cfg: Config, pinched: bool = False) -> None:
    h, w = img.shape[:2]
    for hand in hands:
        pts = [_px(p, w, h) for p in hand.pts]
        for part, links in HAND_LINKS.items():
            for a, b in links:
                cv2.line(img, pts[a], pts[b], PALETTE[part], LINE_THICKNESS, AA)
        for part, idxs in HAND_DOTS.items():
            for i in idxs:
                _dot(img, pts[i], PALETTE[part])

        # Pinch readout on the thumb-index gap (this is the nitro trigger).
        ratio = pinch_ratio(hand, w, h)
        active = ratio < cfg.pinch_on
        c = (0, 255, 255) if active or pinched else (255, 255, 255)
        cv2.line(img, pts[4], pts[8], c, 1, AA)
        mid = ((pts[4][0] + pts[8][0]) // 2 + 6, (pts[4][1] + pts[8][1]) // 2 - 6)
        cv2.putText(img, f"{ratio:.2f}", mid, FONT, 0.5, c, 1, AA)

        # "Left 0.99" label under the wrist, in the palm color.
        cv2.putText(img, f"{hand.label} {hand.score:.2f}",
                    (pts[0][0] - 30, pts[0][1] + 28), FONT, 0.7, PALETTE["palm"], 2, AA)


def draw_skeleton(img, snap, cfg: Config) -> None:
    draw_pose(img, snap.pose)
    draw_hands(img, snap.hands, cfg, snap.pinched)
