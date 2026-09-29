"""Synthesize the original 32-second score. Requires NumPy; no sample assets."""
from pathlib import Path
import wave
import numpy as np

SR = 48000
DURATION = 32
audio = np.zeros((SR * DURATION, 2), dtype=np.float64)


def note(start, duration, hz, gain, pan=0, pad=False):
    size = min(int(duration * SR), len(audio) - int(start * SR))
    t = np.arange(size) / SR
    attack = 1 - np.exp(-t / (0.9 if pad else 0.012))
    release = np.minimum(1, np.maximum(0, (duration - t) / (1.6 if pad else 0.5)))
    envelope = attack * release * (np.exp(-t / 2.0) if not pad else 1)
    tone = np.sin(2 * np.pi * hz * t)
    tone += 0.22 * np.sin(2 * np.pi * hz * 2 * t) * np.exp(-t / 1.6)
    if pad:
        tone += 0.3 * np.sin(2 * np.pi * (hz + 0.35) * t)
    signal = gain * tone * envelope
    left, right = np.sqrt((1 - pan) / 2), np.sqrt((1 + pan) / 2)
    offset = int(start * SR)
    audio[offset:offset + size, 0] += signal * left
    audio[offset:offset + size, 1] += signal * right


# D major / B minor / G major / D major, held softly under the typography.
for start, chord in [(0, [146.83, 220, 277.18]), (7, [123.47, 185, 246.94]),
                     (14, [98, 146.83, 185]), (20, [110, 164.81, 220]),
                     (25, [146.83, 220, 277.18, 369.99])]:
    for i, pitch in enumerate(chord):
        note(start, min(8.5, DURATION - start), pitch, 0.025, (i - 1) * 0.4, True)

# Sparse glass-like accents punctuate the scene changes.
for start, hz, pan in [(0.25, 587.33, -.3), (1.1, 880, .3),
                        (3.5, 739.99, -.2), (4.15, 880, .2),
                        (6.5, 587.33, -.3), (8.0, 493.88, .3),
                        (10.1, 440, 0), (14, 587.33, -.3),
                        (15.1, 739.99, .3), (19.5, 659.25, -.3),
                        (21.0, 880, .3), (25, 587.33, -.35),
                        (25.6, 739.99, 0), (26.2, 880, .35), (27, 1174.66, 0)]:
    note(start, 4, hz, 0.075, pan)

# A small stereo echo, then smooth boundary fades. No clipping/limiter required.
dry = audio.copy()
for seconds, gain in [(0.23, .15), (.46, .07), (.69, .035)]:
    delay = int(seconds * SR)
    audio[delay:] += dry[:-delay, ::-1] * gain
timeline = np.arange(len(audio)) / SR
audio *= (np.minimum(1, timeline / 0.4) * np.minimum(1, (DURATION - timeline) / 2.5))[:, None]
audio *= 0.38 / max(0.38, np.max(np.abs(audio)))
path = Path(__file__).resolve().parents[1] / 'public' / 'soundtrack.wav'
with wave.open(str(path), 'wb') as out:
    out.setnchannels(2)
    out.setsampwidth(2)
    out.setframerate(SR)
    out.writeframes((audio * 32767).astype('<i2').tobytes())
print(f'{path}: {DURATION}s, stereo {SR} Hz, peak {np.max(np.abs(audio)):.3f}')
