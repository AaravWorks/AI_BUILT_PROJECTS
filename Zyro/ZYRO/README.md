# ZYRO - Hand-Gesture Control System

A futuristic computer-control system that lets you interact with your Windows PC using only hand gestures detected through your webcam.

> **Status:** early release. Recognition quality depends heavily on camera
> placement and lighting — expect to tune `zyro/config.py` for your setup.
> If the HUD shows `NO HAND DETECTED`, see [Troubleshooting](#troubleshooting).

## What this does — and what it does not do

ZYRO reads your webcam, recognises hand landmarks locally, and turns gestures
into pointer events on the same machine.

**It does**
- Move the cursor, click, scroll, and minimize/close the window under it
- Process every frame in local memory and discard it

**It does not**
- Connect to the network, open a port, or send data anywhere
- Read or write files outside its own folder
- Execute shell commands or launch processes
- Synthesise keyboard input — it cannot type into other applications
- Record, store, or transmit webcam frames
- Require administrator privileges

The only way ZYRO can open another application is the optional search
feature, which asks your default browser to open a Google query and requires
two deliberate pinches to trigger.

## Quick Start

### 1. Install Python
- Python 3.10 or newer (3.10-3.12 recommended for best package compatibility)

### 2. Create Virtual Environment (Recommended)
```powershell
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

Or manually:
```powershell
pip install opencv-python mediapipe pygetwindow numpy
```

### 4. Run
```powershell
python main.py
```

On Windows you can also double-click `run.bat`, which checks that Python is on
your PATH first.

## Controls

| Gesture / Key | Action |
|---|---|
| Index finger pointing | Move mouse cursor |
| Thumb + Index pinch, cursor held still | Single click |
| Two fingers up/down | Scroll |
| Index + Middle held still | Right click |
| Index + Middle folded, hold 0.6s, hold again to confirm | Close the window under cursor |
| Open palm for 0.8s | Pause/Resume gesture control |
| M key | Minimize the window under the cursor |
| P key | Toggle precision mode (fine cursor control) |
| S key | Toggle search |
| N key | Toggle command reference |
| Q key | Toggle pause |
| ESC | Quit application |
| Window X button | Quit application (closes the preview window) |

Clicks are refused while the cursor is still moving, so an icon cannot
activate just because the pointer passed over it. Double-click-on-hold is
not enabled: it fired on whatever file or application sat under the cursor.
Browser search requires a second confirming pinch.

## Quitting

ZYRO quits on **ESC** or by clicking the **X button** on the preview window.
Either one releases the webcam and closes the window. If you close the
command prompt instead of quitting ZYRO first, the camera can stay locked —
quit ZYRO first, then close the terminal.

## System Requirements
- Windows 10/11
- Webcam
- 4 GB RAM minimum
- Python 3.10+

## Project structure

```
.
├── main.py                  entry point
├── zyro/                    application package
│   ├── __init__.py
│   ├── config.py            every tunable value
│   ├── camera.py            webcam capture
│   ├── hand_tracker.py      MediaPipe HandLandmarker wrapper
│   ├── gesture_recognizer.py rule-based classification
│   ├── mouse_controller.py  mapping, filtering, clicks
│   ├── win_input.py         Win32 SendInput (mouse only)
│   ├── ui.py                HUD and overlays
│   └── virtual_keyboard.py  search keyboard
├── assets/
│   └── hand_landmarker.task MediaPipe model (Google, SHA-256 pinned)
├── docs/
│   └── ARCHITECTURE.md      pipeline, filters, state machines
├── .github/                 CI and issue templates
├── CONTRIBUTING.md
├── SECURITY.md
├── CHANGELOG.md
├── LICENSE
└── requirements.txt
```

## Troubleshooting

**`NO HAND DETECTED` banner.** The camera cannot see your hand. Move the
webcam so your hand fills a good part of the frame, add light, and keep the
hand roughly 40–70 cm from the lens. This is framing, not a code fault.

**The cursor jitters.** Lower `MOUSE_FILTER_MIN_CUTOFF` in `zyro/config.py`
(try `1.2`).

**The cursor feels laggy.** Raise `MOUSE_FILTER_BETA` (try `0.020`).

**Clicking is hard.** Lower `CLICK_STILL_WINDOW` (try `0.10`) or raise
`CLICK_STILL_SPEED`.

**Clicks happen when you do not want them.** Raise `CLICK_STILL_WINDOW` or
raise `PINCH_ACTION_CONFIDENCE`.

**Scrolling barely moves.** Increase `SCROLL_AMOUNT` or lower
`TWO_FINGER_SCROLL_STEP`.

## Architecture

The pipeline is webcam → MediaPipe landmarks → rule-based gesture → mouse
input, all in one process. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
for the data flow, the 1-euro cursor filter, the click-stillness rule, and
each gesture state machine.

- **Camera** — webcam capture and frame management
- **HandTracker** — MediaPipe hand landmark detection (21 points)
- **GestureRecognizer** — rule-based gesture classification
- **MouseController** — cursor mapping, filtering, click and scroll control
- **winInput** — native Win32 `SendInput` backend (cursor, buttons, wheel; mouse only)
- **VirtualKeyboard** — on-screen keyboard that builds a search query
- **UI** — HUD overlay rendering

## Contributing and security

- [CONTRIBUTING.md](CONTRIBUTING.md) — setup, ground rules, pull request checklist
- [SECURITY.md](SECURITY.md) — capabilities, trust boundaries, how to report a vulnerability

## License
MIT
