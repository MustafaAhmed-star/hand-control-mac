"""Hand Control for macOS: control your Mac with hand gestures through the webcam.

    Thumbs up / down     volume up / down (repeats while held)
    Point right / left   right / left arrow key
    Pinch                space bar

In the window: P pauses, Q or Esc quits.
"""

import os
import sys
import time
import urllib.request

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

import gestures
import mac_actions

MODEL_NAME = "hand_landmarker.task"
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/1/hand_landmarker.task")
WINDOW = "Hand Control"

LABELS = {
    gestures.THUMBS_UP: "Volume up",
    gestures.THUMBS_DOWN: "Volume down",
    gestures.POINT_RIGHT: "Right arrow",
    gestures.POINT_LEFT: "Left arrow",
    gestures.PINCH: "Space",
}

GREEN = (80, 220, 100)
WHITE = (255, 255, 255)
ORANGE = (0, 165, 255)
RED = (60, 60, 230)


def model_path():
    """Find the hand model: bundled inside the app, or next to this script (downloaded once)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, MODEL_NAME)
    if not os.path.exists(path):
        print("Downloading hand model (about 8 MB, first run only)...")
        urllib.request.urlretrieve(MODEL_URL, path)
    return path


def perform(gesture):
    if gesture == gestures.THUMBS_UP:
        mac_actions.change_volume(mac_actions.VOLUME_STEP)
    elif gesture == gestures.THUMBS_DOWN:
        mac_actions.change_volume(-mac_actions.VOLUME_STEP)
    elif gesture == gestures.POINT_RIGHT:
        mac_actions.press_key(mac_actions.KEY_RIGHT)
    elif gesture == gestures.POINT_LEFT:
        mac_actions.press_key(mac_actions.KEY_LEFT)
    elif gesture == gestures.PINCH:
        mac_actions.press_key(mac_actions.KEY_SPACE)


def draw_hand(frame, pts):
    for c in vision.HandLandmarksConnections.HAND_CONNECTIONS:
        cv2.line(frame, pts[c.start], pts[c.end], WHITE, 2, cv2.LINE_AA)
    for p in pts:
        cv2.circle(frame, p, 4, GREEN, -1, cv2.LINE_AA)


def draw_text(frame, text, y, color):
    cv2.putText(frame, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(frame, text, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)


def open_camera():
    cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
    return cap


def main():
    options = vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=model_path()),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.6,
        min_tracking_confidence=0.5,
    )
    landmarker = vision.HandLandmarker.create_from_options(options)
    cap = open_camera()
    trigger = gestures.GestureTrigger()
    keys_allowed = mac_actions.can_press_keys()
    if not keys_allowed:
        mac_actions.open_accessibility_settings()

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    try:
        cv2.setWindowProperty(WINDOW, cv2.WND_PROP_TOPMOST, 1)
    except cv2.error:
        pass

    paused = False
    last_ts = 0
    last_action, last_action_at = None, 0.0
    failed_reads = 0
    last_ax_check = 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            # Camera busy, or macOS is still asking for permission: say so and keep retrying.
            failed_reads += 1
            if failed_reads % 20 == 0:
                cap.release()
                cap = open_camera()
            frame = np.zeros((540, 960, 3), np.uint8)
            draw_text(frame, "Waiting for the camera...", 40, ORANGE)
            draw_text(frame, "Allow camera access: System Settings > Privacy & Security > Camera", 80, WHITE)
            draw_text(frame, "Quit other apps using it (Zoom, FaceTime). Press Q to quit.", 115, WHITE)
            cv2.imshow(WINDOW, frame)
            if cv2.waitKey(50) & 0xFF in (ord("q"), ord("Q"), 27):
                break
            continue
        failed_reads = 0

        frame = cv2.flip(frame, 1)  # mirror, so pointing right means your right
        h, w = frame.shape[:2]
        now = time.monotonic()

        gesture = None
        if not paused:
            ts = max(int(now * 1000), last_ts + 1)  # VIDEO mode needs increasing timestamps
            last_ts = ts
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts)
            if result.hand_landmarks:
                pts = [(int(lm.x * w), int(lm.y * h)) for lm in result.hand_landmarks[0]]
                draw_hand(frame, pts)
                gesture = gestures.classify(pts)

            fired = trigger.update(gesture, now)
            if fired:
                perform(fired)
                last_action, last_action_at = fired, now

        if paused:
            draw_text(frame, "PAUSED - press P to resume", 30, ORANGE)
        elif gesture:
            draw_text(frame, LABELS[gesture], 30, GREEN)
        if last_action and now - last_action_at < 1.0:
            draw_text(frame, "-> " + LABELS[last_action], 60, GREEN)
        if not keys_allowed:
            draw_text(frame, "Allow Accessibility for arrows/space", h - 20, RED)
            if now - last_ax_check > 1.0:  # pick up the permission once it is granted
                keys_allowed = mac_actions.can_press_keys()
                last_ax_check = now

        cv2.imshow(WINDOW, frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q"), 27):
            break
        if key in (ord("p"), ord("P")):
            paused = not paused
            trigger = gestures.GestureTrigger()
        if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
            break

    cap.release()
    landmarker.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
