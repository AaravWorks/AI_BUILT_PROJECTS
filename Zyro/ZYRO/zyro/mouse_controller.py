"""
Mouse controller module.
Handles cursor movement, clicks, scrolling and window control.

Input goes through the native Win32 backend in `win_input` rather than
pyautogui, which is both a frequent antivirus false positive and broken
for scrolling on Windows.
"""
import math
import time

import pygetwindow

from . import config
from . import win_input


class _OneEuroFilter:
    """1-euro filter: adaptive low-pass for noisy pointer input.

    Small movements are damped hard so webcam jitter never reaches the
    screen; large movements are followed closely so the cursor does not
    feel laggy. A fixed smoothing factor cannot do both - that trade-off
    is why the cursor felt sticky on slow moves and swam on fast ones.
    """

    def __init__(self, min_cutoff, beta, d_cutoff):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)
        self._x = None
        self._dx = 0.0

    def reset(self):
        self._x = None
        self._dx = 0.0

    @staticmethod
    def _alpha(cutoff, dt):
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, value, dt):
        if self._x is None:
            self._x = value
            return value
        dt = max(dt, 1e-3)
        derivative = (value - self._x) / dt
        a_d = self._alpha(self.d_cutoff, dt)
        self._dx = a_d * derivative + (1.0 - a_d) * self._dx
        cutoff = self.min_cutoff + self.beta * abs(self._dx)
        a = self._alpha(cutoff, dt)
        self._x = a * value + (1.0 - a) * self._x
        return self._x


class MouseController:
    def __init__(self):
        self.screen_width, self.screen_height = win_input.screen_size()
        self.last_x = self.screen_width // 2
        self.last_y = self.screen_height // 2
        self.smoothed_x = self.last_x
        self.smoothed_y = self.last_y
        self.last_click_time = 0.0
        self.last_right_click_time = 0.0
        self.last_scroll_time = 0.0
        self.last_minimize_time = 0.0
        self.last_two_finger_y = None
        self.is_paused = False

        self._filter_x = _OneEuroFilter(
            config.MOUSE_FILTER_MIN_CUTOFF,
            config.MOUSE_FILTER_BETA,
            config.MOUSE_FILTER_D_CUTOFF,
        )
        self._filter_y = _OneEuroFilter(
            config.MOUSE_FILTER_MIN_CUTOFF,
            config.MOUSE_FILTER_BETA,
            config.MOUSE_FILTER_D_CUTOFF,
        )
        self.last_move_time = 0.0
        self.last_fast_move_time = 0.0
        self.last_click_block = None

    def update_screen_size(self):
        """Update screen dimensions (handles resolution changes)."""
        try:
            self.screen_width, self.screen_height = win_input.screen_size()
            self.reset_motion()
        except Exception:
            pass

    @staticmethod
    def map_normalized(norm_x, norm_y, precision=False):
        """Apply center-relative gain and optional horizontal mirroring."""
        gain = config.MOUSE_SENSITIVITY
        if precision:
            gain *= config.MOUSE_PRECISION_SCALE
        scaled_x = 0.5 + (norm_x - 0.5) * gain
        scaled_y = 0.5 + (norm_y - 0.5) * gain
        scaled_x = max(0.0, min(1.0, scaled_x))
        scaled_y = max(0.0, min(1.0, scaled_y))
        if config.MOUSE_MIRROR_X:
            scaled_x = 1.0 - scaled_x
        return scaled_x, scaled_y

    def reset_motion(self):
        """Forget smoothing history, e.g. when tracking is lost.

        Without this the filter interpolates from the position the hand
        occupied before the dropout, so the cursor sweeps across the screen
        when tracking comes back - straight over icons and taskbar buttons.
        """
        self._filter_x.reset()
        self._filter_y.reset()
        self.last_move_time = 0.0
        self.smoothed_x = float(self.last_x)
        self.smoothed_y = float(self.last_y)

    def is_steady(self):
        """True once the pointer has been slow long enough to accept a click."""
        if not config.CLICK_REQUIRE_STILL:
            return True
        return (time.time() - self.last_fast_move_time) >= config.CLICK_STILL_WINDOW

    @property
    def click_armed(self):
        """True if a pinch release would fire a click right now."""
        return self.is_steady() and (
            time.time() - self.last_click_time >= config.PINCH_COOLDOWN
        )

    def move_cursor(self, norm_x, norm_y, smoothing=None, precision=False):
        """
        Map normalized coordinates (0-1) to screen position.

        `smoothing` is accepted for backwards compatibility and ignored;
        damping now comes from the One Euro filter.
        """
        now = time.time()
        dt = config.MOUSE_FILTER_FIXED_DT
        self.last_move_time = now

        mapped_x, mapped_y = self.map_normalized(norm_x, norm_y, precision)
        target_x = mapped_x * self.screen_width
        target_y = mapped_y * self.screen_height

        filtered_x = self._filter_x(target_x, dt)
        filtered_y = self._filter_y(target_y, dt)

        # Clamp how far the pointer may travel in one frame so a single bad
        # landmark cannot throw it across the screen.
        dx = filtered_x - self.smoothed_x
        dy = filtered_y - self.smoothed_y
        distance = math.hypot(dx, dy)
        max_step = config.MOUSE_MAX_SPEED * dt
        if max_step > 0 and distance > max_step:
            scale = max_step / distance
            filtered_x = self.smoothed_x + dx * scale
            filtered_y = self.smoothed_y + dy * scale
            distance = max_step

        self.smoothed_x = filtered_x
        self.smoothed_y = filtered_y

        # Remember when the pointer last moved quickly. Clicks are refused
        # until this has been quiet for CLICK_STILL_WINDOW seconds.
        speed = distance / dt
        if speed > config.CLICK_STILL_SPEED:
            self.last_fast_move_time = now

        new_x = int(round(filtered_x))
        new_y = int(round(filtered_y))
        margin = config.MOUSE_BOUNDARY_MARGIN
        new_x = max(margin, min(self.screen_width - margin, new_x))
        new_y = max(margin, min(self.screen_height - margin, new_y))

        # moveTo is a blocking OS call; skip it when the position is
        # effectively unchanged.
        if (abs(new_x - self.last_x) >= config.MOUSE_DEADBAND_PX
                or abs(new_y - self.last_y) >= config.MOUSE_DEADBAND_PX):
            self.last_x = new_x
            self.last_y = new_y
            try:
                if not self.is_paused:
                    win_input.move_to(new_x, new_y)
            except Exception:
                pass

        return self.last_x, self.last_y

    def left_click(self):
        """Perform a left click, but only if the pointer is settled.

        Refusing to click mid-movement is what stops icons and taskbar
        buttons from activating while the cursor merely passes over them.
        """
        now = time.time()
        if now - self.last_click_time < config.PINCH_COOLDOWN:
            self.last_click_block = "COOLDOWN"
            return False
        if not self.is_steady():
            self.last_click_block = "MOVING"
            return False
        try:
            win_input.left_click()
            self.last_click_time = now
            self.last_click_block = None
            return True
        except Exception:
            self.last_click_block = "ERROR"
            return False

    def double_click(self):
        """Perform a native double-click with the same cooldown and guard."""
        now = time.time()
        if now - self.last_click_time < config.PINCH_COOLDOWN:
            self.last_click_block = "COOLDOWN"
            return False
        if not self.is_steady():
            self.last_click_block = "MOVING"
            return False
        try:
            win_input.double_click()
            self.last_click_time = now
            self.last_click_block = None
            return True
        except Exception:
            self.last_click_block = "ERROR"
            return False

    def _get_window_under_cursor(self):
        try:
            pos = win_input.cursor_position()
            if pos is None:
                return None
            windows = pygetwindow.getWindowsAt(pos[0], pos[1])
        except Exception:
            return None

        for window in windows:
            try:
                title = (window.title or "").strip()
                if not title or title.startswith("ZYRO - Hand Gesture Control"):
                    continue
                if window.width <= 0 or window.height <= 0:
                    continue
                return window
            except Exception:
                continue
        return None

    def minimize_window_under_cursor(self):
        now = time.time()
        if now - self.last_minimize_time < config.MINIMIZE_COOLDOWN:
            return None
        window = self._get_window_under_cursor()
        if window is None:
            return None
        try:
            title = (window.title or "Window").strip()
            window.minimize()
            self.last_minimize_time = now
            return title
        except Exception:
            return None

    def close_window_under_cursor(self):
        window = self._get_window_under_cursor()
        if window is None:
            return None
        try:
            title = (window.title or "Window").strip()
            window.close()
            return title
        except Exception:
            return None

    def right_click(self):
        """Perform a right click with cooldown."""
        now = time.time()
        if now - self.last_right_click_time < config.RIGHT_CLICK_COOLDOWN:
            return False
        try:
            win_input.right_click()
            self.last_right_click_time = now
            return True
        except Exception:
            return False

    def _send_wheel_notches(self, notches):
        """Send real wheel notches at the current cursor position.

        Windows counts wheel deltas in units of 120, so a raw click count
        would be discarded by every application.
        """
        return win_input.wheel(notches)

    def _post_wheel_notches(self, notches):
        """Fallback: post wheel messages to the window under the cursor."""
        return win_input.wheel_to_window(notches)

    def scroll(self, direction):
        """Scroll up or down with cooldown.
        direction: 'up' or 'down'
        Returns True if scroll was performed.
        """
        now = time.time()
        if now - self.last_scroll_time < config.SCROLL_COOLDOWN:
            return False

        notches = config.SCROLL_AMOUNT if direction == 'up' else -config.SCROLL_AMOUNT
        try:
            delivered = self._send_wheel_notches(notches)
            if delivered == 0:
                delivered = self._post_wheel_notches(notches)
            self.last_scroll_time = now
            return delivered > 0
        except Exception:
            return False

    def set_pause(self, paused):
        """Set pause state for mouse operations."""
        self.is_paused = paused

    def get_position(self):
        """Get current mouse position."""
        try:
            return win_input.cursor_position() or (self.last_x, self.last_y)
        except Exception:
            return (self.last_x, self.last_y)
