# schedule_i_auto_slots

Auto-play the slot machines in *Schedule I* on Linux. A single Python script
that walks up to the row of slots, then loops: move to each slot, press `E`,
wait for the reset, repeat.

No dependencies — it injects input through `/dev/uinput` (looks like a real
mouse/keyboard, so it works in any game, X11 or Wayland) and reads hotkeys
straight from `/dev/input`.

## Requirements

- Linux, Python 3 (stdlib only)
- Your user in the `input` group (to read `/dev/input/event*`):

  ```sh
  sudo usermod -aG input $USER   # re-login afterwards
  ```

- Write access to `/dev/uinput` (root, or a udev rule granting the `input` group access)

## Usage

Stand in front of the slots in-game, then:

```sh
python3 main.py
```

| Key | Action |
|-----|--------|
| F1  | start the loop |
| F4  | stop the loop |
| F5  | quit the program |

## Tuning

The movement values are trial-and-error and depend on your mouse sensitivity
and where you stand. Adjust the knobs at the top of `main.py`:

- `INIT_MOVE` — initial mouse move to face the first slot
- `MOVES` — slot-to-slot distances
- `SLOT_DELAY` / `RESET_DELAY` — pacing between slots and between rounds
- `WALK_HOLD` — how long to hold `s` when walking into position
