"""
Virtual keyboard module.
Provides an on-screen keyboard controlled by hand gestures.
All coordinates are in frame (640x480) space.
"""
import cv2

from . import config


class VirtualKeyboard:
    def __init__(self):
        self.is_open = False
        self.text = ""
        self.hovered_key = None
        self.frame_w = config.CAMERA_WIDTH   # 640
        self.frame_h = config.CAMERA_HEIGHT  # 480
        # Keyboard layout in frame coordinates
        self.key_y_start = 100

    def open(self):
        """Open the virtual keyboard."""
        self.is_open = True
        self.text = ""
        self.hovered_key = None

    def close(self):
        """Close the virtual keyboard without discarding the query."""
        self.is_open = False
        self.hovered_key = None

    def get_key_at_position(self, frame_x, frame_y):
        """Determine which key is at the given frame coordinates (0-640, 0-480)."""
        if not self.is_open:
            return None

        # Calculate key positions relative to frame dimensions
        scale_x = self.frame_w / config.CAMERA_WIDTH
        scale_y = self.frame_h / config.CAMERA_HEIGHT

        kw = int(config.KEY_W * scale_x)
        kh = int(config.KEY_H * scale_y)
        gap = int(config.KEY_GAP * scale_x)

        rows = (
            config.KEYBOARD_ROW_0,
            config.KEYBOARD_ROW_1,
            config.KEYBOARD_ROW_2,
            config.KEYBOARD_ROW_3,
        )
        y = int(self.key_y_start * scale_y)
        for row in rows:
            row_width = len(row) * kw + (len(row) - 1) * gap
            row_start_x = (self.frame_w - row_width) // 2
            for i, key in enumerate(row):
                x = row_start_x + i * (kw + gap)
                if x <= frame_x <= x + kw and y <= frame_y <= y + kh:
                    return key
            y += kh + gap

        special_keys = [('Backspace', kw * 2), ('Space', kw * 3), ('Enter', kw),
                        ('.', kw), (',', kw), ('!', kw), ('?', kw)]
        special_x = 20
        for i, (key, width) in enumerate(special_keys):
            x = special_x + i * (width + gap)
            if x <= frame_x <= x + width and y <= frame_y <= y + kh:
                return key

        y += kh + gap
        button_width = kw * 4
        button_x = (self.frame_w - button_width) // 2
        if button_x <= frame_x <= button_x + button_width and y <= frame_y <= y + kh:
            return "SEARCH"

        return None

    def append_key(self, key_name):
        """Append a key to the internal search query string.

        This never reaches the operating system: the characters stay in
        this object and are only used to build a search URL.
        """
        if key_name == "Backspace":
            self.text = self.text[:-1]
        elif key_name == "Space":
            self.text += " "
        elif key_name in ("Enter", "SEARCH"):
            return False
        elif key_name in (".", ",", "!", "?"):
            self.text += key_name
        elif len(key_name) == 1 and key_name.isalnum():
            self.text += key_name.upper()
        else:
            return False
        return True

    def draw_keyboard(self, frame):
        """Draw the virtual keyboard overlay on the frame."""
        if not self.is_open:
            return frame

        height, width = frame.shape[:2]

        # Semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (width, height), (0, 0, 0), -1)
        frame = cv2.addWeighted(overlay, 0.5, frame, 0.5, 0)

        # Title
        cv2.putText(frame, "DIGITAL KEYBOARD", (width // 2 - 110, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 200), 2, cv2.LINE_AA)

        # Scale factor based on frame size
        scale_x = width / config.CAMERA_WIDTH
        scale_y = height / config.CAMERA_HEIGHT

        kw = int(config.KEY_W * scale_x)
        kh = int(config.KEY_H * scale_y)
        gap = int(config.KEY_GAP * scale_x)
        y_start = int(100 * scale_y)

        # Draw all keys
        y_offset = y_start
        row_data = [
            config.KEYBOARD_ROW_0,
            config.KEYBOARD_ROW_1,
            config.KEYBOARD_ROW_2,
            config.KEYBOARD_ROW_3,
        ]

        for row in row_data:
            row_width = len(row) * kw + (len(row) - 1) * gap
            start_x = (width - row_width) // 2
            for i, key in enumerate(row):
                x = start_x + i * (kw + gap)
                hovered = key == self.hovered_key
                color = (0, 255, 255) if hovered else (0, 200, 100)
                thickness = 3 if hovered else 1
                cv2.rectangle(frame, (x, y_offset), (x + kw, y_offset + kh), color, thickness)
                cv2.putText(frame, key, (x + 3, y_offset + kh // 2 + 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
            y_offset += kh + gap

        # Special keys row
        special_keys = [('Backspace', kw * 2), ('Space', kw * 3), ('Enter', kw),
                        ('.', kw), (',', kw), ('!', kw), ('?', kw)]
        sx = 20
        for i, (key, w) in enumerate(special_keys):
            x = sx + i * (w + gap)
            hovered = key == self.hovered_key
            color = (0, 255, 255) if hovered else (100, 150, 255)
            thickness = 3 if hovered else 1
            cv2.rectangle(frame, (x, y_offset), (x + w, y_offset + kh), color, thickness)
            label = key[:6] if len(key) > 6 else key
            cv2.putText(frame, label, (x + 2, y_offset + kh // 2 + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1, cv2.LINE_AA)

        # Search button
        y_offset += kh + gap + 5
        btn_w = kw * 4
        btn_x = (width - btn_w) // 2
        search_hovered = self.hovered_key == "SEARCH"
        search_color = (0, 255, 255) if search_hovered else (0, 255, 0)
        cv2.rectangle(frame, (btn_x, y_offset), (btn_x + btn_w, y_offset + kh),
                     search_color, 3 if search_hovered else 2)
        cv2.putText(frame, "SEARCH", (btn_x + btn_w // 2 - 25, y_offset + kh // 2 + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, search_color, 1, cv2.LINE_AA)

        # Show current text
        cv2.putText(frame, f"Text: {self.text}", (20, y_offset + kh + 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)

        # Instructions
        cv2.putText(frame, "Move finger to keys | Pinch to select | Open Palm to close",
                    (20, height - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (150, 150, 150), 1, cv2.LINE_AA)

        return frame
