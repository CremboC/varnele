#!/bin/sh
# The default device for keyboard tests: boot the Android emulator (AVD varnele_test, Pixel 7,
# API 35 arm64) if it isn't running, wait for it, wake it, and make the debug keyboard the input
# method. With an APK argument, install it first (an install makes the system fall back to Gboard,
# so the keyboard is selected again after it).
#
#   eval/emulator_ready.sh [path/to/VarneleKlaviatura_1.0-debug.apk]
#   adb -s emulator-5554 …        # every later call, so the Fold7 (if connected) is never touched
#
# Exit 0: ready. Exit 1: not ready, with the reason on stderr.

SDK="$HOME/Library/Android/sdk"
ADB="$SDK/platform-tools/adb"
SERIAL=emulator-5554
AVD=varnele_test
IME=dev.imbrasas.varnele.keyboard.debug/helium314.keyboard.latin.LatinIME

limited() { perl -e "alarm ${LIMIT:-30}; exec @ARGV" "$@"; }
a() { limited "$ADB" -s "$SERIAL" "$@"; }
booted() { [ "$(a shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = 1 ]; }

if [ ! -x "$SDK/emulator/emulator" ]; then
    echo "no emulator: see AGENTS.md (Android emulator) for the sdkmanager/avdmanager setup" >&2
    exit 1
fi
if ! booted; then
    nohup "$SDK/emulator/emulator" -avd "$AVD" -no-snapshot -no-audio -no-boot-anim -crash-report-mode never >"${TMPDIR:-/tmp}/varnele-emulator.log" 2>&1 &
    i=0
    until booted; do
        i=$((i + 1))
        if [ $i -gt 60 ]; then echo "emulator did not boot in 5 minutes (log: ${TMPDIR:-/tmp}/varnele-emulator.log)" >&2; exit 1; fi
        perl -e 'select(undef, undef, undef, 5)'
    done
fi
a shell input keyevent 224 >/dev/null      # wake
a shell wm dismiss-keyguard >/dev/null 2>&1
if [ -n "$1" ]; then
    LIMIT=180 a install -r "$1" | tail -1 | grep -q Success || { echo "install failed: $1" >&2; exit 1; }
fi
if a shell pm list packages | grep -q "${IME%%/*}$"; then
    a shell ime enable "$IME" >/dev/null
    a shell ime set "$IME" >/dev/null
    [ "$(a shell settings get secure default_input_method | tr -d '\r')" = "$IME" ] || { echo "could not select $IME" >&2; exit 1; }
fi
echo "$SERIAL ready"
