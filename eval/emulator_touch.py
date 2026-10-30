"""Touch the emulator through its console (localhost:5554), in real time: a tap takes 0.1 s, a swipe
runs at finger speed, unlike `adb shell input` (0.3 s per call, a process each). Used to record demos.

    from emulator_touch import Touch
    t = Touch()
    t.type("pries pora dienu ")      # letters, space, `.`, `,`, `<` = backspace
    t.type("ąčėįšųž?!")              # a long press takes these: the popup's preselected letter
    t.long_press("e", (378, 1570))   # hold a key, slide to a popup letter at that point
    t.swipe("kodel")                 # gesture over the word's keys
    t.point(540, 530)                # any screen point

Key centres are the Pixel 7 AVD's, as in emulator_type.py.
"""

import math
import os
import random
import socket
import time

KEYS = {}
for i, c in enumerate("qwertyuiop"):
    KEYS[c] = (54 + 108 * i, 1767)
for i, c in enumerate("asdfghjkl"):
    KEYS[c] = (108 + 108 * i, 1905)
for i, c in enumerate("zxcvbnm"):
    KEYS[c] = (216 + 108 * i, 2043)
KEYS.update({" ": (648, 2181), ".": (864, 2181), ",": (216, 2181), "\n": (998, 2181), "<": (998, 2043),
             "^": (80, 2043)})
HELD = {"ą": "a", "č": "c", "ė": "e", "į": "i", "š": "s", "ų": "u", "ž": "z", "?": "m", "!": "n"}    # a key's preselected popup letter


class Touch:
    def __init__(self, port=5554, seed=1):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=3)
        self.s.recv(4096)
        token = open(os.path.expanduser("~/.emulator_console_auth_token")).read().strip()
        self._send(f"auth {token}")
        self.rng = random.Random(seed)

    def _send(self, command):
        self.s.sendall(command.encode() + b"\n")
        buf = b""
        while not buf.endswith(b"OK\r\n") and b"KO" not in buf:
            buf += self.s.recv(4096)

    def _mouse(self, x, y, down):
        self._send(f"event mouse {round(x)} {round(y)} 0 {1 if down else 0}")

    def point(self, x, y, hold=0.06):
        self._mouse(x, y, True)
        time.sleep(hold)
        self._mouse(x, y, False)

    def type(self, text, cps=6.0):
        """Tap the keys at cps characters a second, with a typist's small unevenness."""
        for c in text:
            if c in HELD:
                self.hold(HELD[c])
                time.sleep(1 / cps)
                continue
            x, y = KEYS[c.lower()]
            start = time.time()
            self.point(x + self.rng.gauss(0, 7), y + self.rng.gauss(0, 7))
            gap = self.rng.uniform(0.75, 1.25) / cps
            time.sleep(max(0, gap - (time.time() - start)))

    def hold(self, key, seconds=0.5):
        """Long-press a key and let go: its popup's preselected letter."""
        x, y = KEYS[key]
        self._mouse(x, y, True)
        time.sleep(seconds)
        self._mouse(x, y, False)

    def long_press(self, key, to, hold=0.55):
        """Hold key until its popup opens, slide to the point `to` (x, y) and let go."""
        x, y = KEYS[key]
        self._mouse(x, y, True)
        time.sleep(hold)
        self._mouse((x + to[0]) / 2, (y + to[1]) / 2, True)
        time.sleep(0.04)
        self._mouse(to[0], to[1], True)
        time.sleep(0.12)
        self._mouse(to[0], to[1], False)

    def swipe(self, word, seconds=None, noise=14):
        """Drag a curve through the word's keys, a doubled letter once, slightly off the centres."""
        pts = []
        for c in word.lower():
            p = KEYS[c]
            if not pts or pts[-1] != p:
                pts.append((p[0] + self.rng.gauss(0, noise), p[1] + self.rng.gauss(0, noise)))
        path = _catmull_rom(pts)
        length = sum(math.dist(a, b) for a, b in zip(path, path[1:]))
        seconds = seconds or max(0.45, length / 1500)
        step = seconds / len(path)
        self._mouse(*path[0], True)
        time.sleep(0.04)
        for p in path[1:]:
            start = time.time()
            self._mouse(*p, True)
            time.sleep(max(0, step - (time.time() - start)))
        self._mouse(*path[-1], False)


def _catmull_rom(pts, per_segment=7):
    if len(pts) == 1:
        return pts + [(pts[0][0] + 1, pts[0][1])]
    ctrl = [pts[0]] + pts + [pts[-1]]
    out = []
    for i in range(1, len(ctrl) - 2):
        p0, p1, p2, p3 = ctrl[i - 1:i + 3]
        for k in range(per_segment):
            t = k / per_segment
            out.append(tuple(
                0.5 * (2 * p1[a] + (p2[a] - p0[a]) * t + (2 * p0[a] - 5 * p1[a] + 4 * p2[a] - p3[a]) * t * t
                       + (3 * p1[a] - p0[a] - 3 * p2[a] + p3[a]) * t * t * t)
                for a in (0, 1)))
    out.append(pts[-1])
    return out
