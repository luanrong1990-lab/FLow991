"""Original, deterministic soft synth bed and two-second chapter sting."""
from array import array
import math
from pathlib import Path
import sys
import wave

ROOT = Path(__file__).resolve().parent / "assets" / "audio"


def write_wave(path, samples):
    pcm = array("h", [round(max(-1, min(1, value))*32767) for value in samples])
    if sys.byteorder != "little": pcm.byteswap()
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(24000)
        output.writeframes(pcm.tobytes())


def build():
    ROOT.mkdir(parents=True, exist_ok=True)
    rate = 24000
    chords = [(130.81, 164.81, 196.00), (110.00, 130.81, 164.81),
              (87.31, 110.00, 130.81), (98.00, 123.47, 146.83)]
    bed = []
    for index in range(rate*16):
        t = index/rate; local = t % 4
        envelope = min(1, local/0.2, (4-local)/0.4)
        chord = chords[int(t//4)]
        bed.append(0.12*envelope*sum(math.sin(2*math.pi*f*t) for f in chord)/3)
    sting = []
    for index in range(rate*2):
        t = index/rate
        value = 0
        for offset, frequency in [(0, 523.25), (0.15, 659.25), (0.3, 783.99)]:
            age = t-offset
            if age >= 0:
                value += 0.075*min(1, age/0.008)*math.exp(-5*age)*math.sin(2*math.pi*frequency*age)
        sting.append(value)
    write_wave(ROOT / "channel_bed.wav", bed)
    write_wave(ROOT / "chapter_sting.wav", sting)


if __name__ == "__main__": build()
