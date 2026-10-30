#!/bin/sh
# Builds the checker for the extension: extension/varnele.wasm (holds data/varnele.bin, run
# `python3 -m varnele export` first if that is missing). Then load this folder in chrome://extensions.
set -e
cd "$(dirname "$0")/.."
cargo build --release --target wasm32-unknown-unknown --manifest-path rust/Cargo.toml -p varnele-wasm
cp rust/target/wasm32-unknown-unknown/release/varnele_wasm.wasm extension/varnele.wasm
ls -la extension/varnele.wasm
