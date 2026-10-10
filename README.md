# Hand Control for Mac

Control your Mac with hand gestures, using only the webcam.

| Gesture | What it does |
|---|---|
| 👍 Thumbs up | Volume up (keeps going while you hold it) |
| 👎 Thumbs down | Volume down (keeps going while you hold it) |
| 👉 Point right with your index finger | Right arrow |
| 👈 Point left with your index finger | Left arrow |
| 🤏 Pinch thumb and index together | Space bar (one press per pinch) |

The window shows your camera with the hand skeleton drawn on it, so you can see what it sees.

Needs a Mac with Apple Silicon (M1 or newer) and macOS 11 or later. Intel Macs are not supported, because current MediaPipe only ships for Apple Silicon.

## Install (like any Mac app)

**Option A: download the ready app**

1. Download [HandControl-mac.zip](../../releases/latest/download/HandControl-mac.zip) from the latest release, then double-click it to unzip.
2. Drag **HandControl** into your **Applications** folder.
3. Double-click it. The first time, macOS blocks apps from outside the App Store:
   go to **System Settings → Privacy & Security**, scroll down, click **Open Anyway** next to HandControl, then **Open**.
   You only do this once.

**Option B: build it on your Mac**

```bash
./build_mac.sh
```

This builds `HandControl.app` and installs it into Applications. macOS doesn't block apps you build yourself.

After installing, open it from Launchpad, Spotlight (⌘ Space, type "Hand Control") or the Dock, like any other app.
To keep it in the Dock: while it is running, right-click its Dock icon → Options → **Keep in Dock**.

## Permissions (one time)

macOS asks for two permissions. Without them the app opens but cannot do its job.

1. **Camera**: click **OK** when asked. If you said no, go to System Settings → Privacy & Security → Camera and switch on **HandControl**. The app shows "Waiting for the camera..." until access is allowed.
2. **Accessibility**, which arrow keys and space need. The app opens the right settings page on first run. Switch on **HandControl**, then quit and reopen the app. Volume works without this.

## Run from source (for development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python hand_control.py
```

The first run downloads the hand model (about 8 MB). When run this way, give the Accessibility permission to **Terminal** instead.

## Using it

- Arrow keys and space go to the app you clicked last. After starting Hand Control, click your slides, video or photo viewer once.
- Hold a gesture for a moment before it fires. Keep your hand upright or level; diagonal gestures are ignored on purpose.
- In the Hand Control window: **P** pauses, **Q** or **Esc** quits.
- If the camera cannot be opened, quit other apps that use it (Zoom, Teams, FaceTime, Photo Booth).

## Privacy

The camera picture is processed on your Mac only. Nothing is recorded, saved or sent anywhere. The only time the internet is used is the one-time model download when running from source.

## How it works

- `hand_control.py`: camera loop, MediaPipe hand tracking, drawing, and keyboard shortcuts.
- `gestures.py`: turns the 21 hand points into a gesture, plus the hold/repeat timing. It has no camera or OS code, so it is fully unit tested (`python -m unittest discover -s tests`).
- `.github/workflows/build-mac.yml`: builds the app on GitHub's Mac machines and publishes a new release on every push to `main`.
- `mac_actions.py`: volume through `osascript`, key presses through macOS CoreGraphics. No extra packages are needed for this.

Built with [MediaPipe](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker) hand tracking and [OpenCV](https://opencv.org/).

This is an independent implementation inspired by [mahmoudwaelali/hand-control](https://github.com/mahmoudwaelali/hand-control), which is a Windows app. No code from that project is used.
