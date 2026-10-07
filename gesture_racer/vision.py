"""MediaPipe wrapper: RGB frame in, plain landmark data out."""

from __future__ import annotations

import time

from .config import Config
from .models import Hand, Pt, VisionFrame


class Vision:
    def __init__(self, cfg: Config):
        try:
            import mediapipe as mp
            solutions = mp.solutions
        except (ImportError, AttributeError) as exc:
            raise RuntimeError(
                "This project needs the legacy MediaPipe API: pip install mediapipe==0.10.14"
            ) from exc
        self.pose = solutions.pose.Pose(
            model_complexity=cfg.pose_complexity,
            min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.hands = solutions.hands.Hands(
            max_num_hands=2, model_complexity=0,
            min_detection_confidence=0.6, min_tracking_confidence=0.5)

    def process(self, rgb, run_hands: bool) -> VisionFrame:
        rgb.flags.writeable = False          # lets MediaPipe skip a defensive copy
        t0 = time.perf_counter()
        res = self.pose.process(rgb)
        pose = ([Pt(l.x, l.y, l.z, l.visibility) for l in res.pose_landmarks.landmark]
                if res.pose_landmarks else None)
        t1 = time.perf_counter()

        hands: list = []
        if run_hands:
            hres = self.hands.process(rgb)
            if hres.multi_hand_landmarks:
                for i, hl in enumerate(hres.multi_hand_landmarks):
                    cls = hres.multi_handedness[i].classification[0]
                    hands.append(Hand(cls.label, float(cls.score),
                                      [Pt(l.x, l.y, l.z) for l in hl.landmark]))
        t2 = time.perf_counter()
        return VisionFrame(pose, hands, run_hands, (t1 - t0) * 1e3, (t2 - t1) * 1e3)

    def close(self) -> None:
        self.pose.close()
        self.hands.close()
