"""The brain: camera frames -> vision -> gestures -> keys, on its own thread.

The UI thread only draws, so a slow preview can never delay your steering.
"""

from __future__ import annotations

import threading
import time
import traceback

import cv2

from .camera import CameraStream
from .config import Config
from .controller import Hotkeys
from .gestures import (Calibrator, GesturePipeline, PinchDetector, clamp,
                       pose_features)
from .models import (CALIBRATING, GET_READY, PAUSED, RUN, Command, Snapshot)
from .vision import Vision


class Engine:
    def __init__(self, cfg: Config, prefs: dict, stream: CameraStream, backend,
                 hotkeys: Hotkeys, vision_factory=Vision):
        self.cfg = cfg
        self.stream, self.backend, self.hotkeys = stream, backend, hotkeys
        self.vision_factory = vision_factory
        self.sensitivity = clamp(float(prefs.get("sensitivity", cfg.steer_sensitivity)),
                                 cfg.sensitivity_min, cfg.sensitivity_max)
        self.auto_gas = bool(prefs.get("auto_gas", cfg.auto_gas))
        self.running = True
        self.error: str | None = None
        self.snap = Snapshot(sensitivity=self.sensitivity, auto_gas=self.auto_gas)
        self._toast, self._toast_until = "", 0.0
        self._thread = None

    # ---- lifecycle ----
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="engine", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def snapshot(self) -> Snapshot:
        return self.snap          # a single reference read: no lock needed

    def _toast_now(self, text: str, now: float) -> None:
        self._toast, self._toast_until = text, now + self.cfg.toast_seconds

    def _run(self) -> None:
        vision = None
        try:
            vision = self.vision_factory(self.cfg)
            self._loop(vision)
        except Exception as exc:
            self.error = f"{exc}\n{traceback.format_exc()}" if not isinstance(exc, RuntimeError) \
                else str(exc)
        finally:
            self.backend.set(0.0, False, False, False)
            if vision is not None:
                vision.close()
            self.running = False

    # ---- main loop ----
    def _loop(self, vision) -> None:
        cfg = self.cfg
        now = time.monotonic()
        state, calibrator, pipeline = CALIBRATING, Calibrator(cfg, now), None
        pinch = PinchDetector(cfg)
        cmd = Command()
        last_pose_seen = start_at = 0.0
        frame_idx = seq = 0
        fps = lat = pose_ms = hands_ms = 0.0
        last_tick = None
        last_hands: tuple = ()

        while self.running:
            frame, seq, t_cap = self.stream.read(seq)
            if frame is None:
                if self.stream.dead:
                    raise RuntimeError("Camera stopped delivering frames.")
                continue
            if self.backend.error is not None:
                raise RuntimeError(f"Keyboard backend failed: {self.backend.error}")

            now = time.monotonic()
            if last_tick is not None:
                inst = 1.0 / max(now - last_tick, 1e-6)
                fps = inst if fps == 0.0 else 0.85 * fps + 0.15 * inst
            last_tick = now

            # ---- hotkeys / actions ----
            if self.hotkeys.pop("quit"):
                break
            if self.hotkeys.pop("sensitivity_down"):
                self.sensitivity = max(cfg.sensitivity_min, self.sensitivity - cfg.sensitivity_step)
                self._toast_now(f"Sensitivity {self.sensitivity:.2f}", now)
            if self.hotkeys.pop("sensitivity_up"):
                self.sensitivity = min(cfg.sensitivity_max, self.sensitivity + cfg.sensitivity_step)
                self._toast_now(f"Sensitivity {self.sensitivity:.2f}", now)
            if self.hotkeys.pop("auto_gas"):
                self.auto_gas = not self.auto_gas
                self._toast_now(f"Auto gas {'ON' if self.auto_gas else 'OFF'}", now)
            if self.hotkeys.pop("recalib"):
                state, calibrator, pipeline = CALIBRATING, Calibrator(cfg, now), None
                pinch.reset()
                cmd = Command()
            if self.hotkeys.pop("toggle") and state in (RUN, PAUSED):
                state = PAUSED if state == RUN else RUN
                if pipeline is not None:     # stale filters/nitro must not leak across a pause
                    pipeline.reset()
                pinch.reset()
                cmd = Command()

            # ---- vision (flip so leaning toward screen-right steers right) ----
            rgb = cv2.flip(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), 1)
            h, w = rgb.shape[:2]
            vf = vision.process(rgb, run_hands=(frame_idx % cfg.hands_every_n == 0))
            frame_idx += 1
            pose_ms = vf.pose_ms if pose_ms == 0 else 0.9 * pose_ms + 0.1 * vf.pose_ms
            if vf.hands_ran:
                hands_ms = vf.hands_ms if hands_ms == 0 else 0.9 * hands_ms + 0.1 * vf.hands_ms
                last_hands = tuple(vf.hands)       # cached so the skeleton doesn't flicker

            feat = pose_features(vf.pose, w, h, cfg)
            if feat:
                last_pose_seen = now

            nitro_event = False
            if state == RUN and vf.hands_ran:
                nitro_event = pinch.update(vf.hands, w, h, now)

            # ---- state machine ----
            tracking_ok = True
            if state == CALIBRATING:
                base = calibrator.update(feat, now)
                if base is not None:
                    pipeline = GesturePipeline(cfg, base)
                    state, start_at = GET_READY, now + cfg.start_delay
            elif state == GET_READY:
                if now >= start_at:
                    state = RUN
            elif state == RUN:
                tracking_ok = (now - last_pose_seen) <= cfg.failsafe_seconds
                if pipeline is not None:
                    cmd = pipeline.update(feat, nitro_event, now, tracking_ok,
                                          self.sensitivity, self.auto_gas)

            if state == RUN:
                self.backend.set(cmd.steer, cmd.gas, cmd.brake, cmd.nitro)
            else:
                cmd = Command()
                self.backend.set(0.0, False, False, False)

            # Time from camera capture to keys being updated (what you actually feel).
            lat_inst = (time.monotonic() - t_cap) * 1e3
            lat = lat_inst if lat == 0 else 0.9 * lat + 0.1 * lat_inst

            self.snap = Snapshot(
                state=state, cmd=cmd, pose=vf.pose, hands=last_hands,
                pinched=pinch.pinched, tracking_ok=tracking_ok, has_pose=feat is not None,
                calib_left=calibrator.left(now), calib_samples=len(calibrator.samples),
                calib_msg=calibrator.message, ready_left=max(0.0, start_at - now),
                sensitivity=self.sensitivity, auto_gas=self.auto_gas,
                toast=self._toast if now < self._toast_until else "",
                fps=fps, pose_ms=pose_ms, hands_ms=hands_ms, latency_ms=lat)
