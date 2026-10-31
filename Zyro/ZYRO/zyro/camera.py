"""
Camera handling module.
Manages webcam capture with error handling.
"""
import cv2

from . import config


class Camera:
    def __init__(self):
        self.cap = None
        self.frame = None
        self.is_open = False

    def open(self, index=0):
        """Open the webcam."""
        try:
            self.cap = cv2.VideoCapture(index)
            if not self.cap.isOpened():
                return False
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
            self.cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)
            self.is_open = True
            return True
        except Exception as e:
            print(f"[ERROR] Camera init failed: {e}")
            return False

    def read(self):
        """Read a frame from the camera."""
        if not self.is_open or self.cap is None:
            return None
        try:
            ret, frame = self.cap.read()
            if not ret:
                return None
            self.frame = frame
            return frame
        except Exception:
            return None

    def release(self):
        """Release the camera."""
        if self.cap is not None:
            self.cap.release()
        self.is_open = False

    def is_valid(self):
        """Check if camera is ready."""
        return self.is_open and self.cap is not None

    def get_frame_size(self):
        """Get current frame dimensions."""
        if self.frame is not None:
            return self.frame.shape[1], self.frame.shape[0]
        return config.CAMERA_WIDTH, config.CAMERA_HEIGHT
