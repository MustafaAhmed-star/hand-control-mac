"""Gesture recognition from MediaPipe hand landmarks.

Pure logic with no camera or OS dependencies, so it can be unit tested.

Landmark indices (MediaPipe hand model):
    0 wrist
    1-4   thumb   (cmc, mcp, ip, tip)
    5-8   index   (mcp, pip, dip, tip)
    9-12  middle
    13-16 ring
    17-20 pinky
"""

import math

THUMBS_UP = "thumbs_up"
THUMBS_DOWN = "thumbs_down"
POINT_LEFT = "point_left"
POINT_RIGHT = "point_right"
PINCH = "pinch"

# A gesture's direction must be within this many degrees of straight
# up/down/left/right; diagonal hands are ignored on purpose.
MAX_TILT_DEG = 35
# Thumb and index tips closer than this fraction of the hand size count as a pinch.
PINCH_RATIO = 0.28


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _angle_deg(a, b):
    """Angle of the vector a->b in degrees: 0 = right, 90 = up, -90 = down, 180 = left."""
    return math.degrees(math.atan2(-(b[1] - a[1]), b[0] - a[0]))


def _near(angle, target):
    diff = (angle - target + 180) % 360 - 180
    return abs(diff) <= MAX_TILT_DEG


def _extended(pts, pip, tip):
    """A finger is extended when its tip is clearly farther from the wrist than its middle joint."""
    return _dist(pts[0], pts[tip]) > _dist(pts[0], pts[pip]) * 1.15


def _curled(pts, pip, tip):
    return _dist(pts[0], pts[tip]) < _dist(pts[0], pts[pip]) * 1.05


def classify(pts):
    """Return the gesture shown by one hand, or None.

    `pts` is a list of 21 (x, y) points in pixel units, y pointing down,
    taken from an already mirrored frame so "right" is the user's right.
    """
    if len(pts) != 21:
        return None
    hand_size = _dist(pts[0], pts[9])
    if hand_size < 1e-6:
        return None

    others_curled = all(_curled(pts, pip, tip) for pip, tip in ((10, 12), (14, 16), (18, 20)))

    # Pinch: thumb and index tips touching, index tip out in front of its
    # knuckle (so a closed fist does not count).
    if (_dist(pts[4], pts[8]) < hand_size * PINCH_RATIO
            and _dist(pts[0], pts[8]) > _dist(pts[0], pts[5])):
        return PINCH

    # Thumbs up/down: fist with only the thumb sticking out vertically.
    index_curled = _curled(pts, 6, 8)
    thumb_len = _dist(pts[2], pts[4])
    if others_curled and index_curled and thumb_len > hand_size * 0.45:
        angle = _angle_deg(pts[2], pts[4])
        if _near(angle, 90):
            return THUMBS_UP
        if _near(angle, -90):
            return THUMBS_DOWN

    # Pointing: only the index finger out, held horizontally.
    if others_curled and _extended(pts, 6, 8):
        angle = _angle_deg(pts[5], pts[8])
        if _near(angle, 0):
            return POINT_RIGHT
        if _near(angle, 180):
            return POINT_LEFT

    return None


class GestureTrigger:
    """Turns noisy per-frame gestures into actions.

    A gesture fires only after it has been held for `hold` seconds. Volume
    gestures repeat every `repeat` seconds while held; the others fire once
    per gesture and need the hand to change before firing again.
    """

    REPEATING = {THUMBS_UP, THUMBS_DOWN}

    def __init__(self, hold=0.3, repeat=0.25, release=0.15):
        self.hold = hold
        self.repeat = repeat
        self.release = release
        self.active = None  # gesture currently considered held
        self._candidate = None
        self._candidate_since = 0.0
        self._last_fire = None

    def update(self, gesture, now):
        """Feed the gesture seen at time `now`; return a gesture to act on, or None."""
        if gesture != self._candidate:
            self._candidate = gesture
            self._candidate_since = now

        needed = self.release if gesture is None else self.hold
        if self._candidate != self.active and now - self._candidate_since >= needed:
            self.active = self._candidate
            self._last_fire = None

        if self.active is None:
            return None
        if self._last_fire is None:
            self._last_fire = now
            return self.active
        if self.active in self.REPEATING and now - self._last_fire >= self.repeat:
            self._last_fire = now
            return self.active
        return None
