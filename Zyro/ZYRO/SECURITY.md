# Security Policy

## Reporting a vulnerability

Please do **not** open a public issue for a security problem.

Use GitHub's private reporting flow: **Security** tab → **Report a
vulnerability** (Security Advisories). If that is unavailable, contact us directly through the address on their GitHub profile.

Include the affected file, a description of the impact, and steps to
reproduce. Please allow reasonable time for a fix before disclosure.

## Supported versions

The `main` branch is the only supported version.

## What ZYRO can do

ZYRO runs as your user account and synthesises **mouse input** through the
Win32 `SendInput` API: cursor movement, left/right click, and wheel scroll.
It can also minimise or close the window currently under the cursor when you
perform the matching gesture.

## What ZYRO cannot do

- Open a network connection, listen on a port, or send data anywhere
- Execute shell commands or start processes
- Synthesise keyboard input
- Read or write files outside its own folder
- Record, store, or transmit webcam frames
- Request administrator privileges

Webcam frames are processed in memory by MediaPipe and discarded. The only
file the application reads is `assets/hand_landmarker.task`.

## Trust boundaries

- **Local user only.** ZYRO has no authentication because it has no remote
  interface. Anyone who can use your unlocked desktop can already control
  the mouse without ZYRO.
- **Camera input is untrusted.** Gesture recognition is heuristic; a
  misclassified gesture can cause an unintended click. Cooldowns, a
  stillness requirement, and a two-phase window close are the mitigations.
- **Dependencies are third-party.** `opencv-python`, `mediapipe`, `numpy`,
  and `pygetwindow` run with your privileges. Pin versions for reproducible
  builds and audit them with `pip-audit` if that matters to you.
- **The model file is a binary.** `assets/hand_landmarker.task` is Google's
  published MediaPipe model, committed for offline use. Its SHA-256 is
  `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`,
  which matches the file served from
  `storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task`.

## Audit notes

The source was reviewed manually: every import, every Win32 call, and every
file write was enumerated from the AST rather than inferred. At the time of
that review the project contained no `eval`/`exec`/`subprocess`/`os.system`,
no network library, no persistence mechanism, no credential access, and no
webcam exfiltration. The running process held zero TCP and UDP sockets.

This is a point-in-time review of a small codebase, not a guarantee. It does
not cover the source of the dependencies or how antivirus engines classify
the application.

## Known limitations

- Recognition quality depends heavily on camera framing and lighting. A hand
  outside the frame produces no input at all.
- The application is not code-signed. Antivirus heuristics sometimes flag
  programs that synthesise input; source releases are unaffected, prebuilt
  binaries may be.
- No automated dependency vulnerability scanning is configured.
