"""Turns the hands seen in each camera frame into actions for the Mac.

Pure logic with no camera or OS code, so it can be unit tested. The app
performs the returned actions through mac_actions.

Two modes:
    control  gestures trigger keys, volume, desktops and scrolling
    mouse    the hand moves the cursor; pinch clicks and drags
"""

import math
from collections import deque, namedtuple

import gestures as g

CONTROL = "control"
MOUSE = "mouse"

# macOS virtual key codes
KEY_LEFT, KEY_RIGHT, KEY_DOWN, KEY_UP = 123, 124, 125, 126
KEY_SPACE, KEY_TAB, KEY_EQUAL, KEY_MINUS = 49, 48, 24, 27
CTRL, CMD = "ctrl", "cmd"

VOLUME_STEP = 6  # percent

Hand = namedtuple("Hand", "label pts")  # label is "Left" or "Right"; pts are 21 (x, y) pixels

# kind and args:
#   key     (keycode, modifiers)
#   volume  (delta,)
#   scroll  (amount,)                    amount > 0 moves the page up, like swiping up on a phone
#   move    (x, y, dragging)             x and y from 0 to 1 across the screen
#   button  (button, down, clicks)       button is "left" or "right"
#   mode    (mode,)
Action = namedtuple("Action", "kind args label")


def key(code, label, *mods):
    return Action("key", (code, mods), label)


DISCRETE = {
    g.THUMBS_UP: Action("volume", (VOLUME_STEP,), "Volume up"),
    g.THUMBS_DOWN: Action("volume", (-VOLUME_STEP,), "Volume down"),
    g.POINT_RIGHT: key(KEY_RIGHT, "Right arrow"),
    g.POINT_LEFT: key(KEY_LEFT, "Left arrow"),
    g.PINCH: key(KEY_SPACE, "Space"),
    g.CALL_ME: key(KEY_TAB, "Previous app", CMD),
}

# Same directions as the three-finger trackpad swipe.
SWIPES = {
    "left": key(KEY_RIGHT, "Next desktop", CTRL),
    "right": key(KEY_LEFT, "Previous desktop", CTRL),
    "up": key(KEY_UP, "Mission Control", CTRL),
    "down": key(KEY_DOWN, "App windows", CTRL),
}

ZOOM_IN = key(KEY_EQUAL, "Zoom in", CMD)
ZOOM_OUT = key(KEY_MINUS, "Zoom out", CMD)


class SwipeDetector:
    """Spots a fast open-palm movement in one direction."""

    def __init__(self, window=0.4, distance=1.4, cooldown=1.0, grace=0.15):
        self.window = window        # seconds of movement considered
        self.distance = distance    # in hand sizes
        self.cooldown = cooldown    # ignore the hand coming back after a swipe
        self.grace = grace          # tolerate the palm being missed for a frame or two
        self.track = deque()
        self.block_until = 0.0

    def reset(self):
        self.track.clear()

    def update(self, center, size, now):
        """Feed the palm centre (None when no open palm); return a direction or None."""
        if center is None:
            if self.track and now - self.track[-1][0] > self.grace:
                self.track.clear()
            return None
        self.track.append((now, center))
        while now - self.track[0][0] > self.window:
            self.track.popleft()
        if now < self.block_until:
            return None
        start = self.track[0][1]
        dx = (center[0] - start[0]) / size
        dy = (center[1] - start[1]) / size
        if max(abs(dx), abs(dy)) < self.distance:
            return None
        if abs(dx) > 2 * abs(dy):
            direction = "right" if dx > 0 else "left"
        elif abs(dy) > 2 * abs(dx):
            direction = "down" if dy > 0 else "up"
        else:
            return None  # diagonal
        self.track.clear()
        self.block_until = now + self.cooldown
        return direction


class Scroller:
    """Turns vertical hand movement into scroll amounts."""

    def __init__(self, gain=3.0, deadzone=0.03):
        self.gain = gain
        self.deadzone = deadzone  # in hand sizes, so a still hand does not scroll
        self.prev = None

    def reset(self):
        self.prev = None

    def update(self, y, size):
        if self.prev is None:
            self.prev = y
            return 0
        dy = y - self.prev
        if abs(dy) < self.deadzone * size:
            return 0
        self.prev = y
        return int(round(-dy * self.gain))  # hand up -> page moves up


class OneEuroFilter:
    """Smooths a jittery signal while staying responsive to fast moves (Casiez et al., 2012)."""

    def __init__(self, min_cutoff=0.8, beta=6.0, d_cutoff=1.0):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.reset()

    def reset(self):
        self.t = self.x = None
        self.dx = 0.0

    @staticmethod
    def _alpha(dt, cutoff):
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x, t):
        if self.t is None:
            self.t, self.x = t, x
            return x
        dt = max(t - self.t, 1e-3)
        self.t = t
        a_d = self._alpha(dt, self.d_cutoff)
        self.dx = a_d * (x - self.x) / dt + (1 - a_d) * self.dx
        a = self._alpha(dt, self.min_cutoff + self.beta * abs(self.dx))
        self.x = a * x + (1 - a) * self.x
        return self.x


class MouseHand:
    """Mouse mode: the palm moves the cursor, pinches click."""

    # Part of the camera picture mapped onto the whole screen, so the hand
    # can reach the screen edges without leaving the camera's view.
    REGION = (0.2, 0.15, 0.8, 0.75)  # left, top, right, bottom
    PRESS, RELEASE = 0.30, 0.45      # pinch hysteresis, in hand sizes
    CLICK_FREEZE = 0.25              # hold the cursor still right after pressing, for clean clicks
    DOUBLE_CLICK = 0.45

    def __init__(self):
        self.fx, self.fy = OneEuroFilter(), OneEuroFilter()
        self.scroller = Scroller()
        self.pressed = False
        self.right_pressed = False
        self.pressed_at = 0.0
        self.last_click_at = -1.0
        self.clicks = 1

    def release(self):
        """Let go of any held button (hand lost, mode changed)."""
        self.fx.reset()
        self.fy.reset()
        self.scroller.reset()
        self.right_pressed = False
        if self.pressed:
            self.pressed = False
            return [Action("button", ("left", False, self.clicks), None)]
        return []

    def update(self, hand, shape, frame_size, now):
        if hand is None:
            return self.release()
        w, h = frame_size
        x0, y0, x1, y1 = self.REGION
        cx, cy = g.palm_center(hand.pts)
        nx = min(max((cx / w - x0) / (x1 - x0), 0.0), 1.0)
        ny = min(max((cy / h - y0) / (y1 - y0), 0.0), 1.0)
        sx, sy = self.fx(nx, now), self.fy(ny, now)
        index_gap = g.pinch_ratio(hand.pts, 8)
        middle_gap = g.pinch_ratio(hand.pts, 12)
        actions = []

        if not self.pressed and index_gap < self.PRESS:
            self.pressed = True
            self.pressed_at = now
            self.clicks = 2 if now - self.last_click_at < self.DOUBLE_CLICK else 1
            self.last_click_at = now
            actions.append(Action("button", ("left", True, self.clicks),
                                  "Double click" if self.clicks == 2 else "Click"))
        elif self.pressed and index_gap > self.RELEASE:
            self.pressed = False
            actions.append(Action("button", ("left", False, self.clicks), None))

        if not self.right_pressed and not self.pressed and middle_gap < self.PRESS and index_gap > self.RELEASE:
            self.right_pressed = True
            actions.append(Action("button", ("right", True, 1), "Right click"))
            actions.append(Action("button", ("right", False, 1), None))
        elif self.right_pressed and middle_gap > self.RELEASE:
            self.right_pressed = False

        if shape == g.VICTORY and not self.pressed:
            amount = self.scroller.update(cy, g.hand_size(hand.pts))
            if amount:
                actions.append(Action("scroll", (amount,), "Scroll"))
            return actions  # the cursor stays put while scrolling
        self.scroller.reset()

        if not (self.pressed and now - self.pressed_at < self.CLICK_FREEZE):
            actions.append(Action("move", (sx, sy, self.pressed), None))
        return actions


class Controller:
    def __init__(self):
        self.mode = CONTROL
        self.trigger = g.GestureTrigger(repeating=(g.THUMBS_UP, g.THUMBS_DOWN))
        self.swipe = SwipeDetector()
        self.scroller = Scroller()
        self.mouse = MouseHand()
        self.zoom_anchor = None
        self.toggle_since = None
        self.toggle_armed = True
        self.shapes = []  # shape of each hand in the last frame, for display

    def toggle_mode(self):
        actions = self.mouse.release()
        self.mode = MOUSE if self.mode == CONTROL else CONTROL
        self.trigger = g.GestureTrigger(repeating=(g.THUMBS_UP, g.THUMBS_DOWN))
        self.swipe.reset()
        self.scroller.reset()
        label = "Mouse mode" if self.mode == MOUSE else "Control mode"
        return actions + [Action("mode", (self.mode,), label)]

    @staticmethod
    def primary(hands):
        """One-hand gestures use the right hand when both are visible."""
        for hand in hands:
            if hand.label == "Right":
                return hand
        return hands[0] if hands else None

    def update(self, hands, frame_size, now):
        """Feed the hands seen at time `now`; return the actions to perform."""
        self.shapes = [g.classify(h.pts) for h in hands]

        if len(hands) == 2:
            actions = self._two_hands(hands, now)
            if actions is not None:  # a two-hand gesture is in progress
                self.trigger.update(None, now)
                self.swipe.reset()
                self.scroller.reset()
                return actions + (self.mouse.release() if self.mode == MOUSE else [])
        else:
            self.zoom_anchor = None
            self.toggle_since = None
            self.toggle_armed = True

        hand = self.primary(hands)
        shape = self.shapes[hands.index(hand)] if hand else None
        if self.mode == MOUSE:
            return self.mouse.update(hand, shape, frame_size, now)
        return self._control(hand, shape, now)

    def _two_hands(self, hands, now):
        """Both hands showing ✌️ (switch mode) or ✋ (zoom). None when neither."""
        both = self.shapes[0] if self.shapes[0] == self.shapes[1] else None

        if both == g.VICTORY:
            self.zoom_anchor = None
            if self.toggle_since is None:
                self.toggle_since = now
            if self.toggle_armed and now - self.toggle_since >= 1.0:
                self.toggle_armed = False
                return self.toggle_mode()
            return []
        self.toggle_since = None
        self.toggle_armed = True

        if both == g.OPEN_PALM:
            a, b = (g.palm_center(h.pts) for h in hands)
            size = (g.hand_size(hands[0].pts) + g.hand_size(hands[1].pts)) / 2
            spread = math.hypot(a[0] - b[0], a[1] - b[1]) / size
            if self.zoom_anchor is None:
                self.zoom_anchor = spread
            elif spread - self.zoom_anchor >= 0.7:
                self.zoom_anchor = spread
                return [ZOOM_IN]
            elif self.zoom_anchor - spread >= 0.7:
                self.zoom_anchor = spread
                return [ZOOM_OUT]
            return []
        self.zoom_anchor = None
        return None

    def _control(self, hand, shape, now):
        actions = []
        fired = self.trigger.update(shape if shape in DISCRETE else None, now)
        if fired:
            actions.append(DISCRETE[fired])

        if hand is None:
            self.swipe.update(None, 1.0, now)
            self.scroller.reset()
            return actions

        size = g.hand_size(hand.pts)
        center = g.palm_center(hand.pts)
        direction = self.swipe.update(center if shape == g.OPEN_PALM else None, size, now)
        if direction:
            actions.append(SWIPES[direction])

        if shape == g.VICTORY:
            amount = self.scroller.update(center[1], size)
            if amount:
                actions.append(Action("scroll", (amount,), "Scroll"))
        else:
            self.scroller.reset()
        return actions
