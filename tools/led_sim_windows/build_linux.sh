#!/bin/sh
# Linux dev build/run: host library + app (needs: gcc, python3 with pygame numpy)
set -e
cd "$(dirname "$0")"
mkdir -p build
gcc -O2 -shared -fPIC -fvisibility=hidden -Ihost/stubs -I../../firmware/mono_split/main -o build/libledhost.so host/led_host.c -lm -w
echo built build/libledhost.so
