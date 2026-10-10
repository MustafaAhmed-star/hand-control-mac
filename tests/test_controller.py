import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import controller as c  # noqa: E402
from test_gestures import THUMB_UP, hand, rotate  # noqa: E402

FRAME = (960, 540)
FPS = 30
OPEN = hand(True, True, True, True)
PEACE = hand(index=True, middle=True)
PINCH = hand(thumb=[(-20, -15), (-35, -30), (-40, -55), (-40, -75)],
             index_pts=[(-20, -60), (-25, -90), (-35, -95), (-38, -80)])
RIGHT_PINCH = OPEN[:9] + [(-5, -60), (-10, -90), (-30, -90), (-50, -65)] + OPEN[13:]


def at(pts, x, y):
    return [(px + x, py + y) for px, py in pts]


def run(ctrl, frames, start=0.0):
    """frames: list of hand lists, one per frame at 30 fps. Returns (time, action) pairs."""
    out = []
    for i, hands in enumerate(frames):
        now = start + i / FPS
        out += [(now, a) for a in ctrl.update(hands, FRAME, now)]
    return out


def moving(pts, x0, y0, x1, y1, seconds, label="Right"):
    n = max(int(seconds * FPS), 1)
    return [[c.Hand(label, at(pts, x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n))] for i in range(n + 1)]


def labels(out):
    return [a.label for _, a in out if a.label]


class SwipeTest(unittest.TestCase):
    def test_swipe_left_moves_to_next_desktop_once(self):
        ctrl = c.Controller()
        out = run(ctrl, moving(OPEN, 650, 400, 400, 400, 0.3) + moving(OPEN, 400, 400, 650, 400, 0.3))
        self.assertEqual(labels(out), ["Next desktop"])
        key = [a for _, a in out if a.label][0]
        self.assertEqual(key.args, (c.KEY_RIGHT, (c.CTRL,)))

    def test_swipe_right_and_up(self):
        self.assertEqual(labels(run(c.Controller(), moving(OPEN, 300, 400, 550, 400, 0.3))), ["Previous desktop"])
        self.assertEqual(labels(run(c.Controller(), moving(OPEN, 480, 480, 480, 230, 0.3))), ["Mission Control"])

    def test_slow_drift_and_still_hand_do_nothing(self):
        self.assertEqual(labels(run(c.Controller(), moving(OPEN, 650, 400, 400, 400, 3.0))), [])
        self.assertEqual(labels(run(c.Controller(), moving(OPEN, 500, 400, 500, 400, 2.0))), [])

    def test_diagonal_swipe_is_ignored(self):
        self.assertEqual(labels(run(c.Controller(), moving(OPEN, 650, 450, 450, 250, 0.3))), [])


class ControlModeTest(unittest.TestCase):
    def test_peace_sign_scrolls_with_the_hand(self):
        out = run(c.Controller(), moving(PEACE, 480, 450, 480, 300, 1.0))
        scrolls = [a.args[0] for _, a in out if a.kind == "scroll"]
        self.assertTrue(scrolls)
        self.assertTrue(all(s > 0 for s in scrolls))  # hand up -> page moves up

    def test_thumbs_up_repeats_volume(self):
        out = run(c.Controller(), moving(hand(thumb=THUMB_UP), 480, 400, 480, 400, 1.5))
        self.assertGreaterEqual(labels(out).count("Volume up"), 4)

    def test_right_hand_wins_when_both_are_visible(self):
        frames = [[c.Hand("Left", at(rotate(hand(index=True), 90), 300, 400)),
                   c.Hand("Right", at(hand(thumb=THUMB_UP), 650, 400))]] * 15
        self.assertEqual(labels(run(c.Controller(), frames)), ["Volume up"])


class TwoHandTest(unittest.TestCase):
    def palms(self, gap0, gap1, seconds):
        n = int(seconds * FPS)
        frames = []
        for i in range(n + 1):
            gap = gap0 + (gap1 - gap0) * i / n
            frames.append([c.Hand("Left", at(OPEN, 480 - gap / 2, 400)),
                           c.Hand("Right", at(OPEN, 480 + gap / 2, 400))])
        return frames

    def test_spreading_palms_zooms_in_without_switching_desktops(self):
        out = labels(run(c.Controller(), self.palms(150, 450, 0.5)))
        self.assertIn("Zoom in", out)
        self.assertEqual(set(out), {"Zoom in"})

    def test_closing_palms_zooms_out(self):
        self.assertIn("Zoom out", labels(run(c.Controller(), self.palms(450, 150, 0.5))))

    def test_both_peace_signs_toggle_mouse_mode_once(self):
        ctrl = c.Controller()
        both = [[c.Hand("Left", at(PEACE, 300, 400)), c.Hand("Right", at(PEACE, 650, 400))]]
        out = labels(run(ctrl, both * 75))  # held for 2.5 s
        self.assertEqual(out, ["Mouse mode"])
        self.assertEqual(ctrl.mode, c.MOUSE)
        run(ctrl, [[]] * 5, start=3)
        self.assertEqual(labels(run(ctrl, both * 40, start=4)), ["Control mode"])
        self.assertEqual(ctrl.mode, c.CONTROL)


class MouseModeTest(unittest.TestCase):
    def mouse(self):
        ctrl = c.Controller()
        ctrl.toggle_mode()
        return ctrl

    def test_hand_moves_the_cursor(self):
        out = run(self.mouse(), moving(OPEN, 300, 300, 650, 300, 1.0))
        xs = [a.args[0] for _, a in out if a.kind == "move"]
        self.assertGreater(xs[-1], xs[0] + 0.3)
        self.assertTrue(all(0 <= x <= 1 for x in xs))

    def test_pinch_clicks_and_double_clicks(self):
        ctrl = self.mouse()
        still = lambda pts, n: [[c.Hand("Right", at(pts, 480, 400))]] * n  # noqa: E731
        out = run(ctrl, still(OPEN, 5) + still(PINCH, 4) + still(OPEN, 4) + still(PINCH, 4) + still(OPEN, 4))
        buttons = [a.args for _, a in out if a.kind == "button"]
        self.assertEqual(buttons, [("left", True, 1), ("left", False, 1), ("left", True, 2), ("left", False, 2)])

    def test_cursor_holds_still_right_after_pressing(self):
        ctrl = self.mouse()
        frames = [[c.Hand("Right", at(OPEN, 480, 400))]] * 5 + moving(PINCH, 480, 400, 600, 400, 0.5)
        out = run(ctrl, frames)
        down_at = next(t for t, a in out if a.kind == "button")
        early_moves = [a for t, a in out if a.kind == "move" and down_at < t < down_at + 0.2]
        late_drags = [a for t, a in out if a.kind == "move" and t > down_at + 0.3]
        self.assertEqual(early_moves, [])
        self.assertTrue(late_drags and all(a.args[2] for a in late_drags))  # dragging

    def test_losing_the_hand_releases_the_button(self):
        ctrl = self.mouse()
        out = run(ctrl, [[c.Hand("Right", at(PINCH, 480, 400))]] * 5 + [[]])
        self.assertEqual(out[-1][1].args, ("left", False, 1))

    def test_thumb_to_middle_is_right_click(self):
        ctrl = self.mouse()
        out = run(ctrl, [[c.Hand("Right", at(OPEN, 480, 400))]] * 3 + [[c.Hand("Right", at(RIGHT_PINCH, 480, 400))]] * 5)
        self.assertEqual([a.args for _, a in out if a.kind == "button"],
                         [("right", True, 1), ("right", False, 1)])


if __name__ == "__main__":
    unittest.main()
