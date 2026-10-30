"""Record the keyboard's demo videos on the emulator, typed in Google Messages by scripted touches.

    eval/emulator_ready.sh app.apk
    ROUND=2 python3 eval/demo_videos.py setup          # contacts, Lithuanian Messages, clean status bar
    python3 eval/demo_videos.py try zodziai            # run a scene, print what ended up in the field
    python3 eval/demo_videos.py record zodziai DIR     # the same, recorded to DIR/raw/zodziai.mp4
    python3 eval/demo_videos.py compose zodziai DIR    # add the captions (needs Pillow) -> DIR/final/zodziai.mp4

The system spell checker is switched off (the emulator's is Gboard's English one, which would underline
all Lithuanian): every red underline in the videos is the keyboard's own.
"""

import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from emulator_touch import Touch

ADB = [os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"), "-s", "emulator-5554"]
ROUND = int(os.environ.get("ROUND", 1))      # a fresh chat each round: sent messages can't be deleted from adb
SEND = (985, 1368)
STRIP = {"left": (250, 1505), "centre": (570, 1505), "right": (900, 1505)}
CONTACTS = {"zodziai": ("Draugas", 1), "diakritikai": ("Rūta", 2), "gramatika": ("Tomas", 3),
            "spejimas": ("Mama", 4), "braukimas": ("Jonas", 5)}


def adb(*args, check=True):
    return subprocess.run(ADB + list(args), check=check, capture_output=True, text=True).stdout


def number(i):
    return f"+3706000{ROUND:02d}{i:02d}"


def setup():
    adb("shell", "settings", "put", "secure", "spell_checker_enabled", "0")
    adb("shell", "settings", "put", "system", "show_touches", "1")
    adb("shell", "cmd", "locale", "set-app-locales", "com.google.android.apps.messaging", "--user", "0", "--locales", "lt")
    have = adb("shell", "content", "query", "--uri", "content://com.android.contacts/data/phones",
               "--projection", "data1")
    for name, i in CONTACTS.values():
        if number(i) in have:
            continue
        adb("shell", "content", "insert", "--uri", "content://com.android.contacts/raw_contacts",
            "--bind", "account_type:n:", "--bind", "account_name:n:")
        rid = re.findall(r"_id=(\d+)", adb("shell", "content", "query", "--uri",
                                           "content://com.android.contacts/raw_contacts", "--projection", "_id"))[-1]
        data = ["shell", "content", "insert", "--uri", "content://com.android.contacts/data",
                "--bind", f"raw_contact_id:i:{rid}"]
        adb(*data, "--bind", "mimetype:s:vnd.android.cursor.item/name", "--bind", f"data1:s:'{name}'")
        adb(*data, "--bind", "mimetype:s:vnd.android.cursor.item/phone_v2", "--bind", f"data1:s:{number(i)}",
            "--bind", "data2:i:2")
    adb("shell", "settings", "put", "global", "sysui_demo_allowed", "1")
    demo = ["shell", "am", "broadcast", "-a", "com.android.systemui.demo", "-e", "command"]
    adb(*demo, "enter")
    adb(*demo, "clock", "-e", "hhmm", time.strftime("%H%M"))
    adb(*demo, "battery", "-e", "level", "100", "-e", "plugged", "false")
    adb(*demo, "network", "-e", "wifi", "show", "-e", "level", "4", "-e", "fully", "true")
    adb(*demo, "network", "-e", "mobile", "show", "-e", "datatype", "none", "-e", "level", "4")
    adb(*demo, "notifications", "-e", "visible", "false")


def forget():
    """What rehearsals taught the keyboard goes: the words learned, HeliBoard's user history."""
    keyboard = "dev.imbrasas.varnele.keyboard.debug"
    adb("shell", "am", "force-stop", keyboard)
    adb("shell", f"run-as {keyboard} rm -rf files/varnele_user.txt files/UserHistoryDictionary.lt.dict", check=False)
    adb("shell", "ime", "set", f"{keyboard}/helium314.keyboard.latin.LatinIME")      # a stopped keyboard loses the field


def open_chat(scene):
    _, i = CONTACTS[scene]
    forget()
    adb("shell", "am", "force-stop", "com.google.android.apps.messaging")
    adb("shell", "am", "start", "-a", "android.intent.action.SENDTO", "-d", f"sms:{number(i)}")
    time.sleep(3)
    adb("shell", "input", "tap", "500", "2252")     # the message field
    time.sleep(1.5)


def field():
    """The compose field's text."""
    adb("shell", "uiautomator", "dump", "/sdcard/ui.xml", check=False)
    xml = adb("shell", "cat", "/sdcard/ui.xml")
    m = re.findall(r'text="([^"]*)"[^>]*class="android\.widget\.EditText"', xml)
    return m[0] if m else "?"


def zodziai(t):
    t.caption("Žino net tokius žodžius")
    time.sleep(2)
    t.type("paprasčiausiuosiuose vienkiemiuose bebėgiodamas apstatydavau automobilių ratų užraktus.", cps=7)
    t.caption("Nė vieno raudono pabraukimo")
    time.sleep(3)
    t.point(*SEND)
    time.sleep(1)
    t.caption("Net ilgiausias žodis, surinktas be varnelių")
    t.type("nebeprisikiskiakopusteliaudavome.", cps=7)
    time.sleep(3)
    t.point(*SEND)
    time.sleep(1)
    t.caption("O nesąmonę pabraukia")
    t.type("bet sirdgv jau ne zodis. ", cps=6)
    time.sleep(3.5)


def diakritikai(t):
    t.caption("Rašai be varnelių ir nosinių, jas sudeda klaviatūra")
    time.sleep(2)
    t.type("pries pora dienu ", cps=5)
    t.caption("Šnekamoji kalba nėra klaida")
    t.type("buvom mokykloj.", cps=5)
    time.sleep(2.5)
    t.point(*SEND)
    time.sleep(1.8)
    t.caption("Taiso rašybos klaidas, sudeda kablelius")
    t.type("kodel nepataiso visu zodzou kuriu as rasau? ", cps=5)
    time.sleep(3.5)


def gramatika(t):
    t.caption("Supranta gramatiką")
    time.sleep(2)
    t.type("visa sita isterija ", cps=5)
    time.sleep(1)
    t.caption("Veiksmažodis pataiso ankstesnių žodžių linksnį")
    t.type("maciau vakar.", cps=5)
    time.sleep(3)
    t.point(*SEND)
    time.sleep(1)
    t.caption("Derina giminę, skaičių ir linksnį")
    t.type("ant stalo guli viena nukritusia sagute.", cps=5)
    time.sleep(3)
    t.point(*SEND)
    time.sleep(1)
    t.type("tie grazus didele namai. ", cps=5)
    time.sleep(3.5)


def spejimas(t):
    t.caption("Spėja kitą žodį")
    time.sleep(2)
    t.type("labas, kaip ", cps=5)
    time.sleep(2)
    t.point(*STRIP["centre"])      # sekasi
    time.sleep(0.9)
    t.type("? ", cps=4)
    time.sleep(1)
    t.caption("Užbaigia pradėtą žodį")
    t.type("kod", cps=4)
    time.sleep(1.8)
    t.point(*STRIP["right"])       # the ghost: kodėl
    time.sleep(0.9)
    t.type("nerasai?", cps=5)
    time.sleep(1.5)
    t.point(*SEND)
    time.sleep(1)
    t.caption("Po prielinksnio siūlo tinkamą linksnį")
    t.type("einu i ", cps=5)
    time.sleep(3)
    t.point(*STRIP["left"])        # darbą: the case į takes
    time.sleep(3.5)


def braukimas(t):
    t.caption("Braukimas pirštu, diakritikai sudedami patys")
    time.sleep(2)
    for word in ["pries", "pora", "dienu", "maciau", "tavo", "mama"]:
        t.swipe(word, noise=9)
        time.sleep(0.45)
    time.sleep(2.5)
    t.point(*SEND)
    time.sleep(1)
    t.caption("Šnekamoji kalba irgi")
    for word in ["gal", "einam", "valgyti"]:
        t.swipe(word, noise=9)
        time.sleep(0.45)
    time.sleep(3.5)


def card(text, path):
    """A caption as a PNG: white on a dark rounded card, wrapped to the screen's width."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 62, index=1)
    words, lines = text.split(), [""]
    for w in words:
        trial = (lines[-1] + " " + w).strip()
        if font.getlength(trial) > 880:
            lines.append(w)
        else:
            lines[-1] = trial
    height = 60 + 80 * len(lines)
    img = Image.new("RGBA", (1000, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, 999, height - 1), 44, fill=(24, 28, 40, 235))
    for i, line in enumerate(lines):
        d.text((500, 30 + 80 * i), line, font=font, fill="white", anchor="ma")
    img.save(path)


def compose(scene, out):
    """Raw recording + captions -> DIR/final/scene.mp4 (run with Pillow available)."""
    raw = os.path.join(out, "raw", f"{scene}.mp4")
    caps = json.load(open(os.path.join(out, "raw", f"{scene}.json")))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", raw]
    graph, last = [], "0:v"
    length = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", raw],
                                  capture_output=True, text=True).stdout)
    for i, (start, text) in enumerate(caps):
        path = os.path.join(out, "raw", f"{scene}_{i}.png")
        card(text, path)
        end = caps[i + 1][0] if i + 1 < len(caps) else length
        cmd += ["-i", path]
        graph.append(f"[{last}][{i + 1}:v]overlay=40:320:enable='between(t,{start:.2f},{end:.2f})'[v{i}]")
        last = f"v{i}"
    os.makedirs(os.path.join(out, "final"), exist_ok=True)
    cmd += ["-filter_complex", ";".join(graph), "-map", f"[{last}]", "-r", "30", "-c:v", "libx264", "-crf", "20",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", os.path.join(out, "final", f"{scene}.mp4")]
    subprocess.run(cmd, check=True)


def main():
    action, *rest = sys.argv[1:]
    if action == "setup":
        setup()
        return
    if action == "compose":
        compose(rest[0], rest[1])
        return
    scene = rest[0]
    open_chat(scene)
    t = Touch(seed=2)
    t.captions = []
    if action == "record":
        out = os.path.join(rest[1], "raw")
        os.makedirs(out, exist_ok=True)
        rec = subprocess.Popen(ADB + ["shell", "screenrecord", "--bit-rate", "12000000", f"/sdcard/{scene}.mp4"])
        time.sleep(0.7)
    start = time.time()
    t.caption = lambda text: t.captions.append([time.time() - start + 0.3, text])
    globals()[scene](t)
    if action == "record":
        adb("shell", "pkill", "-INT", "screenrecord", check=False)
        rec.wait()
        time.sleep(1)
        adb("pull", f"/sdcard/{scene}.mp4", os.path.join(out, f"{scene}.mp4"))
        json.dump(t.captions, open(os.path.join(out, f"{scene}.json"), "w"), ensure_ascii=False)
    print(field())


if __name__ == "__main__":
    main()
