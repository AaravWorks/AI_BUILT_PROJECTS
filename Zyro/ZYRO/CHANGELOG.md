# Changelog

All notable changes to this project.

## [1.0.0] - 2026-10-26

Initial public release.

### Added

- Hand tracking with MediaPipe HandLandmarker (21 landmarks, local CPU).
- Cursor control driven by the index fingertip.
- Pinch-to-click, two-finger scrolling, two-finger right click.
- Window minimise (`M`) and two-phase close gesture.
- Open-palm pause, precision mode, command reference.
- Optional search overlay with an on-screen keyboard.
- 1-euro cursor filter with speed clamping and tracking-loss reset.
- Click stillness requirement and minimum pinch duration.
- `SECURITY.md`, `CONTRIBUTING.md`, architecture notes, CI smoke test.

### Changed

- Input backend is native Win32 `SendInput`; `pyautogui` is not used.
- Wheel events are sent in real `WHEEL_DELTA` units so applications accept them.
- Project restructured into a `zyro/` package with a root `main.py` entry point.

### Removed

- Double-click-on-hold: it fired on whatever icon or taskbar button sat under
  the cursor, which made applications open unexpectedly.
- Keyboard synthesis from the input backend. The app cannot type into other
  applications.
- The `sync_source.py` source-copy helper.
