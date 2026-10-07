# Gesture Racer Documentation

## Overview

Gesture Racer is a Python project that converts webcam-based body movement into keyboard controls for a racing game. Instead of using a gamepad or steering wheel, the player controls the car by leaning left or right, leaning back to accelerate, leaning forward to brake, and pinching the thumb and index finger for nitro.

The project is built around a direct perception-to-input pipeline:

1. Webcam captures a live frame.
2. MediaPipe estimates the player's pose and hand landmarks.
3. The app extracts meaningful movement signals from the pose.
4. Those values are smoothed and translated into control commands.
5. The commands are sent to the game as keyboard input using `pynput`.

This is a simple and practical human-computer interaction system focused on one purpose: turning natural body motion into real driving actions.

This is the initial version of the project. It is a working foundation for a larger gesture control ecosystem, and upcoming versions will expand this into a more complete system with broader gesture support, smarter calibration, more control profiles, and more immersive interaction design.

## Project goal

The core goal is to make a driving game playable using body movement alone. The project demonstrates how computer vision and gesture recognition can be used to control software in a natural, physical way.

It is designed to be:

- simple to run
- easy to tune
- lightweight and portable
- based on standard webcam input
- focused on a real-world use case

## System design

The project is organized around a small sequence of operations.

### 1. Camera capture
The app opens the default webcam and reads frames continuously. These frames are flipped horizontally so steering feels more natural from the player's perspective.

### 2. Pose estimation
MediaPipe Pose is used to detect landmarks such as the nose, shoulders, and body alignment. These landmarks help determine whether the player is centered, leaning left, leaning right, or leaning forward or backward.

### 3. Feature extraction
The code derives a neutral baseline from the first calibration phase and then compares later frames against it. This gives values such as:

- shoulder width
- face/center offset
- body lean direction
- relative posture ratio

These extracted measurements become the actual control signals.

### 4. Filtering and smoothing
Raw vision data is noisy. The project applies exponential smoothing to stabilize the motion signal and reduce jitter. This makes steering feel stable instead of erratic.

### 5. Control mapping
The project converts pose information into the following commands:

- steering: based on horizontal lean
- acceleration: based on backward lean
- braking: based on forward lean
- nitro: based on thumb-index pinch detection

### 6. Keyboard simulation
The app sends actual key presses to the system so the game receives standard game controls. This means the player does not need a custom driver or an external controller.

## File structure

```text
proj2/
├── main.py
├── requirements.txt
├── gesture_racer_config.json
├── README.md
├── documentations.md
├── games/
└── __pycache__/
```

### `main.py`
This is the central file of the project. It contains most of the logic, including:

- webcam initialization
- MediaPipe model setup
- calibration state machine
- gesture detection
- control pipeline
- keyboard backend
- hotkeys
- HUD rendering
- main loop

This file is the heart of the app and is responsible for turning visual input into keyboard actions.

### `requirements.txt`
This file lists the required Python dependencies.

### `gesture_racer_config.json`
This file contains the adjustable settings used by the controller, such as:

- camera index
- frame dimensions
- calibration duration
- steering sensitivity
- dead zone
- acceleration and brake thresholds
- nitro thresholds
- failsafe timing

These values make it easier to tune the project for different rooms, cameras, and users.

### `games/`
This directory appears to contain the local Python environment used while running the project.

## Configuration and settings

The project includes structured tuning values that determine how responsive and stable the controls feel.

### Camera settings
These affect how the webcam is opened and how frames are processed:

- `camera_index`
- `frame_w`
- `frame_h`
- `camera_fps`
- `camera_mjpg`

### Calibration and control timing
These control how the player is measured and how quickly the system enters gameplay:

- `calibration_seconds`
- `start_delay`
- `recalib_delay`
- `failsafe_s`

### Steering tuning
These values shape how the car responds to body lean:

- `dead_zone`
- `max_lean`
- `steer_sensitivity`
- `sens_step`
- `sens_min`
- `sens_max`
- `pwm_period`

### Gas and brake tuning
These values control how aggressively the system responds to forward or backward motion:

- `gas_on`
- `gas_off`
- `brake_on`
- `brake_off`

### Nitro tuning
These define the pinch threshold and nitro timing:

- `pinch_on`
- `pinch_off`
- `nitro_hold_s`
- `nitro_cooldown`

## Main logic in detail

### Pose feature extraction
The function `pose_features()` extracts the features needed to track the player. It reads the nose, shoulder positions, and body width from MediaPipe pose landmarks.

It returns values such as:

- `nose_x`
- `mid_x`
- `sw`
- shoulder and nose coordinates

These are used to calculate how much the player is leaning and whether their posture is stable enough to use.

### Steering logic
The steering function maps body lean to a target steering value between `-1` and `1`:

- if the lean is inside the dead zone, the output is zero
- larger values outside the dead zone scale up the steering force
- sensitivity modifies the overall strength of steering

This helps prevent small pose noise from causing the car to wobble unpredictably.

### Smoothing logic
The `Ema` class implements an exponential moving average. It is used to smooth values like:

- lean
- body ratio
- raw pose-derived signals

This keeps the driving experience responsive without being twitchy.

### Gesture control pipeline
The `GestureControlPipeline` class sits between the pose detector and the keyboard backend. It is responsible for:

- processing the current pose features
- calming noisy movement using EMA filtering
- generating steering direction
- deciding whether gas should be active
- deciding whether brake should be active
- timing nitro activation

It returns a tuple containing:

- steering value
- gas state
- brake state
- nitro state
- lean value
- ratio value

### Pinch detection
The `PinchDetector` tracks a hand pinch gesture using the thumb and index finger distances. It treats a pinch as a one-time nitro event and only triggers the next event after the hand is released and the cooldown expires.

This prevents accidental repeat nitro triggers from a held pinch.

## Keyboard backend

The `KeyboardBackend` class simulates keyboard input with `pynput`.

It maintains the current state of:

- left arrow
- right arrow
- up arrow
- down arrow
- shift

It updates those keys at a steady loop rate so the game receives a stable stream of input. Presses are released when the corresponding command ends.

This is the final link between human movement and the racing game itself.

## Hotkey system

The `Hotkeys` class listens for global keyboard events while the app is running. These shortcuts allow the user to adjust the system without interacting with the main UI.

Supported global actions include:

- sensitivity down
- sensitivity up
- auto-gas toggle
- pause/resume
- recalibration
- quit

This makes the controller feel more practical during live gameplay.

## State machine

The app uses a simple state machine with these states:

- `CALIBRATING`
- `GET_READY`
- `RUN`
- `PAUSED`

### `CALIBRATING`
The app collects a set of pose samples and computes a baseline posture.

### `GET_READY`
Once calibration is complete, the app gives the user a short countdown to focus the game window.

### `RUN`
The game controls are active and the app continuously maps pose changes to input.

### `PAUSED`
Inputs are suspended so the player can stop and resume without resetting calibration.

## User experience

The app is meant to feel smooth and direct:

- the player stands naturally in front of the camera
- a short setup step calibrates the posture
- the game starts after a ready countdown
- movement directly controls the car
- controls can be re-tuned without changing the app structure

The preview window helps the player orient themselves and keep their body in camera view. The HUD remains minimal so the game experience stays focused.

## Why this project is useful

This project is useful because it demonstrates a real-world human-input interface built from simple components:

- computer vision
- pose estimation
- gesture detection
- control systems
- keyboard automation

It shows how a regular webcam and open-source tools can be used to create an interactive driving experience without expensive hardware.

## Strengths of the project

- lightweight and easy to understand
- no advanced hardware required
- fast to prototype and test
- configurable and adjustable
- easy to extend with new gestures or platforms

## Areas for improvement

The project is intentionally minimal, but there are some practical limitations:

- track quality depends heavily on lighting
- posture changes may affect the baseline measurement
- steering may need tuning for different users
- accurate hand tracking requires a clear view of the hands
- keyboard input only works when the target game is focused

## Future evolution

This is still an early-stage prototype, but the project has strong potential. A future version could include:

- more personalized calibration profiles
- advanced gesture recognition across multiple body parts
- support for different game genres and control schemes
- a more polished user interface
- more robust tracking under varied real-world conditions
- a full gesture-control ecosystem beyond racing games

## Summary

Gesture Racer is a practical webcam-driven control project that translates body movement into racing inputs. It is a compact, useful, and understandable system that demonstrates how gestures can become real control signals in a game environment.

It is an initial version of a larger vision, but it already proves the core concept clearly: natural motion can become an intuitive interaction layer between the player and the game.
