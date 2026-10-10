import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import gestures as g  # noqa: E402


def finger(x, extended):
    """MCP, PIP, DIP, TIP for an upright finger (y grows downwards, wrist at origin)."""
    if extended:
        return [(x, -60), (x, -90), (x, -110), (x, -130)]
    return [(x, -60), (x, -85), (x, -70), (x, -55)]


def hand(index=False, middle=False, ring=False, pinky=False, thumb=None, index_pts=None):
    thumb = thumb or [(-20, -15), (-35, -30), (-45, -45), (-55, -60)]
    pts = [(0, 0)] + thumb
    pts += index_pts or finger(-20, index)
    pts += finger(-5, middle) + finger(10, ring) + finger(25, pinky)
    return pts


def rotate(pts, degrees):
    """Rotate a hand around the wrist; positive turns it clockwise on screen."""
    a = math.radians(degrees)
    return [(x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)) for x, y in pts]


THUMB_UP = [(-20, -15), (-30, -40), (-30, -65), (-30, -90)]


class ClassifyTest(unittest.TestCase):
    def test_thumbs_up_and_down(self):
        fist = hand(thumb=THUMB_UP)
        self.assertEqual(g.classify(fist), g.THUMBS_UP)
        self.assertEqual(g.classify(rotate(fist, 180)), g.THUMBS_DOWN)

    def test_pointing_left_and_right(self):
        point = hand(index=True)
        self.assertEqual(g.classify(rotate(point, 90)), g.POINT_RIGHT)
        self.assertEqual(g.classify(rotate(point, -90)), g.POINT_LEFT)

    def test_diagonal_is_ignored(self):
        self.assertIsNone(g.classify(rotate(hand(thumb=THUMB_UP), 45)))
        self.assertIsNone(g.classify(rotate(hand(index=True), 45)))

    def test_pinch(self):
        index = [(-20, -60), (-25, -90), (-35, -95), (-38, -80)]
        thumb = [(-20, -15), (-35, -30), (-40, -55), (-40, -75)]
        self.assertEqual(g.classify(hand(thumb=thumb, index_pts=index)), g.PINCH)

    def test_open_hand_and_fist_do_nothing(self):
        self.assertIsNone(g.classify(hand(True, True, True, True)))
        tucked_thumb = [(-20, -15), (-30, -35), (-20, -50), (-10, -55)]
        self.assertIsNone(g.classify(hand(thumb=tucked_thumb)))

    def test_bad_input(self):
        self.assertIsNone(g.classify([]))
        self.assertIsNone(g.classify([(0, 0)] * 21))


class TriggerTest(unittest.TestCase):
    def run_frames(self, trigger, gesture, start, end, step=1 / 30):
        fired = []
        t = start
        while t < end:
            out = trigger.update(gesture, t)
            if out:
                fired.append((round(t, 2), out))
            t += step
        return fired

    def test_needs_hold_before_firing(self):
        t = g.GestureTrigger(hold=0.3)
        self.assertEqual(self.run_frames(t, g.PINCH, 0, 0.25), [])
        self.assertEqual(len(self.run_frames(t, g.PINCH, 0.25, 0.4)), 1)

    def test_pinch_fires_once_per_gesture(self):
        t = g.GestureTrigger()
        self.assertEqual(len(self.run_frames(t, g.PINCH, 0, 3)), 1)
        self.run_frames(t, None, 3, 3.5)
        self.assertEqual(len(self.run_frames(t, g.PINCH, 3.5, 4.5)), 1)

    def test_volume_repeats_while_held(self):
        t = g.GestureTrigger(hold=0.3, repeat=0.25)
        times = [at for at, _ in self.run_frames(t, g.THUMBS_UP, 0, 2)]
        self.assertGreaterEqual(len(times), 6)
        self.assertGreaterEqual(times[0], 0.3)
        gaps = [b - a for a, b in zip(times, times[1:])]
        self.assertTrue(all(0.24 <= gap < 0.35 for gap in gaps), gaps)

    def test_brief_dropout_does_not_refire(self):
        t = g.GestureTrigger()
        self.run_frames(t, g.POINT_RIGHT, 0, 1)
        self.run_frames(t, None, 1, 1.05)  # tracking lost for one or two frames
        self.assertEqual(self.run_frames(t, g.POINT_RIGHT, 1.05, 2), [])


if __name__ == "__main__":
    unittest.main()
