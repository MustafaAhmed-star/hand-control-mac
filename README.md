# Hand Control for Mac

Control your Mac with hand gestures, using only the webcam. Works with one hand or both.

### Control mode (default)

| Gesture | What it does |
|---|---|
| 👍 Thumbs up / 👎 down | Volume up / down (keeps going while you hold it) |
| 👉 Point right / 👈 left with your index finger | Right / left arrow key |
| 🤏 Pinch thumb and index together | Space bar: play / pause (one press per pinch) |
| ✋ Open palm, swipe left / right | Next / previous desktop, like the three-finger trackpad swipe |
| ✋ Open palm, swipe up | Mission Control |
| ✋ Open palm, swipe down | All windows of the current app |
| ✌️ Peace sign, move up / down | Scroll |
| 🤙 Thumb and pinky out | Switch to the previous app (⌘ Tab) |
| 🙌 Both open palms, move apart / together | Zoom in / out (⌘ + / ⌘ −) |
| ✌️✌️ Both hands peace sign for 1 second | Switch to mouse mode |

### Mouse mode

| Gesture | What it does |
|---|---|
| ✋ Move your hand | Move the cursor |
| 🤏 Pinch thumb and index | Click; pinch twice quickly to double click |
| 🤏 Hold the pinch and move | Drag |
| Pinch thumb and **middle** finger | Right click |
| ✌️ Peace sign, move up / down | Scroll |
| ✌️✌️ Both hands peace sign for 1 second | Back to control mode |

When both hands are visible, one-hand gestures use your right hand.
The window shows your camera with the hand skeleton drawn on each hand, so you can see what it sees.

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
2. **Accessibility**, which keys and mouse control need. The app opens the right settings page on first run. Switch on **HandControl**, then quit and reopen the app. Volume works without this.

Switching desktops and Mission Control use the standard macOS shortcuts (Control + arrow keys). If they don't work, check they are switched on in System Settings → Keyboard → Keyboard Shortcuts → Mission Control. To have desktops to switch between, open Mission Control and click **+** at the top.

## Run from source (for development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python hand_control.py
```

The first run downloads the hand model (about 8 MB). When run this way, give the Accessibility permission to **Terminal** instead.

## Using it

- Keys go to the app you clicked last. After starting Hand Control, click your slides, video or photo viewer once.
- Hold a gesture for a moment before it fires. Keep your hand upright or level; diagonal gestures are ignored on purpose.
- Swipes need a quick, clear movement of about two hand-widths. Slow drifting is ignored, so resting your hand won't switch desktops.
- In mouse mode, keep your hand in the middle of the camera's view: that area covers the whole screen.
- In the Hand Control window: **H** shows the gestures, **M** switches between control and mouse mode, **P** pauses, **Q** or **Esc** quits.
- If the camera cannot be opened, quit other apps that use it (Zoom, Teams, FaceTime, Photo Booth).

## Privacy

The camera picture is processed on your Mac only. Nothing is recorded, saved or sent anywhere. The only time the internet is used is the one-time model download when running from source.

## How it works

- `hand_control.py`: camera loop, MediaPipe hand tracking (up to two hands), drawing, and window shortcuts.
- `gestures.py`: turns a hand's 21 points into a shape (thumbs up, peace sign, open palm...), plus the hold/repeat timing.
- `controller.py`: turns the hands seen in each frame into actions: swipes, scrolling, two-hand gestures, and mouse mode with smoothing (One Euro filter) and pinch clicks.
- `gestures.py` and `controller.py` have no camera or OS code, so they are fully unit tested (`python -m unittest discover -s tests`).
- `.github/workflows/build-mac.yml`: builds the app on GitHub's Mac machines and publishes a new release on every push to `main`.
- `mac_actions.py`: volume through `osascript`; keys, mouse and scrolling through macOS CoreGraphics. No extra packages are needed for this.

Built with [MediaPipe](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker) hand tracking and [OpenCV](https://opencv.org/).

This is an independent implementation inspired by [mahmoudwaelali/hand-control](https://github.com/mahmoudwaelali/hand-control), which is a Windows app. No code from that project is used.
