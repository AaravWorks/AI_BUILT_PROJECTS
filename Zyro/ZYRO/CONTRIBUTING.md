# Contributing

Thanks for taking a look at ZYRO.

## Setup

```powershell
git clone https://github.com/<owner>/<repo>.git
cd <repo>
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Windows 10/11 and a webcam are required. There is no headless mode: the
camera loop opens a preview window.

## Project layout

```
main.py                 entry point
zyro/                   application package
  config.py             all tunable values
  camera.py             webcam capture
  hand_tracker.py       MediaPipe wrapper
  gesture_recognizer.py rule-based gestures
  mouse_controller.py   mapping, filtering, clicks
  win_input.py          Win32 SendInput (mouse only)
  ui.py                 HUD rendering
  virtual_keyboard.py   search keyboard
assets/                 MediaPipe model
docs/                   architecture notes
```

## Ground rules

These are not style preferences; they are what keeps the project reviewable
and trustworthy:

- **No network code.** No sockets, HTTP clients, telemetry, or update checks.
- **No process execution.** No `subprocess`, `os.system`, `shell=True`.
- **No dynamic code.** No `eval`, `exec`, or `__import__`.
- **No keyboard synthesis.** The input backend is intentionally mouse-only.
- **Webcam frames stay in memory.** Never write, encode, or upload a frame.
- **No new permissions.** The app must keep running as a normal user.

If a feature genuinely needs to break one of these, open an issue first and
explain why.

## Before opening a pull request

```powershell
python -m compileall -q .
python -c "import zyro, zyro.config, zyro.camera, zyro.gesture_recognizer, zyro.hand_tracker, zyro.mouse_controller, zyro.ui, zyro.virtual_keyboard, zyro.win_input"
```

Then run the app and exercise the gesture you touched. If you changed
recognition or filtering, say what camera, lighting, and hand distance you
tested with — results vary a lot by setup.

## Style

- Match the surrounding code; it uses plain functions, small classes, and
  four-space indentation.
- Keep tuning values in `zyro/config.py` with a short comment explaining the
  effect, not just the number.
- Prefer a comment that explains *why* a threshold exists over one that
  restates the code.

## Commits and PRs

- One logical change per commit.
- Describe the user-visible effect in the PR body, plus anything you could
  not test.
- Do not attach compiled executables to a release.
