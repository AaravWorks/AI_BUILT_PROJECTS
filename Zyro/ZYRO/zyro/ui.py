"""
UI/HUD module for ZYRO.

Draws the interface overlay on the camera frame. Panels are composited
only over their own region rather than the whole frame, so the overlay
stays cheap enough to hold a smooth frame rate.
"""
import cv2
import numpy as np

from . import config


BRAND = "ZYRO"
SUBTITLE = "GESTURE CONTROL"
FOOTER_HINTS = "PINCH  Click    I+M  Close    PALM  Pause    P  Precision    S  Search"

FONT = cv2.FONT_HERSHEY_SIMPLEX
HEADER_H = 54
FOOTER_H = 28
PANEL_W = 268
PANEL_H = 98


def get_colors():
    """Return the HUD colour palette."""
    return {
        'bg': config.HUD_BG,
        'panel': config.HUD_PANEL,
        'accent': config.HUD_ACCENT,
        'accent_soft': config.HUD_ACCENT_SOFT,
        'text': config.HUD_TEXT,
        'dim': config.HUD_TEXT_DIM,
        'ok': config.HUD_OK,
        'warn': config.HUD_WARN,
        'bad': config.HUD_BAD,
    }


def _blend_region(frame, x1, y1, x2, y2, color, alpha):
    """Fill a region with a solid colour at the given opacity.

    Only the target region is touched, which keeps this far cheaper than
    compositing a full-frame overlay copy every frame.
    """
    h, w = frame.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return
    region = frame[y1:y2, x1:x2]
    fill = np.empty_like(region)
    fill[:] = color
    cv2.addWeighted(fill, alpha, region, 1.0 - alpha, 0, dst=region)


def _rounded_rect(frame, x1, y1, x2, y2, radius, color, alpha=1.0, thickness=-1):
    """Draw a rectangle with softened corners."""
    if alpha < 1.0:
        _blend_region(frame, x1, y1, x2, y2, color, alpha)
    else:
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
    if thickness == -1:
        r = max(1, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
        for cx, cy in ((x1 + r, y1 + r), (x2 - r, y1 + r),
                       (x1 + r, y2 - r), (x2 - r, y2 - r)):
            cv2.circle(frame, (cx, cy), r, color, -1, cv2.LINE_AA)


def _text_width(text, scale, thickness):
    return cv2.getTextSize(text, FONT, scale, thickness)[0][0]


def _fit_text(text, max_width, scale, thickness, ellipsis="..."):
    """Shorten text with an ellipsis until it fits the available width."""
    if _text_width(text, scale, thickness) <= max_width:
        return text
    trimmed = text
    while trimmed and _text_width(trimmed + ellipsis, scale, thickness) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + ellipsis) if trimmed else ellipsis


def _label(frame, text, org, color, scale=0.42, thickness=1, spacing=1):
    """Draw uppercase letter-spaced label text for a refined look."""
    x, y = org
    gap = int(round(_text_width(" ", scale, thickness) * spacing))
    for ch in text:
        cv2.putText(frame, ch, (x, y), FONT, scale, color, thickness, cv2.LINE_AA)
        x += _text_width(ch, scale, thickness) + gap
    return x


def _draw_header(frame, colors, is_paused, fps, click_armed=False):
    h, w = frame.shape[:2]
    _blend_region(frame, 0, 0, w, HEADER_H, config.HUD_BG, config.HUD_BAR_ALPHA)

    # Accent underline
    cv2.line(frame, (0, HEADER_H - 2), (w, HEADER_H - 2), colors['accent'], 2, cv2.LINE_AA)
    cv2.line(frame, (0, HEADER_H - 1), (w, HEADER_H - 1), colors['accent_soft'], 1, cv2.LINE_AA)

    # Brand
    cv2.putText(frame, BRAND, (18, 34), FONT, 0.92, colors['accent'], 2, cv2.LINE_AA)
    brand_w = _text_width(BRAND, 0.92, 2)
    _label(frame, SUBTITLE, (18 + brand_w + 16, 33), colors['dim'], 0.4, 1)

    # Status pill, right aligned
    label = "PAUSED" if is_paused else "ACTIVE"
    dot_color = colors['bad'] if is_paused else colors['ok']
    pill_w = _text_width(label, 0.46, 1) + 34
    x2 = w - 16
    x1 = x2 - pill_w
    y1, y2 = 14, 40
    _rounded_rect(frame, x1, y1, x2, y2, config.HUD_RADIUS,
                  colors['panel'], config.HUD_PANEL_ALPHA)
    cv2.rectangle(frame, (x1, y1), (x2, y2), colors['accent_soft'], 1, cv2.LINE_AA)
    cv2.circle(frame, (x1 + 15, (y1 + y2) // 2), 4, dot_color, -1, cv2.LINE_AA)
    if is_paused:
        cv2.circle(frame, (x1 + 15, (y1 + y2) // 2), 7, colors['bad'], 1, cv2.LINE_AA)
    cv2.putText(frame, label, (x1 + 25, (y1 + y2) // 2 + 5), FONT,
                0.46, dot_color, 1, cv2.LINE_AA)

    # Click readiness dot - green = click will fire, red = blocked (moving / cooldown)
    click_label = "CLICK ARMED" if click_armed else "CLICK BLOCKED"
    click_dot_color = colors['ok'] if click_armed else colors['bad']
    click_pill_w = _text_width(click_label, 0.42, 1) + 30
    cx2 = x1 - 10
    cx1 = cx2 - click_pill_w
    if cx1 > 20:
        _rounded_rect(frame, cx1, y1, cx2, y2, config.HUD_RADIUS,
                      colors['panel'], config.HUD_PANEL_ALPHA)
        cv2.rectangle(frame, (cx1, y1), (cx2, y2), colors['accent_soft'], 1, cv2.LINE_AA)
        cv2.circle(frame, (cx1 + 15, (y1 + y2) // 2), 4, click_dot_color, -1, cv2.LINE_AA)
        cv2.putText(frame, click_label, (cx1 + 25, (y1 + y2) // 2 + 5), FONT,
                    0.42, click_dot_color, 1, cv2.LINE_AA)

    # FPS - right aligned so it cannot collide with the status pill
    if config.HUD_FPS:
        fps_text = f"{int(fps)} FPS"
        fps_w = _text_width(fps_text, 0.44, 1)
        cv2.putText(frame, fps_text, (x1 - 14 - fps_w, (y1 + y2) // 2 + 5), FONT,
                    0.44, colors['dim'], 1, cv2.LINE_AA)


def _draw_info_panel(frame, colors, gesture, action):
    h, w = frame.shape[:2]
    x1, y1 = 16, HEADER_H + 14
    x2 = min(w - 16, x1 + PANEL_W)
    y2 = y1 + PANEL_H

    _rounded_rect(frame, x1, y1, x2, y2, config.HUD_RADIUS,
                  colors['panel'], config.HUD_PANEL_ALPHA)
    cv2.rectangle(frame, (x1, y1), (x2, y2), colors['accent_soft'], 1, cv2.LINE_AA)
    # Accent spine on the left edge
    cv2.rectangle(frame, (x1, y1 + 1), (x1 + 3, y2 - 1), colors['accent'], -1)

    pad = 14
    inner_x = x1 + pad
    inner_w = (x2 - x1) - pad * 2

    _label(frame, "GESTURE", (inner_x, y1 + 20), colors['dim'], 0.4, 1)
    cv2.putText(frame, _fit_text(gesture or "-", inner_w, 0.58, 1),
                (inner_x, y1 + 44), FONT, 0.58, colors['accent'], 1, cv2.LINE_AA)

    cv2.line(frame, (inner_x, y1 + 54), (x2 - pad, y1 + 54), colors['accent_soft'], 1)

    _label(frame, "ACTION", (inner_x, y1 + 70), colors['dim'], 0.4, 1)
    cv2.putText(frame, _fit_text(action or "-", inner_w, 0.5, 1),
                (inner_x, y1 + 88), FONT, 0.5, colors['text'], 1, cv2.LINE_AA)


def _draw_footer(frame, colors):
    h, w = frame.shape[:2]
    y1 = h - FOOTER_H
    _blend_region(frame, 0, y1, w, h, config.HUD_BG, config.HUD_BAR_ALPHA)
    cv2.line(frame, (0, y1), (w, y1), colors['accent_soft'], 1, cv2.LINE_AA)

    text = FOOTER_HINTS
    scale = 0.36
    if _text_width(text, scale, 1) > w - 28:
        scale = 0.32
    cv2.putText(frame, text, (14, h - 10), FONT, scale, colors['dim'], 1, cv2.LINE_AA)


def _draw_cursor(frame, colors, cursor_x, cursor_y):
    x, y = int(cursor_x), int(cursor_y)
    r = 9
    cv2.circle(frame, (x, y), r, colors['accent'], 1, cv2.LINE_AA)
    cv2.circle(frame, (x, y), 2, colors['accent'], -1, cv2.LINE_AA)
    # Corner brackets instead of a full crosshair - reads cleaner
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        ax, ay = x + sx * (r + 3), y + sy * (r + 3)
        cv2.line(frame, (ax, ay), (ax - sx * 5, ay), colors['accent'], 1, cv2.LINE_AA)
        cv2.line(frame, (ax, ay), (ax, ay - sy * 5), colors['accent'], 1, cv2.LINE_AA)


def _draw_pause_overlay(frame, colors):
    h, w = frame.shape[:2]
    _blend_region(frame, 0, 0, w, h, (0, 0, 0), 0.62)
    cv2.putText(frame, "CONTROL PAUSED", (w // 2 - 190, h // 2 - 6), FONT,
                1.05, colors['bad'], 2, cv2.LINE_AA)
    cv2.putText(frame, "open palm or press Q to resume", (w // 2 - 160, h // 2 + 24), FONT,
                0.5, colors['text'], 1, cv2.LINE_AA)


def _draw_no_hand_banner(frame, colors):
    """Make 'the camera cannot see your hand' impossible to miss.

    When detection silently fails every gesture feels broken with no clue
    why, so this states the cause directly on screen.
    """
    h, w = frame.shape[:2]
    bw, bh = 300, 54
    x1, y1 = (w - bw) // 2, int(h * 0.62)
    x2, y2 = x1 + bw, y1 + bh
    _blend_region(frame, x1, y1, x2, y2, (0, 0, 0), 0.72)
    cv2.rectangle(frame, (x1, y1), (x2, y2), colors['bad'], 2, cv2.LINE_AA)
    title = "NO HAND DETECTED"
    tw = _text_width(title, 0.6, 2)
    cv2.putText(frame, title, ((w - tw) // 2, y1 + 24), FONT, 0.6,
                colors['bad'], 2, cv2.LINE_AA)
    hint = "check your hand is inside the preview"
    hw = _text_width(hint, 0.44, 1)
    cv2.putText(frame, hint, ((w - hw) // 2, y1 + 43), FONT, 0.44,
                colors['text'], 1, cv2.LINE_AA)


def draw_hud(frame, gesture, action, is_paused=False, fps=0,
             cursor_x=None, cursor_y=None, click_armed=False):
    """Draw the main heads-up display on the frame."""
    colors = get_colors()
    _draw_header(frame, colors, is_paused, fps, click_armed)
    if config.HUD_GESTURE or config.HUD_ACTION:
        _draw_info_panel(frame, colors, gesture, action)
    if config.HUD_CURSOR_INDICATOR and cursor_x is not None and cursor_y is not None:
        _draw_cursor(frame, colors, cursor_x, cursor_y)
    _draw_footer(frame, colors)
    if gesture == "NO_HAND":
        _draw_no_hand_banner(frame, colors)
    if is_paused:
        _draw_pause_overlay(frame, colors)
    return frame


def _dim_background(frame, alpha=0.68):
    h, w = frame.shape[:2]
    _blend_region(frame, 0, 0, w, h, (0, 0, 0), alpha)


def _panel_heading(frame, colors, title, y, scale=0.82):
    h, w = frame.shape[:2]
    tw = _text_width(title, scale, 2)
    cv2.putText(frame, title, ((w - tw) // 2, y), FONT, scale, colors['accent'], 2, cv2.LINE_AA)
    cv2.line(frame, (w // 2 - tw // 2, y + 10), (w // 2 + tw // 2, y + 10),
             colors['accent_soft'], 1, cv2.LINE_AA)


def draw_search_interface(frame, search_text=""):
    """Draw the web search interface overlay."""
    h, w = frame.shape[:2]
    colors = get_colors()
    _dim_background(frame)

    _panel_heading(frame, colors, "WEB SEARCH", 66)

    box_w, box_h = min(420, w - 60), 46
    box_x, box_y = (w - box_w) // 2, 104
    _rounded_rect(frame, box_x, box_y, box_x + box_w, box_y + box_h,
                  config.HUD_RADIUS, colors['panel'], config.HUD_PANEL_ALPHA)
    cv2.rectangle(frame, (box_x, box_y), (box_x + box_w, box_y + box_h),
                  colors['accent'], 1, cv2.LINE_AA)

    shown = _fit_text(search_text, box_w - 40, 0.6, 1)
    cv2.putText(frame, shown, (box_x + 16, box_y + 30), FONT, 0.6,
                colors['text'], 1, cv2.LINE_AA)
    caret_x = box_x + 18 + _text_width(shown, 0.6, 1)
    cv2.rectangle(frame, (caret_x, box_y + 12), (caret_x + 2, box_y + box_h - 12),
                  colors['accent'], -1)

    hint = "pinch keys to type, pinch SEARCH to run"
    cv2.putText(frame, hint, ((w - _text_width(hint, 0.46, 1)) // 2, h - 26), FONT,
                0.46, colors['dim'], 1, cv2.LINE_AA)
    return frame


def draw_nav_interface(frame, gesture=""):
    """Draw the command reference interface."""
    h, w = frame.shape[:2]
    colors = get_colors()
    _dim_background(frame)

    _panel_heading(frame, colors, "COMMANDS", 60)

    rows = [
        ("Move cursor", "index finger extended"),
        ("Click / tap", "pinch and release"),
        ("Double click", "pinch, hold, release"),
        ("Precision", "P  (fine cursor)"),
        ("Minimize", "M"),
        ("Scroll", "index + middle up / down"),
        ("Right click", "hold index + middle still"),
        ("Close window", "hold index + middle folded"),
        ("Pause / resume", "hold open palm"),
    ]

    x1 = max(20, (w - 440) // 2)
    x2 = min(w - 20, x1 + 440)
    y = 96
    row_h = 34

    _rounded_rect(frame, x1 - 12, y - 26, x2 + 12, y + len(rows) * row_h - 6,
                  config.HUD_RADIUS, colors['panel'], config.HUD_PANEL_ALPHA)
    cv2.rectangle(frame, (x1 - 12, y - 26), (x2 + 12, y + len(rows) * row_h - 6),
                  colors['accent_soft'], 1, cv2.LINE_AA)

    for i, (label, detail) in enumerate(rows):
        cy = y + i * row_h
        if i % 2 == 0:
            _blend_region(frame, x1 - 11, cy - 4, x2 + 11, cy + row_h - 4,
                          colors['bg'], 0.35)
        cv2.putText(frame, label, (x1, cy + 14), FONT, 0.52, colors['text'], 1, cv2.LINE_AA)
        detail_x = x1 + 168
        if detail_x < x2:
            cv2.putText(frame, detail, (detail_x, cy + 14), FONT, 0.46,
                        colors['dim'], 1, cv2.LINE_AA)
        cv2.line(frame, (x1, cy + row_h - 6), (x2, cy + row_h - 6),
                 colors['accent_soft'], 1, cv2.LINE_AA)

    if gesture:
        text = f"tracking: {gesture}"
        cv2.putText(frame, text, ((w - _text_width(text, 0.46, 1)) // 2, h - 22), FONT,
                    0.46, colors['accent'], 1, cv2.LINE_AA)
    return frame
