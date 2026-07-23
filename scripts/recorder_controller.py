from __future__ import annotations

import argparse
import json
import socket
import time
from pathlib import Path

from pylsl import resolve_byprop


def find_streams(name: str, stream_type: str = "") -> list:
    exact_matches = resolve_byprop("name", name, timeout=0.5)
    if exact_matches:
        return exact_matches
    if stream_type:
        return resolve_byprop("type", stream_type, timeout=0.5)
    return []


def wait_for_stream(name: str, wait_sec: int, stream_type: str = "") -> bool:
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        streams = find_streams(name, stream_type)
        if streams:
            return True
        time.sleep(0.2)
    return False


def write_status(path: Path | None, **payload: object) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def send_cmd(host: str, port: int, cmd: str, connect_timeout: float = 5.0) -> None:
    with socket.create_connection((host, port), timeout=connect_timeout) as sock:
        sock.sendall((cmd.strip() + "\n").encode("utf-8"))


def wait_for_rcs(host: str, port: int, wait_sec: int) -> bool:
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        try:
            send_cmd(host, port, "update", connect_timeout=2.0)
            return True
        except OSError:
            time.sleep(0.5)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session_dir", required=True)
    ap.add_argument("--stop_file", required=True)
    ap.add_argument("--xdf", required=True)
    ap.add_argument("--status_file", default="")

    ap.add_argument("--markers_name", required=True)
    ap.add_argument("--eeg_name", required=True)
    ap.add_argument("--markers_type", default="Markers")
    ap.add_argument("--eeg_type", default="EEG")
    ap.add_argument("--wait_sec", type=int, default=30)

    ap.add_argument("--rcs_host", default="127.0.0.1")
    ap.add_argument("--rcs_port", type=int, default=22345)

    ap.add_argument("--participant", required=True)
    ap.add_argument("--session", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--task", required=True)

    args, unknown_args = ap.parse_known_args()

    session_dir = Path(args.session_dir)
    stop_file = Path(args.stop_file)
    xdf_path = Path(args.xdf)
    status_file = Path(args.status_file) if args.status_file else None
    session_dir.mkdir(parents=True, exist_ok=True)
    xdf_path.parent.mkdir(parents=True, exist_ok=True)

    write_status(
        status_file,
        stage="starting",
        eeg_name=args.eeg_name,
        markers_name=args.markers_name,
        eeg_type=args.eeg_type,
        markers_type=args.markers_type,
        ignored_args=unknown_args,
        xdf=str(xdf_path),
    )

    if unknown_args:
        print(f"Ignoring unknown args: {unknown_args}")

    if stop_file.exists():
        stop_file.unlink()

    if not wait_for_stream(args.markers_name, args.wait_sec, args.markers_type):
        write_status(status_file, stage="failed", error=f"Markers stream not found: {args.markers_name}")
        raise SystemExit(f"Markers stream not found: {args.markers_name}")
    if not wait_for_stream(args.eeg_name, args.wait_sec, args.eeg_type):
        write_status(status_file, stage="failed", error=f"EEG stream not found: {args.eeg_name}")
        raise SystemExit(f"EEG stream not found: {args.eeg_name}")

    if not wait_for_rcs(args.rcs_host, args.rcs_port, args.wait_sec):
        write_status(
            status_file,
            stage="failed",
            error=f"LabRecorder RCS not reachable at {args.rcs_host}:{args.rcs_port}",
        )
        raise SystemExit(f"LabRecorder RCS not reachable at {args.rcs_host}:{args.rcs_port}")

    root = str(xdf_path.parent)
    if not root.endswith("\\"):
        root = root + "\\"
    template = xdf_path.name

    write_status(status_file, stage="arming", xdf=str(xdf_path))
    send_cmd(args.rcs_host, args.rcs_port, "select all")
    send_cmd(
        args.rcs_host, args.rcs_port,
        f"filename {{root:{root}}} "
        f"{{template:{template}}} "
        f"{{participant:{args.participant}}} "
        f"{{session:{args.session}}} "
        f"{{run:{args.run}}} "
        f"{{task:{args.task}}} "
        f"{{modality:eeg}}"
    )
    send_cmd(args.rcs_host, args.rcs_port, "update")
    send_cmd(args.rcs_host, args.rcs_port, "start")
    write_status(status_file, stage="recording", xdf=str(xdf_path))

    while True:
        if stop_file.exists():
            break
        time.sleep(0.25)

    write_status(status_file, stage="stopping", xdf=str(xdf_path))
    send_cmd(args.rcs_host, args.rcs_port, "stop")
    write_status(status_file, stage="stopped", xdf=str(xdf_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
