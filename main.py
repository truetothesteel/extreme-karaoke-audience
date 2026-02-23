"""
Crowd Energy Meter — measures how loud and energetic the audience is
by listening to the microphone in real time and printing a visual bar.
"""

import sys
import numpy as np
import sounddevice as sd
from scipy.signal import welch

# ── Settings you can tweak ──────────────────────────────────────────
SAMPLE_RATE = 44100        # audio samples per second (CD quality)
BLOCK_DURATION = 0.1       # seconds of audio analysed per update
BLOCK_SIZE = int(SAMPLE_RATE * BLOCK_DURATION)
BAR_WIDTH = 40             # max width of the energy bar in characters
QUIET_DB = 40.0            # dB level that counts as "silent"
LOUD_DB = 90.0             # dB level that counts as "max energy"
ENERGY_BAND_HZ = (300, 4000)  # frequency range where crowd cheers live


def rms_db(samples: np.ndarray) -> float:
    """Return the loudness of an audio block in decibels (dB)."""
    rms = np.sqrt(np.mean(samples ** 2))
    if rms < 1e-10:
        return 0.0
    return 20 * np.log10(rms)


def band_energy_ratio(samples: np.ndarray, fs: int,
                      band: tuple[float, float]) -> float:
    """What fraction of total energy sits inside the given frequency band.

    A high ratio means the sound is dominated by crowd-cheer frequencies
    rather than low rumble or high-pitched feedback.
    """
    freqs, power = welch(samples, fs=fs, nperseg=min(len(samples), 1024))
    total = power.sum()
    if total < 1e-20:
        return 0.0
    mask = (freqs >= band[0]) & (freqs <= band[1])
    return float(power[mask].sum() / total)


def energy_score(db: float, band_ratio: float) -> float:
    """Combine loudness and spectral shape into a 0-100 energy score."""
    loudness_pct = np.clip((db - QUIET_DB) / (LOUD_DB - QUIET_DB), 0, 1)
    score = (0.7 * loudness_pct + 0.3 * band_ratio) * 100
    return round(float(score), 1)


def label_for(score: float) -> str:
    """Turn a numeric score into a human-readable vibe label."""
    if score < 15:
        return "Crickets..."
    if score < 35:
        return "Warming up"
    if score < 55:
        return "Getting into it!"
    if score < 75:
        return "Crowd is LIVE"
    return "ABSOLUTE BANGER"


def print_bar(score: float) -> None:
    """Print a single-line energy bar that updates in place."""
    filled = int(BAR_WIDTH * min(score, 100) / 100)
    bar = "#" * filled + "-" * (BAR_WIDTH - filled)
    tag = label_for(score)
    sys.stdout.write(f"\r  [{bar}] {score:5.1f}%  {tag}    ")
    sys.stdout.flush()


def audio_callback(indata, frames, time_info, status):
    """Called automatically by sounddevice for each audio block."""
    if status:
        print(f"\n  (audio warning: {status})", file=sys.stderr)

    samples = indata[:, 0]  # mono — use first channel
    db = rms_db(samples)
    ratio = band_energy_ratio(samples, SAMPLE_RATE, ENERGY_BAND_HZ)
    score = energy_score(db, ratio)
    print_bar(score)


def main():
    print("=" * 56)
    print("  CROWD ENERGY METER  —  press Ctrl+C to stop")
    print("=" * 56)
    print()

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE,
                            blocksize=BLOCK_SIZE,
                            channels=1,
                            callback=audio_callback):
            print("  Listening on default microphone ...\n")
            while True:
                sd.sleep(100)
    except KeyboardInterrupt:
        print("\n\n  Stopped. Rock on!")
    except sd.PortAudioError as e:
        print(f"\n  Could not open microphone: {e}")
        print("  Make sure a mic is connected and not in use by another app.")
        sys.exit(1)


if __name__ == "__main__":
    main()
