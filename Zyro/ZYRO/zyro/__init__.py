"""ZYRO - local hand-gesture control for Windows.

Everything in this package runs on the local machine. Webcam frames are
processed in memory and discarded; the only output is synthetic mouse
input through Win32 ``SendInput``. There is no network code, no process
execution, and no keyboard synthesis.
"""

__version__ = "1.0.0"
