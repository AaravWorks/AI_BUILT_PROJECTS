"""MediaPipe 1.x hand tracking and landmark extraction."""
from pathlib import Path
import time

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import vision

from . import config


BaseOptions = mp.tasks.BaseOptions


HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)


class HandTracker:
    def __init__(self):
        self.hands = None
        self.landmarks = None
        self.handedness = []
        self.hand_found = False
        self._last_timestamp_ms = 0
        self.model_path = (
            Path(__file__).resolve().parent.parent
            / "assets"
            / "hand_landmarker.task"
        )

        if not self.model_path.is_file():
            print(f"[ERROR] Hand model not found: {self.model_path}")
            return

        try:
            options = vision.HandLandmarkerOptions(
                base_options=BaseOptions(
                    model_asset_path=str(self.model_path),
                    delegate=BaseOptions.Delegate.CPU,
                ),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=config.MAX_NUM_HANDS,
                min_hand_detection_confidence=config.HAND_DETECTION_CONFIDENCE,
                min_hand_presence_confidence=config.HAND_TRACKING_CONFIDENCE,
                min_tracking_confidence=config.HAND_TRACKING_CONFIDENCE,
            )
            self.hands = vision.HandLandmarker.create_from_options(options)
        except Exception as exc:
            print(f"[ERROR] MediaPipe hand tracker initialization failed: {exc}")
            self.hands = None

    def process(self, frame):
        """Process a BGR frame and return whether a hand was detected."""
        if self.hands is None or frame is None:
            self.hand_found = False
            self.landmarks = None
            return False

        try:
            rgb_frame = np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            timestamp_ms = time.monotonic_ns() // 1_000_000
            if timestamp_ms <= self._last_timestamp_ms:
                timestamp_ms = self._last_timestamp_ms + 1
            self._last_timestamp_ms = timestamp_ms

            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            result = self.hands.detect_for_video(image, timestamp_ms)

            self.landmarks = None
            self.handedness = []

            if not result.hand_landmarks:
                self.hand_found = False
                return False

            self.hand_found = True
            self.landmarks = [
                np.array([[point.x, point.y, point.z] for point in hand])
                for hand in result.hand_landmarks
            ]

            for handedness in result.handedness:
                if handedness:
                    self.handedness.append(handedness[0].category_name)

            return True
        except Exception as exc:
            print(f"[ERROR] Hand tracking error: {exc}")
            self.hand_found = False
            self.landmarks = None
            return False

    def draw_landmarks(self, frame):
        """Draw the detected hand skeleton and landmark points."""
        landmarks = self.get_landmarks()
        if landmarks is None:
            return frame

        height, width = frame.shape[:2]
        points = [
            (int(point[0] * width), int(point[1] * height))
            for point in landmarks
        ]

        for start, end in HAND_CONNECTIONS:
            cv2.line(
                frame,
                points[start],
                points[end],
                (100, 255, 100),
                2,
                cv2.LINE_AA,
            )

        for index, point in enumerate(points):
            radius = 5 if index in (4, 8) else 3
            color = (0, 255, 255) if index == 8 else (100, 255, 100)
            cv2.circle(frame, point, radius, color, -1, cv2.LINE_AA)

        return frame

    def get_landmarks(self):
        if self.landmarks:
            return self.landmarks[0]
        return None

    def get_index_finger_tip(self):
        landmarks = self.get_landmarks()
        if landmarks is not None and len(landmarks) > 8:
            return landmarks[8][0], landmarks[8][1]
        return None

    def get_thumb_tip(self):
        landmarks = self.get_landmarks()
        if landmarks is not None and len(landmarks) > 4:
            return landmarks[4][0], landmarks[4][1]
        return None

    def get_middle_finger_tip(self):
        landmarks = self.get_landmarks()
        if landmarks is not None and len(landmarks) > 12:
            return landmarks[12][0], landmarks[12][1]
        return None

    def get_pinky_tip(self):
        landmarks = self.get_landmarks()
        if landmarks is not None and len(landmarks) > 20:
            return landmarks[20][0], landmarks[20][1]
        return None

    def get_hand_center(self):
        landmarks = self.get_landmarks()
        if landmarks is not None:
            return landmarks[0][0], landmarks[0][1]
        return None

    def close(self):
        if self.hands is not None:
            self.hands.close()
            self.hands = None
