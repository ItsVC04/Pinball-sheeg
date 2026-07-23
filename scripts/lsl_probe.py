
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from pylsl import StreamInfo, resolve_byprop

BRIDGE_DEFAULT_STREAM_NAME = "MarkerStream"
BRIDGE_DEFAULT_STREAM_TYPE = "Markers"
BRIDGE_DEFAULT_SOURCE_ID = "godot_udp"


def stream_info(stream: StreamInfo) -> dict:
    return {
        "name": stream.name(),
        "type": stream.type(),
        "source_id": stream.source_id(),
        "channels": stream.channel_count(),
        "sample_rate": stream.nominal_srate(),
    }


def find_eeg_streams(expected_name: str | None) -> list[StreamInfo]:
    streams = resolve_byprop("type", "EEG", timeout=1.0)
    filtered = [
        stream
        for stream in streams
        if "CGX" in stream.name() or "Cognionics" in stream.name()
    ]
    if expected_name:
        exact_matches = [stream for stream in filtered if stream.name() == expected_name]
        if exact_matches:
            return exact_matches
    return filtered


def find_marker_streams(expected_name: str) -> list[StreamInfo]:
    exact_matches = resolve_byprop("name", expected_name, timeout=0.5)
    if exact_matches:
        return exact_matches

    type_matches = resolve_byprop("type", BRIDGE_DEFAULT_STREAM_TYPE, timeout=0.5)
    preferred = [
        stream
        for stream in type_matches
        if stream.name() in {expected_name, BRIDGE_DEFAULT_STREAM_NAME}
        or stream.source_id() == BRIDGE_DEFAULT_SOURCE_ID
    ]
    if preferred:
        return preferred
    return type_matches


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe for CGX EEG and marker LSL streams.",
    )
    parser.add_argument("--timeout", type=float, default=30, help="Timeout in seconds")
    parser.add_argument("--out", required=True, help="Path to save JSON report")
    parser.add_argument("--markers", default="Markers", help="Expected marker stream name")
    parser.add_argument("--expected-eeg-name", default="", help="Preferred EEG stream name")
    parser.add_argument("--require_markers", action="store_true", help="Fail if marker not found")
    parser.add_argument("--require_eeg", action="store_true", help="Fail if EEG not found")
    args = parser.parse_args()

    deadline = time.time() + args.timeout
    eeg_streams: list[StreamInfo] = []
    marker_streams: list[StreamInfo] = []
    ok = False

    print("Probing LSL streams...")

    while time.time() < deadline:
        eeg_streams = find_eeg_streams(args.expected_eeg_name or None)
        marker_streams = find_marker_streams(args.markers) if args.require_markers else []

        eeg_ready = bool(eeg_streams) or not args.require_eeg
        markers_ready = bool(marker_streams) or not args.require_markers

        if eeg_ready and markers_ready:
            ok = True
            break

        time.sleep(0.25)

    eeg_found = bool(eeg_streams)
    markers_found = bool(marker_streams)

    report = {
        "ok": ok,
        "status": {
            "eeg_found": eeg_found,
            "markers_found": markers_found,
        },
        "bridge_defaults": {
            "stream_name": BRIDGE_DEFAULT_STREAM_NAME,
            "stream_type": BRIDGE_DEFAULT_STREAM_TYPE,
            "source_id": BRIDGE_DEFAULT_SOURCE_ID,
        },
        "required": {
            "eeg": args.expected_eeg_name or "type=EEG filtered to CGX/Cognionics",
            "markers": args.markers if args.require_markers else "(not required)",
        },
        "found": {
            "eeg": [stream_info(stream) for stream in eeg_streams],
            "markers": [stream_info(stream) for stream in marker_streams],
        },
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if ok:
        print(f"EEG found: {'yes' if eeg_found else 'no'}")
        if eeg_streams:
            print(f"Found {len(eeg_streams)} EEG stream(s)")
            for index, stream in enumerate(eeg_streams, 1):
                print(
                    f"  [{index}] {stream.name()} | "
                    f"{stream.channel_count()} ch | {stream.nominal_srate()} Hz"
                )
        if args.require_markers:
            print(f"Markers found: {'yes' if markers_found else 'no'}")
            if marker_streams:
                for index, stream in enumerate(marker_streams, 1):
                    print(
                        f"  [{index}] {stream.name()} | "
                        f"type={stream.type()} | source_id={stream.source_id()}"
                    )
        return 0

    print(f"EEG found: {'yes' if eeg_found else 'no'}")
    if eeg_streams:
        for index, stream in enumerate(eeg_streams, 1):
            print(
                f"  EEG[{index}] {stream.name()} | "
                f"{stream.channel_count()} ch | {stream.nominal_srate()} Hz"
            )
    print(f"Markers found: {'yes' if markers_found else 'no'}")
    if marker_streams:
        for index, stream in enumerate(marker_streams, 1):
            print(
                f"  Marker[{index}] {stream.name()} | "
                f"type={stream.type()} | source_id={stream.source_id()}"
            )
    else:
        print(
            "  No marker stream matched. "
            f"Expected name '{args.markers}', but the bridge may publish "
            f"'{BRIDGE_DEFAULT_STREAM_NAME}' with source_id '{BRIDGE_DEFAULT_SOURCE_ID}'."
        )
    print("Required LSL streams were not detected before timeout.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
