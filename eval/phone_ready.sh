#!/bin/sh
# Fail fast before a phone test: the phone is connected over adb, awake and unlocked.
# Reconnects wireless adb through mDNS when no device is attached. Every adb call has a time
# limit (macOS has no `timeout`): a dropped wireless link or a locked screen otherwise makes
# adb install / input / uiautomator wait forever.
#
#   eval/phone_ready.sh && adb -s PHONE install -r app.apk   (PHONE: the non-emulator line of adb devices)
#
# Exit 0: ready. Exit 1: not ready, with the reason on stderr (unlock the phone, reconnect).

ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"
LIMIT="${PHONE_TIMEOUT:-8}"

# run with a time limit; prints nothing and fails if the limit is hit
limited() { perl -e "alarm $LIMIT; exec @ARGV" "$@"; }

# the phone, not the emulator (often running too: adb without a serial then refuses every call)
devices() { limited "$ADB" devices 2>/dev/null | awk 'NR > 1 && $2 == "device" && $1 !~ /^emulator-/ { print $1 }'; }

if [ -z "$(devices)" ]; then
    # wireless adb dropped (or the adb server restarted): reconnect to an advertised phone
    for addr in $(limited "$ADB" mdns services 2>/dev/null | awk '/_adb-tls-connect/ { print $3 }'); do
        limited "$ADB" connect "$addr" >/dev/null 2>&1
    done
fi
if [ -z "$(devices)" ]; then
    echo "phone not connected: no adb device (enable wireless debugging, or adb connect HOST:PORT)" >&2
    exit 1
fi
export ANDROID_SERIAL="${ANDROID_SERIAL:-$(devices | head -1)}"

state=$(limited "$ADB" shell 'dumpsys power | grep -m1 "mWakefulness="; dumpsys window | grep -m1 -E "isKeyguardShowing|mKeyguardShowing|mShowingLockscreen"' 2>/dev/null)
if [ -z "$state" ]; then
    echo "phone not answering within ${LIMIT}s (wireless adb stalled): reconnect it" >&2
    exit 1
fi
case "$state" in
    *mWakefulness=Awake*) ;;
    *) echo "phone screen is off (timed out): wake and unlock it" >&2; exit 1 ;;
esac
case "$state" in
    *isKeyguardShowing=true*|*mKeyguardShowing=true*|*mShowingLockscreen=true*)
        echo "phone is locked: unlock it" >&2; exit 1 ;;
esac
exit 0
