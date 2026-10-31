# Architecture

ZYRO is a single-process, single-threaded desktop application. There is no
server, no background service, and no network layer.

## Pipeline

```
webcam frame
    |
    v
Camera.read()                    OpenCV VideoCapture, 640x480
    |
    v
HandTracker.process()            MediaPipe HandLandmarker, 21 landmarks
    |
    v
GestureRecognizer.recognize()    rule-based classification
    |
    +--> process_frame()         pointing / pinch move the cursor
    |
    +--> process_gesture_actions()  clicks, scroll, window close
             |
             v
        MouseController
             |
             v
        win_input (Win32 SendInput)
             |
             v
        cursor / buttons / wheel
```

Every frame is processed and discarded. Nothing is written to disk.

## Modules

| Module | Responsibility |
|---|---|
| `main.py` | Entry point, camera loop, gesture-to-action dispatch, keyboard shortcuts |
| `zyro/config.py` | Every tunable value, centralised |
| `zyro/camera.py` | Webcam open/read/release with failure handling |
| `zyro/hand_tracker.py` | MediaPipe wrapper; landmark extraction and drawing |
| `zyro/gesture_recognizer.py` | Rule-based gesture classification (no ML model of its own) |
| `zyro/mouse_controller.py` | Cursor mapping, filtering, click/scroll, window control |
| `zyro/win_input.py` | Native Win32 `SendInput` for mouse only |
| `zyro/ui.py` | HUD, command screen, search overlay |
| `zyro/virtual_keyboard.py` | On-screen keyboard that builds a search query string |

## Coordinate spaces

1. **Landmark space** — MediaPipe returns normalised `(x, y)` in `0..1`,
   origin top-left of the camera frame.
2. **Mapped space** — `MouseController.map_normalized()` applies a gain about
   the frame centre, clamps to `0..1`, then optionally mirrors X so moving
   your hand right moves the cursor right.
3. **Screen space** — multiplied by the primary display size, filtered,
   speed-clamped, then rounded.

## Cursor filtering

A fixed exponential smoothing factor forces a trade-off: enough damping to
kill webcam jitter also adds visible lag on fast movement. ZYRO uses a
**1-euro filter** instead, whose cutoff frequency rises with estimated speed:

- at rest, cutoff is `MOUSE_FILTER_MIN_CUTOFF` (heavy damping, no jitter)
- while moving, cutoff scales with `MOUSE_FILTER_BETA * |velocity|`

A second stage clamps travel to `MOUSE_MAX_SPEED` px/s so one bad landmark
cannot teleport the cursor. The filter is reset whenever tracking is lost,
otherwise reacquisition would interpolate across the screen.

## Click safety

A click has three preconditions:

1. the pinch must last at least `PINCH_MIN_HOLD` (shorter is noise)
2. the pointer must have been slower than `CLICK_STILL_SPEED` for
   `CLICK_STILL_WINDOW` seconds
3. the pinch cooldown must have elapsed

Condition 2 is what stops icons and taskbar buttons from activating while
the cursor merely passes over them. Double-click-on-hold is disabled by
default (`PINCH_ENABLE_DOUBLE_CLICK = False`) because it fired on whatever
sat under the pointer.

## Gesture state machines

Each gesture owns its own timer so a dropped frame cannot leak state into
another gesture:

| Gesture | State | Fires when |
|---|---|---|
| Pinch | `pinch_started_at`, `pinch_fired` | on release, one click |
| Two finger | `two_finger_*` | scroll by accumulated motion, or right click after a still hold |
| Close window | `close_window_*` | 0.6 s to arm, a further 0.6 s to confirm |
| Palm | `palm_*` | 0.8 s hold toggles pause |

## Security boundaries

- Only `user32.dll` is loaded through `ctypes`.
- No `subprocess`, `os.system`, `eval`, `exec`, or dynamic import.
- No socket is ever created; the process holds zero network handles.
- Keyboard synthesis was removed entirely — `SendInput` is used for mouse
  events only.
- The browser is opened only through `webbrowser.open()` with a
  `quote_plus`-encoded Google query, after two confirmation pinches.
- The application never requests elevation.

## Tuning

All values live in `zyro/config.py`. The ones users change most:

| Setting | Effect |
|---|---|
| `MOUSE_SENSITIVITY` | Overall cursor gain |
| `MOUSE_PRECISION_SCALE` | Gain multiplier while precision mode is on |
| `MOUSE_FILTER_MIN_CUTOFF` | Lower = smoother at rest, more lag |
| `MOUSE_FILTER_BETA` | Higher = snappier fast movement |
| `CLICK_STILL_WINDOW` | Lower = easier to click, more accidental clicks |
| `PINCH_RATIO` | Pinch distance as a fraction of hand size |
| `HAND_DETECTION_CONFIDENCE` | Lower = finds hands in poor light, more false positives |
