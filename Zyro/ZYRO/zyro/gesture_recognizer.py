"""
Gesture recognition module.
Uses landmark positions, distances, and angles to classify gestures.
No AI model - pure rule-based recognition.
"""
import numpy as np

from . import config


# Landmark indices
THUMB_TIP = 4
INDEX_TIP = 8
MIDDLE_TIP = 12
RING_TIP = 16
PINKY_TIP = 20
WRIST = 0
INDEX_PIP = 6
MIDDLE_MCP = 9
MIDDLE_PIP = 10
RING_PIP = 14
PINKY_PIP = 18
THUMB_IP = 3


class GestureRecognizer:
    def __init__(self):
        self.current_gesture = "UNKNOWN"
        self.gesture_confidence = 0.0
        self.is_paused = False
        self.pause_toggle_time = 0

    def count_extended_fingers(self, landmarks):
        """Count how many fingers are extended based on landmark positions.
        A finger is considered extended if its tip is farther from wrist
        than its PIP joint (in y-coordinate) AND tip is farther than a threshold.
        """
        if landmarks is None:
            return 0

        extended = 0
        wrist_y = landmarks[WRIST][1]

        # Index finger: tip y < pip y (above in image = extended)
        if landmarks[INDEX_TIP][1] < landmarks[INDEX_PIP][1]:
            extended += 1

        # Middle finger
        if landmarks[MIDDLE_TIP][1] < landmarks[MIDDLE_PIP][1]:
            extended += 1

        # Ring finger
        if len(landmarks) > 14:
            if landmarks[RING_TIP][1] < landmarks[14][1]:
                extended += 1

        # Pinky
        if len(landmarks) > 18:
            if landmarks[PINKY_TIP][1] < landmarks[18][1]:
                extended += 1

        # Thumb: check if tip is far from index finger MCP (landmark 5)
        # Compare x-distance
        if len(landmarks) > 5:
            thumb_dist_x = abs(landmarks[THUMB_TIP][0] - landmarks[5][0])
            thumb_dist_y = abs(landmarks[THUMB_TIP][1] - landmarks[5][1])
            if thumb_dist_x > 0.05 or thumb_dist_y > 0.05:
                # More precise: if thumb is spread out from hand
                index_mcp_x = landmarks[5][0]
                if landmarks[THUMB_TIP][0] > index_mcp_x or landmarks[THUMB_TIP][0] < index_mcp_x - 0.03:
                    if abs(landmarks[THUMB_TIP][1] - landmarks[5][1]) > 0.05:
                        extended += 1

        return extended

    def get_distance(self, p1, p2):
        """Calculate Euclidean distance between two normalized points."""
        return np.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

    def hand_scale(self, landmarks):
        """Return a size reference for the hand, in normalized units.

        Pinch distance has to be judged relative to hand size. With a fixed
        absolute threshold the same physical pinch reads as a pinch or not
        depending only on how far the user sits from the camera.
        """
        if landmarks is None or len(landmarks) <= MIDDLE_MCP:
            return None
        scale = self.get_distance(landmarks[WRIST], landmarks[MIDDLE_MCP])
        return scale if scale > 1e-6 else None

    def is_pinch_gesture(self, landmarks):
        """Check for a thumb-index pinch, measured relative to hand size.

        Two guards stop a pinch firing during other poses:
          * the threshold scales with the hand, so it behaves the same at
            any distance from the camera
          * the middle finger must not be clearly extended, which is what
            separates a pinch from the two-finger scroll pose
        """
        if landmarks is None or len(landmarks) <= MIDDLE_TIP:
            return False, 0.0

        scale = self.hand_scale(landmarks)
        if scale is None:
            return False, 0.0

        # Reject the two-finger / three-finger poses outright.
        if landmarks[MIDDLE_TIP][1] < landmarks[MIDDLE_PIP][1] - config.PINCH_MIDDLE_GUARD:
            return False, 0.0

        dist = self.get_distance(landmarks[THUMB_TIP], landmarks[INDEX_TIP])
        ratio = dist / scale
        if ratio >= config.PINCH_RATIO:
            return False, 0.0
        return True, 1.0 - (ratio / config.PINCH_RATIO)

    def is_open_palm(self, landmarks):
        """Check if all fingers are extended (open palm)."""
        if landmarks is None:
            return False, 0.0
        extended = self.count_extended_fingers(landmarks)
        # All 5 fingers extended = open palm
        is_open = extended >= 4  # Allow 4+ fingers
        confidence = extended / 5.0
        return is_open, confidence

    def is_index_middle_closed(self, landmarks):
        """Check for folded index and middle fingers with another finger extended."""
        if landmarks is None or len(landmarks) <= PINKY_PIP:
            return False, 0.0

        index_folded = landmarks[INDEX_TIP][1] >= landmarks[INDEX_PIP][1] + 0.015
        middle_folded = landmarks[MIDDLE_TIP][1] >= landmarks[MIDDLE_PIP][1] + 0.015
        ring_extended = landmarks[RING_TIP][1] < landmarks[RING_PIP][1]
        pinky_extended = landmarks[PINKY_TIP][1] < landmarks[PINKY_PIP][1]
        is_close_gesture = index_folded and middle_folded and (ring_extended or pinky_extended)
        return is_close_gesture, 0.9 if is_close_gesture else 0.0

    def is_two_finger_gesture(self, landmarks):
        """Check if index + middle finger are up (for right-click/scroll)."""
        if landmarks is None or len(landmarks) < 13:
            return False, 0.0

        index_up = landmarks[INDEX_TIP][1] < landmarks[INDEX_PIP][1]
        middle_up = landmarks[MIDDLE_TIP][1] < landmarks[MIDDLE_PIP][1]
        ring_down = landmarks[RING_TIP][1] > landmarks[14][1] if len(landmarks) > 14 else True
        pinky_down = landmarks[PINKY_TIP][1] > landmarks[18][1] if len(landmarks) > 18 else True

        is_two = index_up and middle_up and ring_down and pinky_down
        confidence = 0.8 if is_two else 0.0
        return is_two, confidence

    def get_two_finger_direction(self, landmarks):
        """Get vertical direction of two-finger gesture for scrolling.
        Returns: 'up', 'down', or None
        """
        if landmarks is None or len(landmarks) < 13:
            return None

        index_tip = landmarks[INDEX_TIP][1]
        middle_tip = landmarks[MIDDLE_TIP][1]
        wrist_y = landmarks[WRIST][1]

        avg_finger_y = (index_tip + middle_tip) / 2.0

        # Check if fingers are in two-finger pose
        index_up = landmarks[INDEX_TIP][1] < landmarks[INDEX_PIP][1]
        middle_up = landmarks[MIDDLE_TIP][1] < landmarks[MIDDLE_PIP][1]

        if not (index_up and middle_up):
            return None

        # Compare to wrist to determine direction
        # If fingers are above wrist significantly -> scrolled up
        # If fingers move down relative to initial -> scrolled down
        # Use threshold from config
        return avg_finger_y  # Return normalized y for external use

    def get_two_finger_delta(self, landmarks, prev_avg_y):
        """Calculate vertical delta of two fingers from previous position."""
        if landmarks is None or len(landmarks) < 13:
            return 0.0
        avg_y = (landmarks[INDEX_TIP][1] + landmarks[MIDDLE_TIP][1]) / 2.0
        return avg_y - prev_avg_y

    def recognize(self, landmarks, prev_avg_y=None):
        """Main recognition method. Returns gesture name and confidence."""
        if landmarks is None or len(landmarks) < 5:
            self.current_gesture = "NO_HAND"
            self.gesture_confidence = 0.0
            return self.current_gesture, self.gesture_confidence

        # Check open palm (pause)
        is_open, open_conf = self.is_open_palm(landmarks)
        if is_open and open_conf > config.PALM_OPEN_RATIO:
            self.current_gesture = "PALM_OPEN"
            self.gesture_confidence = open_conf
            return self.current_gesture, self.gesture_confidence

        is_close_window, close_conf = self.is_index_middle_closed(landmarks)
        if is_close_window and close_conf >= 0.8:
            self.current_gesture = "CLOSE_WINDOW"
            self.gesture_confidence = close_conf
            return self.current_gesture, self.gesture_confidence

        # Check pinch
        is_pinch, pinch_conf = self.is_pinch_gesture(landmarks)
        if is_pinch and pinch_conf > config.PINCH_LABEL_CONFIDENCE:
            self.current_gesture = "PINCH"
            self.gesture_confidence = pinch_conf
            return self.current_gesture, self.gesture_confidence

        # Check two-finger gesture
        is_two, two_conf = self.is_two_finger_gesture(landmarks)
        if is_two and two_conf > 0.7:
            self.current_gesture = "TWO_FINGER"
            self.gesture_confidence = two_conf
            return self.current_gesture, self.gesture_confidence

        # Check if index finger is pointing (mouse move)
        lm = landmarks
        index_up = len(lm) > 8 and lm[INDEX_TIP][1] < lm[INDEX_PIP][1]
        if index_up:
            self.current_gesture = "POINTING"
            self.gesture_confidence = 0.9
            return self.current_gesture, self.gesture_confidence

        # Default: fist/open hand not matched
        self.current_gesture = "FIST"
        self.gesture_confidence = 0.3
        return self.current_gesture, self.gesture_confidence

    def reset_pause(self):
        """Reset the pause state."""
        self.is_paused = False

    def toggle_pause(self):
        """Toggle pause state."""
        self.is_paused = not self.is_paused
        return self.is_paused
