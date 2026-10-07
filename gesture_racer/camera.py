"""Threaded webcam capture that always hands out the newest frame."""

from __future__ import annotations

import threading
import time

import cv2

from .config import Config


class CameraStream:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.cap = cv2.VideoCapture(cfg.camera_index)
        self.opened = self.cap.isOpened()
        self.dead = False
        self._frame = None
        self._ts = 0.0
        self._seq = 0
        self._cond = threading.Condition()
        self._run = True
        if not self.opened:
            return
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.frame_w)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.frame_h)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        fails = 0
        while self._run:
            ok, frame = self.cap.read()
            if not ok:
                fails += 1
                if fails >= self.cfg.camera_fail_limit:
                    break
                time.sleep(0.01)
                continue
            fails = 0
            with self._cond:
                self._frame, self._ts, self._seq = frame, time.monotonic(), self._seq + 1
                self._cond.notify_all()
        with self._cond:
            self.dead = True
            self._cond.notify_all()

    def read(self, last_seq: int, timeout: float = 0.5):
        """Block for a frame newer than last_seq.

        Returns (frame, seq, captured_at) or (None, last_seq, 0.0) on timeout.
        Any number of consumers can read independently.
        """
        with self._cond:
            self._cond.wait_for(lambda: self._seq != last_seq or self.dead, timeout)
            if self._seq != last_seq:
                return self._frame, self._seq, self._ts
            return None, last_seq, 0.0

    def release(self):
        self._run = False
        if self.opened:
            self._thread.join(timeout=1.0)
        self.cap.release()
