"""
Crowd Energy Meter — reads live audio from a Focusrite interface
and prints the RMS amplitude to the terminal every ~100 ms.

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crowd Energy Meter — live RMS from a Focusrite input."
    )
    parser.add_argument(
        "--list-devices", action="store_true",
        help="Show all audio devices and exit.",
    )
    parser.add_argument(
        "--device", type=int, default=None,
        help="Input device index (run --list-devices to find it).",
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
    print(f"  Print  : every {int(PRINT_INTERVAL * 1000)} ms")
    print()

    rms_accumulator: list[float] = []
    last_print = time.monotonic()

    def audio_callback(indata, frames, time_info, status):
        nonlocal last_print
        if status:
            print(f"\n  (audio warning: {status})", file=sys.stderr)

        samples = indata[:, 0]
        rms_accumulator.append(rms_amplitude(samples))

        now = time.monotonic()
        if now - last_print >= PRINT_INTERVAL:
            avg_rms = float(np.mean(rms_accumulator))
            rms_accumulator.clear()
            last_print = now
            sys.stdout.write(f"\r  RMS: {avg_rms:.6f}  ")
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
        print("\n\n  Stopped.")
    except sd.PortAudioError as e:
        print(f"\n  Could not open device {args.device}: {e}")
        print("  Make sure the Focusrite is connected and powered on.")
        sys.exit(1)


if __name__ == "__main__":
    main()
