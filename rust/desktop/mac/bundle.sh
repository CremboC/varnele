#!/bin/sh
# Build Varnele.app into ~/Applications. Ad-hoc signed: macOS ties the Accessibility permission to
# the exact build, so after a rebuild remove Varnelė from the list and add it again (--reset does
# the removal), until the app is signed with a real certificate.
set -e
root=$(cd "$(dirname "$0")/../.." && pwd)
app="$HOME/Applications/Varnele.app"
id=dev.imbrasas.varnele.desktop

cargo build --release --manifest-path "$root/Cargo.toml" -p varnele-desktop
pkill -x varnele-desktop || true
rm -rf "$app"
mkdir -p "$app/Contents/MacOS"
cp "$root/desktop/mac/Info.plist" "$app/Contents/"
cp "$root/target/release/varnele-desktop" "$app/Contents/MacOS/"
codesign --force --sign - --identifier "$id" "$app"
if [ "$1" = "--reset" ]; then
    tccutil reset Accessibility "$id"
fi
echo "$app"
