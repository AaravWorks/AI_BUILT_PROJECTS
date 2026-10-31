"""
ZYRO - Hand-Gesture Control System for Windows

Pipeline: Webcam -> Hand Detection -> Landmarks -> Gesture Recognition -> Action -> Computer Control

Phase 1-2: Camera + Hand detection + Mouse movement
Phase 3:   Pinch -> Native Double Click
Phase 4:   Double Pinch / Folded Fingers -> Window Controls
Phase 5:   Search + Virtual Keyboard
Phase 6:   Navigation + Instruction interface
Phase 7:   Futuristic UI

Keyboard shortcuts (via OpenCV window):
  ESC    - Quit
  Q      - Toggle pause
  N      - Toggle navigation/instruction mode
  S      - Toggle search
"""

import time
import webbrowser
from urllib.parse import quote_plus

import cv2

from zyro import config
from zyro.camera import Camera
from zyro.hand_tracker import HandTracker
from zyro.gesture_recognizer import GestureRecognizer
from zyro.mouse_controller import MouseController
from zyro.virtual_keyboard import VirtualKeyboard
from zyro.ui import draw_hud, draw_search_interface, draw_nav_interface


class ZYROApp:
    def __init__(self):
        # Core modules
        self.camera = Camera()
        self.tracker = HandTracker()
        self.recognizer = GestureRecognizer()
        self.mouse = MouseController()
        self.keyboard = VirtualKeyboard()

        # State
        self.running = True
        self.is_paused = False
        self.current_gesture = "INIT"
        self.current_action = "WAITING"
        self.fps = 0
        self.frame_count = 0
        self.start_time = time.time()

        # Gesture tracking state
        self.last_pinch_time = 0
        self.pinch_started_at = None
        self.pinch_fired = False
        self.is_precision = False
        self.last_palm_time = 0
        self.last_two_finger_y = None
        self.search_active = False
        self.search_text = ""
        self.nav_mode = False
        self.cursor_frame = (
            config.CAMERA_WIDTH // 2,
            config.CAMERA_HEIGHT // 2,
        )
        self.hovered_key = None
        self.pending_search_query = None
        self.pending_search_time = 0.0

        self.pinch_latched = False
        self.interface_pinch_latched = False
        self.palm_started_at = None
        self.palm_fired = False
        self.two_finger_started_at = None
        self.two_finger_start_y = None
        self.two_finger_scroll_anchor_y = None
        self.two_finger_mode = None
        self.two_finger_click_fired = False
        self.two_finger_scroll_accum = 0.0
        self.two_finger_prev_y = None
        self.two_finger_smooth_y = None
        self.two_finger_origin_y = None
        self.two_finger_last_seen = 0.0
        self.close_window_started_at = None
        self.close_window_fired = False
        self.close_window_confirm_started_at = None
        self.close_window_confirmed = False

        self.frame_w = config.CAMERA_WIDTH
        self.frame_h = config.CAMERA_HEIGHT
        self.last_loop_error = None
        self.last_loop_error_time = 0.0

    def initialize(self):
        """Initialize all modules and validate dependencies."""
        print("[ZYRO] Initializing...")

        # Check camera
        if not self.camera.open(0):
            print("[ERROR] Could not open webcam!")
            return False

        # Check tracker
        if self.tracker.hands is None:
            print("[ERROR] MediaPipe failed to initialize!")
            self.camera.release()
            return False

        print("[ZYRO] System initialized successfully.")
        print("[ZYRO] Press ESC to quit, Q to pause/resume.")
        print("[ZYRO] Pinch tap=click (single only), two fingers=scroll/right-click")
        print("[ZYRO] I+M folded=close window, palm=pause")
        print("[ZYRO] Keys: M=minimize  P=precision  S=search  N=commands  Q=pause  ESC=quit")
        return True

    def update_fps(self):
        """Calculate and update FPS counter."""
        self.frame_count += 1
        now = time.time()
        elapsed = now - self.start_time
        if elapsed > 0:
            self.fps = self.frame_count / elapsed

    def process_frame(self, frame):
        """Process a single frame through the entire pipeline."""
        if frame is None:
            return None, None

        # Hand tracking
        self.tracker.process(frame)
        landmarks = self.tracker.get_landmarks()

        # Draw landmarks on frame
        frame = self.tracker.draw_landmarks(frame)

        if landmarks is not None:
            # Gesture recognition
            gesture, confidence = self.recognizer.recognize(landmarks, self.last_two_finger_y)
            self.current_gesture = gesture

            # Get index finger position for mouse control
            index_pos = self.tracker.get_index_finger_tip()

            if (
                index_pos is not None
                and not self.is_paused
                and not self.search_active
                and gesture in ("POINTING", "PINCH")
            ):
                norm_x, norm_y = index_pos[0], index_pos[1]
                self.mouse.move_cursor(norm_x, norm_y, precision=self.is_precision)
                mapped_x, mapped_y = self.mouse.map_normalized(norm_x, norm_y)
                self.cursor_frame = (int(mapped_x * self.frame_w), int(mapped_y * self.frame_h))

            self.process_gesture_actions(landmarks, gesture, confidence)
        else:
            self.pinch_latched = False
            self.interface_pinch_latched = False
            self._reset_palm_gesture()
            self._maybe_reset_two_finger_gesture(time.time())
            self._reset_close_window_gesture()
            self.mouse.reset_motion()
            self.current_gesture = "NO_HAND"
            self.current_action = "NO_HAND_DETECTED"

        self.update_fps()
        return self.cursor_frame

    def _handle_palm_gesture(self, now, on_activation):
        if self.palm_started_at is None:
            self.palm_started_at = now
            self.palm_fired = False
            return
        if not self.palm_fired and now - self.palm_started_at >= config.PALM_ACTIVATION_DELAY:
            on_activation()
            self.palm_fired = True

    def _reset_palm_gesture(self):
        self.palm_started_at = None
        self.palm_fired = False

    def _reset_two_finger_gesture(self):
        self.two_finger_started_at = None
        self.two_finger_start_y = None
        self.two_finger_scroll_anchor_y = None
        self.two_finger_mode = None
        self.two_finger_click_fired = False
        self.two_finger_scroll_accum = 0.0
        self.two_finger_prev_y = None
        self.two_finger_smooth_y = None
        self.two_finger_origin_y = None
        self.last_two_finger_y = None

    def _maybe_reset_two_finger_gesture(self, now):
        """Reset the two-finger state machine, but tolerate brief dropouts.

        Tracking flickers constantly (especially when the hand rises toward
        the top of the frame), and a hard reset on every dropped frame wiped
        the scroll progress - which is why scrolling up barely worked.
        """
        if self.two_finger_started_at is None:
            return
        if now - self.two_finger_last_seen >= config.TWO_FINGER_RESET_GRACE:
            self._reset_two_finger_gesture()

    def _reset_close_window_gesture(self):
        self.close_window_started_at = None
        self.close_window_fired = False
        self.close_window_confirm_started_at = None
        self.close_window_confirmed = False

    def process_gesture_actions(self, landmarks, gesture, confidence):
        now = time.time()

        if gesture != "PINCH":
            self.pinch_latched = False
        if gesture != "PALM_OPEN":
            self._reset_palm_gesture()
        if gesture != "TWO_FINGER":
            self._maybe_reset_two_finger_gesture(now)
        if gesture != "CLOSE_WINDOW":
            self._reset_close_window_gesture()

        if self.search_active:
            if gesture == "PALM_OPEN":
                self._handle_palm_gesture(
                    now,
                    self._close_active_interface,
                )
            else:
                self.current_action = "INTERFACE_ACTIVE"
            return

        if gesture == "PALM_OPEN":
            self._handle_palm_gesture(now, self._toggle_pause)
            return

        if self.is_paused:
            self.current_action = "GESTURE CONTROL PAUSED"
            return

        if gesture == "CLOSE_WINDOW" and confidence >= 0.8:
            # Two-phase close: arm (0.6s) then confirm (0.6s). Requiring a
            # second deliberate hold prevents accidental window destruction.
            if self.close_window_confirm_started_at is None:
                # Phase 1: arm the close
                if self.close_window_started_at is None:
                    self.close_window_started_at = now
                    self.close_window_fired = False
                if not self.close_window_fired and now - self.close_window_started_at >= config.CLOSE_WINDOW_ACTIVATION_DELAY:
                    self.close_window_confirm_started_at = now
                    self.close_window_fired = True  # armed
                    self.current_action = "CLOSE WINDOW? HOLD TO CONFIRM"
                elif not self.close_window_fired:
                    remaining = max(0.0, config.CLOSE_WINDOW_ACTIVATION_DELAY - (now - self.close_window_started_at))
                    self.current_action = f"HOLD TO CLOSE WINDOW {remaining:.1f}s"
            else:
                # Phase 2: confirm
                if now - self.close_window_confirm_started_at >= config.CLOSE_WINDOW_CONFIRM_DELAY:
                    title = self.mouse.close_window_under_cursor()
                    self.close_window_confirmed = True
                    self.close_window_confirm_started_at = None
                    self.close_window_started_at = None
                    self.current_action = f"WINDOW CLOSED: {title}" if title else "NO WINDOW TO CLOSE"
                else:
                    remaining = max(0.0, config.CLOSE_WINDOW_CONFIRM_DELAY - (now - self.close_window_confirm_started_at))
                    self.current_action = f"CONFIRM CLOSE {remaining:.1f}s"
            return

        if gesture == "PINCH" and confidence >= config.PINCH_ACTION_CONFIDENCE:
            # A pinch now resolves to at most one click, decided on release.
            # Double-click-on-hold was removed: on a desktop it fired on
            # whatever icon or taskbar button sat under the cursor, which is
            # why applications opened by themselves.
            if not self.pinch_latched:
                if self.pinch_started_at is None:
                    self.pinch_started_at = now
                    self.pinch_fired = False
                elif not self.pinch_fired:
                    if now - self.pinch_started_at > config.PINCH_MAX_HOLD:
                        # Failsafe: tracking dropped before the release was
                        # seen. Retry until the pointer is settled enough.
                        if self.mouse.left_click():
                            self.pinch_fired = True
                            self.pinch_latched = True
                            self.pinch_started_at = None
                            self.current_action = "CLICK (failsafe)"
                        else:
                            self.current_action = self._click_block_text()
                    else:
                        self.current_action = "PINCH HELD"
            return

        # Pinch released: fire a single click if the pinch was deliberate.
        if self.pinch_started_at is not None and not self.pinch_fired:
            held = now - self.pinch_started_at
            self.pinch_started_at = None
            self.pinch_fired = False
            if held < config.PINCH_MIN_HOLD:
                self.current_action = "PINCH IGNORED (TOO SHORT)"
                return
            if now - self.last_pinch_time < config.PINCH_COOLDOWN:
                self.current_action = "CLICK RATE LIMITED"
                return
            if (config.PINCH_ENABLE_DOUBLE_CLICK
                    and held >= config.PINCH_HOLD_FOR_DOUBLE):
                ok = self.mouse.double_click()
            else:
                ok = self.mouse.left_click()
            if ok:
                self.last_pinch_time = now
                self.current_action = "DOUBLE CLICK" if (
                    config.PINCH_ENABLE_DOUBLE_CLICK
                    and held >= config.PINCH_HOLD_FOR_DOUBLE
                ) else "CLICK"
            else:
                self.current_action = self._click_block_text()
            return

        if gesture == "TWO_FINGER" and confidence >= 0.7:
            average_y = (landmarks[8][1] + landmarks[12][1]) / 2.0
            self.last_two_finger_y = average_y
            self.two_finger_last_seen = now

            if self.two_finger_started_at is None:
                self.two_finger_started_at = now
                self.two_finger_start_y = average_y
                self.two_finger_scroll_anchor_y = average_y
                self.two_finger_mode = "pending"
                self.two_finger_click_fired = False
                self.two_finger_scroll_accum = 0.0
                self.two_finger_prev_y = None
                self.two_finger_smooth_y = average_y
                self.two_finger_origin_y = average_y
                return

            # 1) Smooth the finger height. Tracker jitter is large relative
            #    to the scroll step, so the raw signal is unusable.
            if self.two_finger_smooth_y is None:
                self.two_finger_smooth_y = average_y
            else:
                self.two_finger_smooth_y += (
                    average_y - self.two_finger_smooth_y
                ) * config.TWO_FINGER_SMOOTHING
            smooth_y = self.two_finger_smooth_y

            # 2) Commit dead zone. Motion hovering around the origin never
            #    enters the integrator, so an idle hand cannot drift-scroll.
            if abs(smooth_y - self.two_finger_origin_y) >= config.TWO_FINGER_COMMIT_ZONE:
                if self.two_finger_prev_y is not None:
                    delta = smooth_y - self.two_finger_prev_y
                    if abs(delta) >= config.TWO_FINGER_MOVE_DEADBAND:
                        # 3) Leaky integrator. A plain sum either starves
                        #    slow scrolling or random-walks into phantom
                        #    scrolling; decaying lets deliberate movement
                        #    accumulate while noise falls back to zero.
                        self.two_finger_scroll_accum = (
                            self.two_finger_scroll_accum
                            * config.TWO_FINGER_SCROLL_DECAY
                            + delta
                        )
            self.two_finger_prev_y = smooth_y

            if abs(self.two_finger_scroll_accum) >= config.TWO_FINGER_SCROLL_STEP:
                if now - self.mouse.last_scroll_time >= config.SCROLL_COOLDOWN:
                    direction = "up" if self.two_finger_scroll_accum < 0 else "down"
                    if self.mouse.scroll(direction):
                        steps = int(
                            abs(self.two_finger_scroll_accum)
                            / config.TWO_FINGER_SCROLL_STEP
                        )
                        steps = min(steps, config.TWO_FINGER_MAX_STEPS_PER_FIRE)
                        spent = steps * config.TWO_FINGER_SCROLL_STEP
                        self.two_finger_scroll_accum -= (
                            spent if self.two_finger_scroll_accum > 0 else -spent
                        )
                        self.two_finger_mode = "scroll"
                        self.current_action = "SCROLL_UP" if direction == "up" else "SCROLL_DOWN"
                        # Re-arm the dead zone at the new position so the
                        # gesture can keep going without lifting your hand.
                        self.two_finger_origin_y = average_y
                        self.two_finger_scroll_accum = 0.0
                self.two_finger_scroll_anchor_y = average_y

            if self.two_finger_mode != "scroll":
                if (
                    not self.two_finger_click_fired
                    and now - self.two_finger_started_at >= config.RIGHT_CLICK_ACTIVATION_DELAY
                ):
                    if self.mouse.right_click():
                        self.two_finger_click_fired = True
                        self.current_action = "RIGHT_CLICK"
                else:
                    self.current_action = "TWO_FINGER READY"
            return

        if gesture == "POINTING":
            self.current_action = "MOUSE_MOVE"
        elif gesture == "FIST":
            self.current_action = "READY"

    def _toggle_pause(self):
        self.is_paused = not self.is_paused
        self.recognizer.is_paused = self.is_paused
        self.mouse.set_pause(self.is_paused)
        self.current_action = "PAUSED" if self.is_paused else "RESUMED"

    def _click_block_text(self):
        """Human-readable reason the last click was refused."""
        reason = getattr(self.mouse, "last_click_block", None)
        if reason == "MOVING":
            return "CLICK BLOCKED: HOLD STILL"
        if reason == "COOLDOWN":
            return "CLICK RATE LIMITED"
        return "CLICK BLOCKED"

    def _close_active_interface(self):
        if self.search_active:
            self.search_active = False
            self.keyboard.close()
            self.pending_search_query = None
            self.current_action = "SEARCH_CLOSED"
        self.interface_pinch_latched = False

    def handle_search_input(self):
        if not self.search_active:
            self.interface_pinch_latched = False
            return

        landmarks = self.tracker.get_landmarks()
        index_pos = self.tracker.get_index_finger_tip()
        if landmarks is None or index_pos is None:
            self.interface_pinch_latched = False
            self.hovered_key = None
            self.keyboard.hovered_key = None
            return

        mapped_x, mapped_y = self.mouse.map_normalized(index_pos[0], index_pos[1])
        frame_x = int(mapped_x * self.frame_w)
        frame_y = int(mapped_y * self.frame_h)
        self.hovered_key = self.keyboard.get_key_at_position(frame_x, frame_y)
        self.keyboard.hovered_key = self.hovered_key
        is_pinch, confidence = self.recognizer.is_pinch_gesture(landmarks)

        if not is_pinch:
            self.interface_pinch_latched = False
            return
        if confidence < 0.5 or self.interface_pinch_latched or self.hovered_key is None:
            return

        now = time.time()
        if now - self.last_pinch_time < config.PINCH_COOLDOWN:
            return

        self.interface_pinch_latched = True
        self.last_pinch_time = now
        key = self.hovered_key

        if key in ("SEARCH", "Enter"):
            query = self.keyboard.text.strip()
            if not query:
                self.current_action = "ENTER A SEARCH QUERY"
                return
            # Opening a browser is the only way ZYRO can start another
            # application. Requiring a second pinch means a single stray
            # pinch can never launch it.
            confirmed = (
                not config.SEARCH_REQUIRE_CONFIRM
                or (
                    self.pending_search_query == query
                    and now - self.pending_search_time
                    <= config.SEARCH_CONFIRM_WINDOW
                )
            )
            if not confirmed:
                self.pending_search_query = query
                self.pending_search_time = now
                self.current_action = "PINCH AGAIN TO OPEN SEARCH"
                return
            self.pending_search_query = None
            self.search_active = False
            self.keyboard.close()
            webbrowser.open(f"https://www.google.com/search?q={quote_plus(query)}")
            self.current_action = f"SEARCHED: {query}"
            return

        self.keyboard.append_key(key)
        self.search_text = self.keyboard.text
        self.current_action = f"TYPED: {key}"

    def run(self):
        if not self.initialize():
            return

        print("[ZYRO] Starting main loop...")
        camera_failures = 0

        while self.running:
            try:
                frame = self.camera.read()
                if frame is None:
                    camera_failures += 1
                    if camera_failures % 30 == 0:
                        print("[WARNING] Waiting for webcam frames...")
                    time.sleep(0.03)
                    continue
                camera_failures = 0

                cursor_x, cursor_y = self.process_frame(frame)
                self.handle_search_input()

                if self.search_active:
                    frame = draw_search_interface(frame, self.search_text)
                elif self.nav_mode:
                    frame = draw_nav_interface(frame, self.current_gesture)
                else:
                    frame = draw_hud(
                        frame,
                        gesture=self.current_gesture,
                        action=self.current_action,
                        is_paused=self.is_paused,
                        fps=self.fps,
                        cursor_x=cursor_x,
                        cursor_y=cursor_y,
                        click_armed=self.mouse.click_armed,
                    )

                if self.keyboard.is_open:
                    frame = self.keyboard.draw_keyboard(frame)

                cv2.imshow("ZYRO - Hand Gesture Control", frame)
                key = cv2.waitKey(1) & 0xFF

                # ESC quits. Clicking the window's X button also quits:
                # getWindowProperty returns 0 (hidden) or -1 (destroyed /
                # error) once the window is closed. Without this check the
                # loop would keep running after the X button, so closing one
                # instance looked like "it restarted" when another instance
                # was still alive.
                try:
                    if cv2.getWindowProperty(
                        "ZYRO - Hand Gesture Control", cv2.WND_PROP_VISIBLE
                    ) < 1:
                        break
                except Exception:
                    pass

                if key == 27:
                    break
                if key in (ord("q"), ord("Q")):
                    self._toggle_pause()
                if key in (ord("n"), ord("N")):
                    self.nav_mode = not self.nav_mode
                    self.current_action = "NAV_MODE" if self.nav_mode else "READY"
                if key in (ord("m"), ord("M")):
                    title = self.mouse.minimize_window_under_cursor()
                    self.current_action = f"MINIMIZED: {title}" if title else "NO WINDOW TO MINIMIZE"
                if key in (ord("p"), ord("P")):
                    self.is_precision = not self.is_precision
                    self.current_action = "PRECISION ON" if self.is_precision else "PRECISION OFF"
                if key in (ord("s"), ord("S")):
                    self.search_active = not self.search_active
                    if self.search_active:
                        self.keyboard.open()
                        self.current_action = "SEARCH"
                    else:
                        self.keyboard.close()
                        self.current_action = "SEARCH_CLOSED"

            except Exception as exc:
                now = time.time()
                error_text = f"{type(exc).__name__}: {exc}"
                if error_text != self.last_loop_error or now - self.last_loop_error_time >= 5:
                    print(f"[ERROR] Main loop: {error_text}")
                    self.last_loop_error = error_text
                    self.last_loop_error_time = now
                time.sleep(0.03)

        self.cleanup()

    def cleanup(self):
        """Clean up all resources."""
        print("\n[ZYRO] Shutting down...")
        self.camera.release()
        self.tracker.close()
        cv2.destroyAllWindows()
        print("[ZYRO] Goodbye!")


def main():
    """Entry point for the application."""
    app = ZYROApp()
    app.run()


if __name__ == "__main__":
    main()
