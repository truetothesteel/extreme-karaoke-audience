"""
Crowd Energy Meter — reads live audio from a Focusrite interface,
auto-calibrates to the room's noise floor, and prints a Hype Score
from 0 (silence) to 100 (peak crowd energy).

QUICK START
-----------
1.  pip install -r requirements.txt
2.  python main.py --list-devices      (find your Focusrite device number)
3.  python main.py --device 5          (replace 5 with your number)
"""

import sys
import time
import argparse
import numpy as np
import sounddevice as sd

# ── Audio settings ──────────────────────────────────────────────────
SAMPLE_RATE = 44100   # Hz
BLOCK_SIZE = 1024     # samples per chunk
PRINT_INTERVAL = 0.1  # seconds between terminal updates

# ── Calibration & scoring ───────────────────────────────────────────
CALIBRATION_SECONDS = 5    # how long to listen for the noise floor
PEAK_OFFSET_DB = 40.0      # dB above the noise floor that maps to 100

# ── Bar display ─────────────────────────────────────────────────────
BAR_WIDTH = 50
GREEN_CEIL = 40.0    # scores below this are green
YELLOW_CEIL = 70.0   # scores below this (but >= green) are yellow; above is red

# ANSI escape codes
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def list_devices() -> None:
    """Print every audio device the system can see, then exit."""
    print("\nAvailable audio devices:\n")
    print(sd.query_devices())
    print(
        "\nLook for your Focusrite interface in the list above.\n"
        "The number on the left is the device index.\n"
        "Pass it with:  python main.py --device <number>\n"
    )


def rms_amplitude(samples: np.ndarray) -> float:
    """Root-mean-square amplitude of an audio buffer (linear, 0.0–1.0)."""
    return float(np.sqrt(np.mean(samples ** 2)))


def rms_to_db(rms: float) -> float:
    """Convert a linear RMS value to decibels (dBFS)."""
    if rms < 1e-10:
        return -100.0
    return 20.0 * np.log10(rms)


def hype_score(current_db: float, floor_db: float, ceiling_db: float) -> float:
    """Map a dB reading to a 0–100 score, clamped at both ends."""
    if ceiling_db <= floor_db:
        return 0.0
    raw = (current_db - floor_db) / (ceiling_db - floor_db) * 100.0
    return float(np.clip(raw, 0.0, 100.0))


def _zone_color(score: float) -> str:
    """Return the ANSI color code for the current hype zone."""
    if score < GREEN_CEIL:
        return _GREEN
    if score < YELLOW_CEIL:
        return _YELLOW
    return _RED


def _zone_label(score: float) -> str:
    """A short text tag for the current hype zone."""
    if score < GREEN_CEIL:
        return "Chill"
    if score < YELLOW_CEIL:
        return "Hyped"
    return "PEAK!"


def render_bar(score: float) -> str:
    """Build a color-coded bar string.

    Each filled block is colored according to the zone it falls in:
      positions 0–39 %  → green
      positions 40–69 % → yellow
      positions 70–100% → red
    """
    filled = int(BAR_WIDTH * score / 100.0)
    green_end = int(BAR_WIDTH * GREEN_CEIL / 100.0)
    yellow_end = int(BAR_WIDTH * YELLOW_CEIL / 100.0)

    bar = ""
    for i in range(BAR_WIDTH):
        if i < filled:
            if i < green_end:
                color = _GREEN
            elif i < yellow_end:
                color = _YELLOW
            else:
                color = _RED
            bar += f"{color}{_BOLD}\u2588{_RESET}"
        else:
            bar += f"{_DIM}-{_RESET}"

    zone_color = _zone_color(score)
    label = _zone_label(score)
    return f"  {bar}  {zone_color}{_BOLD}{score:5.1f}{_RESET}  {zone_color}{label}{_RESET}"


def calibrate(device: int) -> float:
    """Record for CALIBRATION_SECONDS and return the average RMS as dBFS."""
    rms_values: list[float] = []

    def cal_callback(indata, frames, time_info, status):
        rms_values.append(rms_amplitude(indata[:, 0]))

    print(f"  Calibrating noise floor — keep the room at its normal idle level …")
    with sd.InputStream(
        device=device,
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        channels=1,
        callback=cal_callback,
    ):
        for remaining in range(CALIBRATION_SECONDS, 0, -1):
            sys.stdout.write(f"\r  {remaining} …  ")
            sys.stdout.flush()
            sd.sleep(1000)

    avg_rms = float(np.mean(rms_values))
    floor_db = rms_to_db(avg_rms)
    print(f"\r  Noise floor locked at {floor_db:+.1f} dBFS (RMS {avg_rms:.6f})")
    return floor_db


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crowd Energy Meter — Hype Score from a Focusrite input."
    )
    parser.add_argument(
        "--list-devices", action="store_true",
        help="Show all audio devices and exit.",
    )
    parser.add_argument(
        "--device", type=int, default=None,
        help="Input device index (run --list-devices to find it).",
    )
    parser.add_argument(
        "--peak-offset", type=float, default=PEAK_OFFSET_DB,
        help="dB above the noise floor that equals Hype 100 (default: 40).",
    )
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        return

    if args.device is None:
        print(
            "ERROR: No device specified.\n"
            "Run  python main.py --list-devices  to see available devices,\n"
            "then  python main.py --device <number>  to start.\n"
        )
        sys.exit(1)

    device_info = sd.query_devices(args.device)
    device_name = device_info["name"]
    max_channels = device_info["max_input_channels"]
    if max_channels < 1:
        print(f"ERROR: Device {args.device} ({device_name}) has no input channels.")
        sys.exit(1)

    print("=" * 58)
    print("  CROWD ENERGY METER  —  press Ctrl+C to stop")
    print("=" * 58)
    print(f"  Device : [{args.device}] {device_name}")
    print(f"  Rate   : {SAMPLE_RATE} Hz")
    print(f"  Block  : {BLOCK_SIZE} samples")
    print()

    # ── Phase 1: calibrate ──────────────────────────────────────────
    try:
        floor_db = calibrate(args.device)
    except sd.PortAudioError as e:
        print(f"\n  Could not open device {args.device}: {e}")
        print("  Make sure the Focusrite is connected and powered on.")
        sys.exit(1)

    ceiling_db = floor_db + args.peak_offset
    print(f"  Hype 100 ceiling at {ceiling_db:+.1f} dBFS "
          f"(floor + {args.peak_offset:.0f} dB)")
    print()

    # ── Phase 2: live metering ──────────────────────────────────────
    rms_accumulator: list[float] = []
    last_print = time.monotonic()

    def audio_callback(indata, frames, time_info, status):
        nonlocal last_print
        if status:
            print(f"\n  (audio warning: {status})", file=sys.stderr)

        rms_accumulator.append(rms_amplitude(indata[:, 0]))

        now = time.monotonic()
        if now - last_print >= PRINT_INTERVAL:
            avg_rms = float(np.mean(rms_accumulator))
            rms_accumulator.clear()
            last_print = now

            db = rms_to_db(avg_rms)
            score = hype_score(db, floor_db, ceiling_db)
            sys.stdout.write(f"\r{render_bar(score)}   ")
            sys.stdout.flush()

    try:
        with sd.InputStream(
            device=args.device,
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            channels=1,
            callback=audio_callback,
        ):
            print("  Listening …\n")
            while True:
                sd.sleep(50)
    except KeyboardInterrupt:
        print("\n\n  Stopped. Rock on!")
    except sd.PortAudioError as e:
        print(f"\n  Could not open device {args.device}: {e}")
        print("  Make sure the Focusrite is connected and powered on.")
        sys.exit(1)


if __name__ == "__main__":
    main()
