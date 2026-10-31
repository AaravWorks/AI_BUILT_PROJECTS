"""
Configuration module for ZYRO Hand-Gesture Control System.
All adjustable parameters are centralized here.
"""

# --- Camera Settings ---
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

# --- MediaPipe Hand Settings ---
# Detection thresholds. Measured against a real frame from this machine's
# camera: at 0.55/0.40 the hand was never detected, at 0.30/0.25 it is found
# reliably. The room is dim and the webcam sits below hand level, so the
# default thresholds see nothing.
HAND_DETECTION_CONFIDENCE = 0.30
HAND_TRACKING_CONFIDENCE = 0.25
MAX_NUM_HANDS = 1

# --- Mouse Settings ---
MOUSE_SENSITIVITY = 1.30        # Center-relative gain. 2.0 was unusable: it mapped
                                 # the camera's central half across the whole screen,
                                 # so buttons could not be aimed at.
MOUSE_PRECISION_SCALE = 0.35     # Extra gain reduction while precision mode is on
MOUSE_MIRROR_X = True            # Match the user's intuitive left/right hand movement
MOUSE_SMOOTHING = 0.30           # Legacy fixed damping, superseded by the filter below
MOUSE_BOUNDARY_MARGIN = 20       # Pixels from screen edge to keep cursor in bounds
MOUSE_MAX_OFFSET = 26            # Legacy per-frame cap, superseded by MOUSE_MAX_SPEED

# Cursor smoothing uses a One Euro filter: heavy damping while the hand is
# still (kills webcam jitter) and light damping while it moves (no lag).
# A fixed smoothing factor cannot do both, which is why the cursor felt
# sticky on slow moves and swam on fast ones.
#
# Tune these if the cursor feels jittery or sluggish:
#   - Lower MIN_CUTOFF = smoother at rest, but more lag on slow moves
#   - Higher BETA      = snappier transition when you start moving
#   - Higher D_CUTOFF  = smoother speed estimate, less "twitchy" feel
MOUSE_FILTER_MIN_CUTOFF = 0.8     # Hz. Heavy damping at rest for zero jitter
MOUSE_FILTER_BETA = 0.025         # Speed coupling. Follows hand quickly once moving
MOUSE_FILTER_D_CUTOFF = 1.5       # Hz. Smooths the speed estimate itself
MOUSE_FILTER_FIXED_DT = 1.0 / 30.0 # Use fixed 30fps dt so filter behavior is stable
MOUSE_MAX_SPEED = 3200           # Pixels per second cap so a bad landmark cannot teleport
MOUSE_DEADBAND_PX = 1.0          # Ignore sub-pixel moves; nothing changes on screen below this

# --- Click Settings ---
# Pinch is measured as thumb-index distance divided by hand size, so the
# gesture behaves the same whether the user is close to the camera or far.
# A fixed absolute threshold was why pinching became impossible to trigger.
PINCH_RATIO = 0.40              # Pinch distance as a fraction of hand size
PINCH_MIDDLE_GUARD = 0.02       # Middle finger must be this far from extended
PINCH_LABEL_CONFIDENCE = 0.34   # Lower bar just to report the PINCH gesture
PINCH_ACTION_CONFIDENCE = 0.42  # Minimum confidence for the click to fire
PINCH_COOLDOWN = 0.25           # Minimum release time between separate pinch pulses
PINCH_HOLD_FOR_DOUBLE = 0.45    # Only used when PINCH_ENABLE_DOUBLE_CLICK is True
PINCH_MAX_HOLD = 1.10           # Failsafe: fire a single click if release is never seen
PINCH_MIN_HOLD = 0.25            # Pinches shorter than this are tracker noise, not intent

# A held pinch used to fire a double-click on release. On a desktop that
# double-click lands on whatever icon or taskbar button the cursor happens
# to rest on, which is why applications opened by themselves. Deliberately
# disabled: a pinch now always produces exactly one single click.
PINCH_ENABLE_DOUBLE_CLICK = False

# Clicking while the hand is still travelling is the other half of the same
# problem: the cursor swept across a taskbar icon and the release fired a
# click there. A click now requires the pointer to have been slow for
# CLICK_STILL_WINDOW seconds first.
CLICK_REQUIRE_STILL = True
CLICK_STILL_SPEED = 320          # px/second below which the pointer counts as stopped
CLICK_STILL_WINDOW = 0.6         # Seconds of stillness required before a click is allowed
PINCH_MIN_HOLD = 0.25            # Pinches shorter than this are tracker noise, not intent
CLOSE_WINDOW_ACTIVATION_DELAY = 0.6  # Hold folded index+middle to arm close
CLOSE_WINDOW_CONFIRM_DELAY = 0.6     # Hold again to confirm window close
RIGHT_CLICK_THRESHOLD = 0.10    # Distance for index-middle finger separation
RIGHT_CLICK_COOLDOWN = 0.5      # Seconds between right clicks
MINIMIZE_COOLDOWN = 1.0              # Seconds between minimize actions (M key)

# --- Scroll Settings ---
SCROLL_TWO_FINGER_THRESHOLD = 0.08  # Min distance between index+middle for scroll detection
SCROLL_COOLDOWN = 0.12              # Seconds between scroll actions
SCROLL_AMOUNT = 5                   # Lines per scroll step
SCROLL_VERTICAL_SENSITIVITY = 0.8   # How fast vertical movement maps to scroll

# --- Palm Pause ---
PALM_OPEN_RATIO = 0.85            # Ratio of fingers extended to detect open palm
PALM_PAUSE_KEY = 'q'              # Keyboard key to toggle pause
PALM_ACTIVATION_DELAY = 0.8       # Hold open palm before pause/resume activates
RIGHT_CLICK_ACTIVATION_DELAY = 0.9
TWO_FINGER_SCROLL_THRESHOLD = 0.025
TWO_FINGER_SMOOTHING = 0.40         # EMA on finger height (rejects tracker jitter)
TWO_FINGER_COMMIT_ZONE = 0.012      # Dead zone around origin before scroll arms
TWO_FINGER_MOVE_DEADBAND = 0.002    # Ignore per-frame jitter below this
TWO_FINGER_SCROLL_DECAY = 0.82      # Leaky integrator: real motion builds up, jitter decays
TWO_FINGER_RESET_GRACE = 0.35       # Survive brief tracking dropouts
TWO_FINGER_SCROLL_STEP = 0.020      # Accumulated motion needed per scroll event
TWO_FINGER_MAX_STEPS_PER_FIRE = 3   # Cap a burst of scroll events

# --- Emergency Exit ---
EMERGENCY_EXIT_KEY = 'escape'     # Key to quit the application entirely

# --- Search Settings ---
SEARCH_GESTURE = 'open_palm_double'  # Gesture name to activate search
SEARCH_COOLDOWN = 2.0
# Opening a browser is the only way ZYRO can start another application, so
# it costs a second deliberate pinch. One stray pinch can no longer launch it.
SEARCH_REQUIRE_CONFIRM = True
SEARCH_CONFIRM_WINDOW = 3.0       # Seconds allowed between the two confirmation pinches

KEY_W = 36
KEY_H = 36
KEY_GAP = 4

# --- UI/HUD ---
HUD_FPS = True
HUD_GESTURE = True
HUD_ACTION = True
HUD_STATUS = True
HUD_CURSOR_INDICATOR = True

# Professional dark palette (BGR)
HUD_BG = (24, 22, 20)          # header / bar fill
HUD_PANEL = (32, 30, 28)       # info panel fill
HUD_ACCENT = (222, 176, 62)    # primary accent
HUD_ACCENT_SOFT = (128, 104, 44)
HUD_TEXT = (236, 238, 243)     # primary text
HUD_TEXT_DIM = (138, 142, 150) # secondary text
HUD_OK = (110, 202, 118)       # live / success
HUD_WARN = (86, 168, 240)      # caution
HUD_BAD = (96, 96, 226)        # error / danger
HUD_PANEL_ALPHA = 0.78         # panel opacity
HUD_BAR_ALPHA = 0.86           # header / footer opacity
HUD_RADIUS = 6                 # corner radius for rounded panels

FONT_SCALE = 0.7

# --- Gesture States ---
STATE_IDLE = "IDLE"
STATE_MOUSE_MOVE = "MOUSE_MOVE"
STATE_LEFT_CLICK = "LEFT_CLICK"
STATE_RIGHT_CLICK = "RIGHT_CLICK"
STATE_SCROLL_UP = "SCROLL_UP"
STATE_SCROLL_DOWN = "SCROLL_DOWN"
STATE_PAUSED = "PAUSED"
STATE_SEARCH = "SEARCH"
STATE_NAV_BACK = "NAV_BACK"
STATE_NAV_FORWARD = "NAV_FORWARD"