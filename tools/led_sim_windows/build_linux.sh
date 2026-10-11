#!/bin/sh
# Host library from the CURRENT firmware sources (+ the firmware SHA compiled in). Linux .so and Windows .dll.
set -e
cd "$(dirname "$0")"
mkdir -p build
FW=$(git -C ../.. log -1 --format=%H -- firmware/mono_split/main firmware/panel_id)
INC="-Ihost/stubs -I../../firmware/mono_split/main -I../../firmware/panel_id"
gcc -O2 -shared -fPIC -fvisibility=hidden $INC -DFW_SHA=\"$FW\" -o build/libledhost.so host/led_host.c -lm -w
x86_64-w64-mingw32-gcc -O2 -shared $INC -DFW_SHA=\"$FW\" -o build/led_host.dll host/led_host.c -lm -w -static-libgcc
echo built build/libledhost.so build/led_host.dll from firmware $FW
# bit-exact check of the simulator's 8-bit BCM/gamma duty against the firmware's own matrix_refresh.c sample stream
gcc -O1 -w -DMONO_SIM -Ihost/verify/stubs -Ihost/stubs -I../../firmware/mono_split/main -o build/verify_refresh host/verify/verify_refresh.c -Lbuild -lledhost -lm
LD_LIBRARY_PATH=build ./build/verify_refresh
