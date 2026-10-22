"""Type on the emulator's keyboard by tapping its keys (adb -s emulator-5554 input tap), so the text
goes through Varnelė Klaviatūra like a finger's: autocorrect, the sentence fixer, learning.

    python3 eval/emulator_type.py "mano drakonas valgo morkas. "

Letters a-z (typed without diacritics; the keyboard adds them), space, `.` and `,`, `<` = backspace,
`\\n` = enter. Key centres are the Pixel 7 AVD's (1080x2400, number row on, Lithuanian QWERTY);
another screen or layout needs new ones (a screenshot: adb exec-out screencap -p > s.png).
"""

import os
import subprocess
import sys
import time

ADB = ["perl", "-e", "alarm 30; exec @ARGV", os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"),
       "-s", "emulator-5554"]
KEYS = {}
for i, c in enumerate("qwertyuiop"):
    KEYS[c] = (54 + 108 * i, 1767)
for i, c in enumerate("asdfghjkl"):
    KEYS[c] = (108 + 108 * i, 1905)
for i, c in enumerate("zxcvbnm"):
    KEYS[c] = (216 + 108 * i, 2043)
KEYS.update({" ": (648, 2181), ".": (864, 2181), ",": (216, 2181), "\n": (998, 2181), "<": (998, 2043)})


def tap(c, pause=0.25):
    x, y = KEYS[c]
    subprocess.run(ADB + ["shell", "input", "tap", str(x), str(y)], check=True)
    time.sleep(pause)    # a faster typist than this outruns the suggestion updates


def main():
    for c in sys.argv[1]:
        tap(c.lower())
    time.sleep(1)


if __name__ == "__main__":
    main()
