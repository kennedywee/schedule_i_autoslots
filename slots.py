#!/usr/bin/env python3
"""Slot macro. F1 = start loop, F4 = stop loop, F5 = quit program.

Self-contained: injects input via /dev/uinput (looks like real hardware,
works in any game, X11 or Wayland) and reads hotkeys straight from
/dev/input (needs 'input' group membership, which you have).

Run:  python3 slots.py
"""
import glob
import os
import select
import struct
import threading
import time
from fcntl import ioctl

# --- knobs: trial and error, same as the original AHK script -----------
INIT_MOVE = -1900          # initial move to the first slot
MOVES = [650, 1050, 1100, 950]  # slot-to-slot distances
SLOT_DELAY = 0.2           # pause after hitting a slot
RESET_DELAY = 2.0          # wait for slots to reset each round
WALK_HOLD = 0.75           # how long to hold 's' at the start

# --- kernel input constants ---------------------------------------------
EV_SYN, EV_KEY, EV_REL = 0, 1, 2
REL_X, REL_Y = 0, 1
BTN_LEFT = 0x110  # unused, but libinput only accepts pointers that look like a real mouse
KEY_LEFTCTRL, KEY_S, KEY_E = 29, 31, 18
KEY_F1, KEY_F4, KEY_F5 = 59, 62, 63
EVENT_FMT = "qqHHi"  # struct input_event on 64-bit
EVENT_SIZE = struct.calcsize(EVENT_FMT)

def make_uinput():
    fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
    ioctl(fd, 0x40045564, EV_KEY)   # UI_SET_EVBIT
    ioctl(fd, 0x40045564, EV_REL)
    for key in (KEY_LEFTCTRL, KEY_S, KEY_E, BTN_LEFT):
        ioctl(fd, 0x40045565, key)  # UI_SET_KEYBIT
    ioctl(fd, 0x40045566, REL_X)    # UI_SET_RELBIT
    ioctl(fd, 0x40045566, REL_Y)
    # legacy struct uinput_user_dev: name[80], input_id, ff_effects_max, abs arrays
    os.write(fd, struct.pack("80sHHHHi", b"slots-macro", 0x03, 0x1234, 0x5678, 1, 0)
                 + b"\0" * (4 * 64 * 4))
    ioctl(fd, 0x5501)               # UI_DEV_CREATE
    time.sleep(2)                   # let udev/compositor pick the device up
    return fd

def emit(fd, etype, code, value):
    os.write(fd, struct.pack(EVENT_FMT, 0, 0, etype, code, value))
    os.write(fd, struct.pack(EVENT_FMT, 0, 0, EV_SYN, 0, 0))

def tap(fd, key, hold=0.05):
    emit(fd, EV_KEY, key, 1)
    time.sleep(hold)
    emit(fd, EV_KEY, key, 0)

def move_x(fd, dx):
    # chunked into small deltas like a real mouse; one giant event gets ignored/clamped
    step = 25 if dx > 0 else -25
    for _ in range(abs(dx) // 25):
        emit(fd, EV_REL, REL_X, step)
        time.sleep(0.002)
    if dx % 25:
        emit(fd, EV_REL, REL_X, dx % 25 if dx > 0 else -(abs(dx) % 25))

# --- the macro loop, runs in a thread so F4 stays responsive -------------
def macro(fd, stop):
    print("started (F4 stops)", flush=True)
    tap(fd, KEY_LEFTCTRL)
    tap(fd, KEY_S, hold=WALK_HOLD)
    move_x(fd, INIT_MOVE)
    while not stop.is_set():
        for dx in [0] + MOVES:
            move_x(fd, dx)
            tap(fd, KEY_E)
            time.sleep(0.05)
            if stop.wait(SLOT_DELAY):
                print("stopped", flush=True)
                return
        move_x(fd, -sum(MOVES))  # back to the first slot
        if stop.wait(RESET_DELAY):
            break
    print("stopped", flush=True)

def main():
    uinput = make_uinput()
    devices = [os.open(p, os.O_RDONLY | os.O_NONBLOCK)
               for p in glob.glob("/dev/input/event*")]
    stop = threading.Event()
    worker = None
    print(f"ready, watching {len(devices)} input devices. F1 start, F4 stop, F5 quit.", flush=True)
    try:
        while True:
            ready, _, _ = select.select(devices, [], [])
            for dev in ready:
                try:
                    data = os.read(dev, EVENT_SIZE * 64)
                except OSError:
                    continue
                for off in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE):
                    _, _, etype, code, value = struct.unpack_from(EVENT_FMT, data, off)
                    if etype != EV_KEY or value != 1:
                        continue
                    if code == KEY_F1 and (worker is None or not worker.is_alive()):
                        stop.clear()
                        worker = threading.Thread(target=macro, args=(uinput, stop), daemon=True)
                        worker.start()
                    elif code == KEY_F4:
                        stop.set()
                    elif code == KEY_F5:
                        print("bye", flush=True)
                        return
    finally:
        stop.set()
        ioctl(uinput, 0x5502)  # UI_DEV_DESTROY

if __name__ == "__main__":
    main()
