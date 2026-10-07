import dataclasses
import time

from gesture_racer.config import Config
from gesture_racer.controller import KeyboardBackend, Hotkeys, _resolve_key

CFG = dataclasses.replace(Config(), watchdog_seconds=0.25)


class FakeCtl:
    def __init__(self):
        self.down = set()

    def press(self, k):
        self.down.add(k)

    def release(self, k):
        self.down.discard(k)


def make():
    ctl = FakeCtl()
    return ctl, KeyboardBackend(CFG, ctl)


def test_gas_and_nitro_pressed_then_released_on_close():
    ctl, be = make()
    be.set(0.0, True, False, True)
    time.sleep(0.08)
    assert _resolve_key("up") in ctl.down and _resolve_key("shift") in ctl.down
    be.close()
    assert not ctl.down


def test_full_steer_holds_arrow():
    ctl, be = make()
    be.set(1.0, False, False, False)
    time.sleep(0.08)
    assert _resolve_key("right") in ctl.down
    be.set(-1.0, False, False, False)
    time.sleep(0.08)
    assert _resolve_key("left") in ctl.down and _resolve_key("right") not in ctl.down
    be.close()


def test_partial_steer_pulses_the_key():
    ctl, be = make()
    be.set(0.5, False, False, False)
    seen = set()
    for _ in range(80):
        seen.add(_resolve_key("right") in ctl.down)
        time.sleep(0.005)
    be.close()
    assert seen == {True, False}


def test_brake_overrides_gas():
    ctl, be = make()
    be.set(0.0, True, True, False)
    time.sleep(0.08)
    assert _resolve_key("down") in ctl.down and _resolve_key("up") not in ctl.down
    be.close()


def test_watchdog_releases_keys_when_engine_stalls():
    ctl, be = make()
    be.set(0.0, True, False, True)
    time.sleep(0.1)
    assert ctl.down
    time.sleep(CFG.watchdog_seconds + 0.2)
    assert not ctl.down
    be.close()


def test_backend_failure_is_captured_and_keys_released():
    class Bad(FakeCtl):
        def press(self, k):
            raise RuntimeError("boom")
    be = KeyboardBackend(CFG, Bad())
    be.set(0.0, True, False, False)
    time.sleep(0.1)
    assert isinstance(be.error, RuntimeError)
    be.close()


def test_hotkey_flags_are_consumed_once():
    hk = Hotkeys(listen=False)
    hk.press("toggle")
    assert hk.pop("toggle") is True
    assert hk.pop("toggle") is False
