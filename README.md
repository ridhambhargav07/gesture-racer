# Gesture Racer

This project turns body movement into driving inputs. A webcam tracks your pose, and the app turns leaning, braking, and pinch gestures into keyboard actions for a racing game.

It is a simple and practical system built around a single Python script and a small set of configuration values. The goal is to make driving feel natural without using a steering wheel or gamepad.

## What the project does

The app watches the player through the webcam and reads:

- head and shoulder position for steering
- forward or backward lean for braking and acceleration
- pinch gesture between thumb and index finger for nitro

Those cues are translated into keyboard presses for the game, including left, right, up, down, and Shift.

## Controls

| Movement | Game input |
| --- | --- |
| Lean left | Left arrow |
| Lean right | Right arrow |
| Lean backward | Up arrow / accelerate |
| Lean forward | Down arrow / brake |
| Thumb + index pinch | Shift / nitro |

### Global hotkeys

- F5 / F6: decrease or increase steering sensitivity
- F7: toggle automatic acceleration
- F8: pause or resume controls
- F9: recalibrate
- F10: quit app

When the preview window is active:

- P: pause or resume
- C: recalibrate
- Q: quit

## Quick start

```bash
pip install -r requirements.txt
python main.py
```

Then:

1. Keep your face and shoulders visible.
2. Stay still while the app calibrates.
3. Focus the racing game window when the ready timer starts.

## Files in the project

```text
proj2/
├── main.py
├── requirements.txt
├── gesture_racer_config.json
├── games/
├── README.md
└── .gitignore (if present)
```

### `main.py`
This is the main control script. It handles:

- webcam input
- pose detection via MediaPipe
- calibration of the player's neutral posture
- smoothing and filtering of body movement
- steering, acceleration, brake, and nitro logic
- keyboard events through `pynput`
- hotkeys and the preview window

### `requirements.txt`
Lists the packages needed to run the project.

### `gesture_racer_config.json`
Stores tuning values like:

- camera settings
- calibration timing
- dead zone and steering sensitivity
- gas and brake thresholds
- nitro pinch thresholds
- failsafe timing

## How it works

The project uses a straightforward loop:

1. Capture a frame from the webcam.
2. Run pose detection to find landmarks on the body.
3. Measure the player's body position relative to a calibration baseline.
4. Apply smoothing so small hand or body movements do not create noisy controls.
5. Convert the motion into steering and acceleration values.
6. Send those values to the game as real keyboard input.

### Calibration

At startup, the app records a neutral standing posture. That posture becomes the baseline for later calculations. The goal is to compare the player's current pose against that saved reference.

### Steering

The steering value comes from body lean. A very small lean is ignored, and larger lean changes produce stronger input. This helps the car feel responsive without twitching from tiny movements.

### Gas and brake

The app compares the current body ratio to the calibration baseline. When the player leans back, the car accelerates. When the player leans forward, the car brakes. The system includes a failsafe so controls are released if tracking is lost.

### Nitro

The nitro system watches finger distance using the hand model. A pinch between the thumb and index finger triggers a short nitro burst. The trigger is intentionally limited by a cooldown so it does not fire repeatedly from a single hold.

## Tuning

The project is designed to be easy to adjust. The most important values are in the config file and in the main script:

- `DEAD_ZONE`: ignores very small body movement
- `STEER_SENSITIVITY`: controls how strongly leaning affects steering
- `GAS_ON_RATIO` and `BRAKE_ON_RATIO`: define acceleration and braking thresholds
- `PINCH_ON` and `PINCH_OFF`: set when nitro should trigger or reset
- `FAILSAFE_SECONDS`: controls how quickly inputs release if tracking is lost

A small amount of tuning usually makes the controls feel much more natural for your room, webcam angle, and lighting.

## Limitations

This is a practical prototype, not a perfect control system. It works best when:

- the camera has good lighting
- the player stays in frame
- the face and shoulders remain visible
- the target game is focused and active

Movement can feel inconsistent if the camera is too far away, too close, or slightly angled.

## This is the initial version

This is the initial version of the project, built as a working foundation for gesture-based game control. In upcoming versions, we plan to grow this into a full gesture control ecosystem with more accurate motion tracking, better calibration, improved control profiles, broader game compatibility, and a more complete interaction system.

## Future direction

The project can be expanded in several useful ways:

- support for more control mappings and game profiles
- improved gesture recognition for smoother motion
- better calibration and posture handling
- support for different camera setups and lighting conditions
- integration with a broader gesture-control framework

## Summary

Gesture Racer is a compact webcam-driven control system that turns natural body motion into driving inputs. It is intentionally lightweight, practical, and easy to tune, which makes it a good starting point for a more advanced gesture-control project.
