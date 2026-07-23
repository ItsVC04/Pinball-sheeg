from __future__ import annotations

import argparse
import time
from pylsl import resolve_streams, StreamInlet


def inspect_stream(info):
    print("\n" + "=" * 80)
    print(f"STREAM NAME   : {info.name()}")
    print(f"TYPE          : {info.type()}")
    print(f"SOURCE ID     : {info.source_id()}")
    print(f"CHANNELS      : {info.channel_count()}")
    print(f"SAMPLE RATE   : {info.nominal_srate()}")
    print("=" * 80)


def classify(info, sample):
    name = info.name().lower()
    typ = info.type().lower()
    ch = info.channel_count()
    rate = info.nominal_srate()

    # ---- EEG ----
    if typ == "eeg":
        return "🧠 EEG STREAM"

    if any(k in name for k in ["cgx", "cognionics", "openbci", "brainflow"]):
        return "🧠 EEG STREAM"

    if ch >= 8 and rate >= 100:
        return "🧠 POSSIBLE EEG STREAM"

    # ---- Marker Stream ----
    if typ in ["markers", "events"]:
        return "🎯 MARKER STREAM"

    if ch == 1 and rate == 0:
        return "🎯 POSSIBLE MARKER STREAM"

    if sample:
        val = str(sample[0]).upper()
        if any(k in val for k in ["START", "STOP", "GO", "HIT", "LEFT", "RIGHT"]):
            return "🎯 MARKER STREAM"

    # ---- Motion / Sensors ----
    if ch in [3, 6, 9]:
        return "📱 MOTION / IMU STREAM"

    # ---- Generic ----
    return "❓ UNKNOWN DATA STREAM"


def read_sample(info):
    try:
        inlet = StreamInlet(info, max_buflen=1)
        sample, ts = inlet.pull_sample(timeout=2.0)
        return sample
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description="Smart LSL Analyzer")
    ap.add_argument("--refresh", type=float, default=3.0)
    args = ap.parse_args()

    print("=" * 80)
    print("🔬 SMART LSL ANALYZER")
    print("Reads stream metadata + actual samples")
    print("Press CTRL + C to stop")
    print("=" * 80)

    seen = set()

    try:
        while True:
            streams = resolve_streams(wait_time=1.0)

            for s in streams:
                key = (s.name(), s.type(), s.source_id())

                if key in seen:
                    continue

                seen.add(key)

                inspect_stream(s)

                sample = read_sample(s)

                if sample is not None:
                    print(f"FIRST SAMPLE  : {sample[:10]}")
                else:
                    print("FIRST SAMPLE  : <no sample received>")

                result = classify(s, sample)
                print(f"ANALYSIS      : {result}")

            time.sleep(args.refresh)

    except KeyboardInterrupt:
        print("\n🛑 Analyzer stopped.")


if __name__ == "__main__":
    main()