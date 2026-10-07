"""UI thread: draws the preview and forwards keypresses. Control runs in engine.py."""

from __future__ import annotations

import argparse
import atexit
import dataclasses
import signal
import sys
import time

import cv2

from .camera import CameraStream
from .config import Config, load_prefs, save_prefs
from .controller import Hotkeys, KeyboardBackend
from .engine import Engine
from .hud import draw_hud
from .skeleton import draw_skeleton

WINDOW = "Gesture Racer"
PREVIEW_KEYS = {ord("q"): "quit", ord("p"): "toggle", ord("c"): "recalib"}


class App:
    def __init__(self, cfg: Config, prefs: dict, debug: bool = False):
        self.cfg, self.prefs, self.debug = cfg, prefs, debug
        self.skeleton = True

    def run(self) -> int:
        cfg = self.cfg
        stream = CameraStream(cfg)
        if not stream.opened:
            print(f"Unable to open camera {cfg.camera_index}. "
                  "Check the connection or pass --camera N.")
            return 1

        backend = KeyboardBackend(cfg)
        atexit.register(backend.release_all)
        hotkeys = Hotkeys()
        engine = Engine(cfg, self.prefs, stream, backend, hotkeys)
        engine.start()

        cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
        try:
            cv2.setWindowProperty(WINDOW, cv2.WND_PROP_TOPMOST, 1)
        except Exception:
            pass

        seq, ui_fps, last = 0, 0.0, None
        try:
            while engine.running:
                frame, seq, _ = stream.read(seq, timeout=0.2)
                if frame is None:
                    self._keys(hotkeys)
                    continue
                now = time.monotonic()
                if last is not None:
                    inst = 1.0 / max(now - last, 1e-6)
                    ui_fps = inst if ui_fps == 0 else 0.9 * ui_fps + 0.1 * inst
                last = now

                frame = cv2.flip(frame, 1)       # mirror view
                snap = engine.snapshot()
                if self.skeleton:
                    draw_skeleton(frame, snap, cfg)
                draw_hud(frame, snap, self.debug, ui_fps)
                if cfg.preview_scale != 1:
                    frame = cv2.resize(frame, None, fx=cfg.preview_scale,
                                       fy=cfg.preview_scale, interpolation=cv2.INTER_AREA)
                cv2.imshow(WINDOW, frame)
                self._keys(hotkeys)
        finally:
            engine.stop()
            backend.close()                      # releases every held key
            hotkeys.stop()
            stream.release()
            cv2.destroyAllWindows()
            save_prefs(engine.sensitivity, engine.auto_gas)

        if engine.error:
            print(engine.error)
            return 1
        return 0

    def _keys(self, hotkeys: Hotkeys) -> None:
        key = cv2.waitKey(1) & 0xFF
        if key in PREVIEW_KEYS:
            hotkeys.press(PREVIEW_KEYS[key])
        elif key == ord("h"):
            self.debug = not self.debug
        elif key == ord("k"):
            self.skeleton = not self.skeleton


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Gesture Racer: drive browser games by leaning.")
    ap.add_argument("--camera", type=int, default=Config.camera_index, help="camera index")
    ap.add_argument("--pose-complexity", type=int, choices=(0, 1),
                    default=Config.pose_complexity, help="0 = fastest, 1 = more accurate")
    ap.add_argument("--debug", action="store_true", help="show timing overlay")
    ap.add_argument("--reset", action="store_true", help="ignore saved preferences")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = dataclasses.replace(Config(), camera_index=args.camera,
                              pose_complexity=args.pose_complexity)
    prefs = {} if args.reset else load_prefs()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))   # lets `finally` release keys
    try:
        return App(cfg, prefs, args.debug).run()
    except KeyboardInterrupt:
        return 0
