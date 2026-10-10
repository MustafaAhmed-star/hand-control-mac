"""Hand Control for macOS: control your Mac with hand gestures through the webcam.

See HELP below (or press H in the window) for the gestures.
In the window: H shows help, M switches mouse mode, P pauses, Q or Esc quits.
"""

import os
import sys
import time
import urllib.request

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

import controller
import mac_actions

MODEL_NAME = "hand_landmarker.task"
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/1/hand_landmarker.task")
WINDOW = "Hand Control"

HELP = {
    controller.CONTROL: [
        "Thumbs up / down: volume",
        "Point left / right: arrow keys",
        "Pinch: space (play / pause)",
        "Open palm swipe left / right: switch desktop",
        "Open palm swipe up / down: Mission Control / app windows",
        "Peace sign, move up / down: scroll",
        "Thumb + pinky out: previous app",
        "Both palms apart / together: zoom in / out",
        "Both hands peace sign 1s: mouse mode",
    ],
    controller.MOUSE: [
        "Move your hand: move the cursor",
        "Pinch thumb + index: click (twice = double click)",
        "Hold the pinch and move: drag",
        "Pinch thumb + middle: right click",
        "Peace sign, move up / down: scroll",
        "Both hands peace sign 1s: back to control mode",
    ],
}

GREEN = (80, 220, 100)
WHITE = (255, 255, 255)
ORANGE = (0, 165, 255)
RED = (60, 60, 230)
BLUE = (240, 170, 60)


def model_path():
    """Find the hand model: bundled inside the app, or next to this script (downloaded once)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, MODEL_NAME)
    if not os.path.exists(path):
        print("Downloading hand model (about 8 MB, first run only)...")
        urllib.request.urlretrieve(MODEL_URL, path)
    return path


def draw_hand(frame, pts, color):
    for c in vision.HandLandmarksConnections.HAND_CONNECTIONS:
        cv2.line(frame, pts[c.start], pts[c.end], WHITE, 2, cv2.LINE_AA)
    for p in pts:
        cv2.circle(frame, p, 4, color, -1, cv2.LINE_AA)


def draw_text(frame, text, y, color, x=12, scale=0.7):
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2, cv2.LINE_AA)


def draw_help(frame, mode):
    lines = HELP[mode]
    h = frame.shape[0]
    overlay = frame.copy()
    top = h - 30 - 26 * len(lines)
    cv2.rectangle(overlay, (0, top - 30), (620, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
    for i, line in enumerate(lines):
        draw_text(frame, line, top + 26 * i, WHITE, scale=0.55)


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
        num_hands=2,
        min_hand_detection_confidence=0.6,
        min_tracking_confidence=0.5,
    )
    landmarker = vision.HandLandmarker.create_from_options(options)
    cap = open_camera()
    control = controller.Controller()
    keys_allowed = mac_actions.can_press_keys()
    if not keys_allowed:
        mac_actions.open_accessibility_settings()

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    try:
        cv2.setWindowProperty(WINDOW, cv2.WND_PROP_TOPMOST, 1)
    except cv2.error:
        pass

    paused = False
    show_help = False
    help_until = time.monotonic() + 10  # show the gestures for the first seconds
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

        if not paused:
            ts = max(int(now * 1000), last_ts + 1)  # VIDEO mode needs increasing timestamps
            last_ts = ts
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts)
            hands = []
            for i, landmarks in enumerate(result.hand_landmarks):
                # The frame is mirrored, which is what MediaPipe's handedness assumes.
                label = result.handedness[i][0].category_name if result.handedness else "Right"
                pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
                hands.append(controller.Hand(label, pts))
                draw_hand(frame, pts, GREEN if label == "Right" else BLUE)

            for action in control.update(hands, (w, h), now):
                mac_actions.perform(action)
                if action.label:
                    last_action, last_action_at = action.label, now

        mode_text = "MOUSE MODE" if control.mode == controller.MOUSE else "CONTROL MODE"
        draw_text(frame, mode_text, 30, BLUE if control.mode == controller.MOUSE else GREEN)
        draw_text(frame, "H help  M mouse  P pause  Q quit", 30, WHITE, x=w - 400, scale=0.55)
        if paused:
            draw_text(frame, "PAUSED - press P to resume", 60, ORANGE)
        elif last_action and now - last_action_at < 1.0:
            draw_text(frame, "-> " + last_action, 60, GREEN)
        if show_help or now < help_until:
            draw_help(frame, control.mode)
        if not keys_allowed:
            draw_text(frame, "Allow Accessibility for keys and mouse", 90, RED)
            if now - last_ax_check > 1.0:  # pick up the permission once it is granted
                keys_allowed = mac_actions.can_press_keys()
                last_ax_check = now

        cv2.imshow(WINDOW, frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q"), 27):
            break
        if key in (ord("p"), ord("P")):
            paused = not paused
            for action in control.mouse.release():  # never leave a mouse button held down
                mac_actions.perform(action)
        if key in (ord("h"), ord("H")):
            show_help = not (show_help or now < help_until)
            help_until = 0
        if key in (ord("m"), ord("M")):
            for action in control.toggle_mode():
                mac_actions.perform(action)
                if action.label:
                    last_action, last_action_at = action.label, now
        if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
            break

    cap.release()
    landmarker.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
