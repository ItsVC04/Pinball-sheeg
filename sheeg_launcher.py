from __future__ import annotations

import argparse
import ctypes
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from pylsl import StreamInfo, StreamOutlet, resolve_byprop


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def launcher_script_path() -> Path:
    return Path(__file__).resolve()


def ensure_windows() -> None:
    if os.name != "nt":
        raise RuntimeError("This launcher supports Windows only.")


def assert_path(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def assert_value(value: str, label: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{label} is missing or empty.")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def resolve_config_path(root: Path, configured_path: str) -> Path | None:
    expanded = os.path.expandvars(configured_path or "")
    if not expanded:
        return None
    path = Path(expanded)
    if path.is_absolute():
        return path
    return root / path


def resolve_preferred_path(
    root: Path,
    configured_path: str,
    env_var_name: str = "",
    candidates: list[str] | None = None,
    label: str = "Path",
) -> Path:
    if env_var_name:
        env_value = os.environ.get(env_var_name, "")
        if env_value:
            env_path = resolve_config_path(root, env_value)
            if env_path and env_path.exists():
                return env_path

    direct_path = resolve_config_path(root, configured_path)
    if direct_path is not None and direct_path.exists():
        return direct_path

    for candidate in candidates or []:
        candidate_path = resolve_config_path(root, candidate)
        if candidate_path is not None and candidate_path.exists():
            return candidate_path

    details = []
    if env_var_name:
        details.append(f"environment variable '{env_var_name}'")
    if configured_path:
        details.append(f"configured path '{configured_path}'")
    if candidates:
        details.append(f"candidates: {', '.join(candidates)}")
    raise FileNotFoundError(f"{label} could not be resolved. Checked {'; '.join(details)}")


def resolve_runtime_python(root: Path, config: dict) -> Path:
    if is_frozen():
        return Path(sys.executable)
    return resolve_preferred_path(
        root,
        config["python"]["exeWin"],
        config["python"].get("envVar", ""),
        [],
        "Python interpreter",
    )


def launcher_command(python_exe: Path, subcommand: str, *extra_args: str) -> list[str]:
    if is_frozen():
        return [str(python_exe), subcommand, *extra_args]
    return [str(python_exe), str(launcher_script_path()), subcommand, *extra_args]


def stop_process_safe(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    if proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def get_exit_code_or_default(proc: subprocess.Popen | None, default_code: int = -1) -> int:
    if proc is None:
        return default_code
    code = proc.poll()
    return default_code if code is None else code


def start_windows_process(path: Path, cwd: Path, elevate: bool = False) -> subprocess.Popen | None:
    if not elevate:
        return subprocess.Popen([str(path)], cwd=str(cwd))

    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        str(path),
        None,
        str(cwd),
        1,
    )
    if result <= 32:
        raise PermissionError(f"Failed to elevate process launch for: {path}")
    return None


def write_summary(session_dir: Path, start_time: float, exit_code: int, xdf_path: Path, extra: dict | None = None) -> None:
    payload = {
        "ended_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_s": int(time.time() - start_time),
        "exit_code": exit_code,
        "xdf_path": str(xdf_path),
    }
    if extra:
        payload.update(extra)
    write_json(session_dir / "summary.json", payload)


def stream_info(stream: StreamInfo) -> dict:
    return {
        "name": stream.name(),
        "type": stream.type(),
        "source_id": stream.source_id(),
        "channels": stream.channel_count(),
        "sample_rate": stream.nominal_srate(),
    }


BRIDGE_DEFAULT_STREAM_NAME = "MarkerStream"
BRIDGE_DEFAULT_STREAM_TYPE = "Markers"
BRIDGE_DEFAULT_SOURCE_ID = "godot_udp"


def find_eeg_streams(expected_name: str | None) -> list[StreamInfo]:
    streams = resolve_byprop("type", "EEG", timeout=1.0)
    filtered = [s for s in streams if "CGX" in s.name() or "Cognionics" in s.name()]
    if expected_name:
        exact_matches = [s for s in filtered if s.name() == expected_name]
        if exact_matches:
            return exact_matches
    return filtered


def find_marker_streams(expected_name: str) -> list[StreamInfo]:
    exact_matches = resolve_byprop("name", expected_name, timeout=0.5)
    if exact_matches:
        return exact_matches
    type_matches = resolve_byprop("type", BRIDGE_DEFAULT_STREAM_TYPE, timeout=0.5)
    preferred = [
        s for s in type_matches
        if s.name() in {expected_name, BRIDGE_DEFAULT_STREAM_NAME} or s.source_id() == BRIDGE_DEFAULT_SOURCE_ID
    ]
    return preferred or type_matches


def cmd_bridge(args: argparse.Namespace) -> int:
    info = StreamInfo(
        name=args.stream_name,
        type=args.stream_type,
        channel_count=1,
        nominal_srate=0.0,
        channel_format="string",
        source_id=args.source_id,
    )
    outlet = StreamOutlet(info)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))
    print(f"Listening on {args.host}:{args.port} and publishing LSL stream '{args.stream_name}'...")
    while True:
        data, _addr = sock.recvfrom(4096)
        if not data:
            continue
        raw = data.decode("utf-8").strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            print(f"Skipping invalid JSON payload: {raw!r}")
            continue
        marker = str(msg.get("marker", "unknown"))
        outlet.push_sample([marker])
        print(f"Sent LSL marker: {marker}")


def cmd_probe(args: argparse.Namespace) -> int:
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
        "status": {"eeg_found": eeg_found, "markers_found": markers_found},
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
            "eeg": [stream_info(s) for s in eeg_streams],
            "markers": [stream_info(s) for s in marker_streams],
        },
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_path, report)
    print(f"EEG found: {'yes' if eeg_found else 'no'}")
    for i, s in enumerate(eeg_streams, 1):
        print(f"  EEG[{i}] {s.name()} | {s.channel_count()} ch | {s.nominal_srate()} Hz")
    print(f"Markers found: {'yes' if markers_found else 'no'}")
    for i, s in enumerate(marker_streams, 1):
        print(f"  Marker[{i}] {s.name()} | type={s.type()} | source_id={s.source_id()}")
    if not marker_streams:
        print(
            f"  No marker stream matched. Expected '{args.markers}', bridge may publish "
            f"'{BRIDGE_DEFAULT_STREAM_NAME}' with source_id '{BRIDGE_DEFAULT_SOURCE_ID}'."
        )
    if not ok:
        print("Required LSL streams were not detected before timeout.")
        return 1
    return 0


def find_streams(name: str, stream_type: str = "") -> list[StreamInfo]:
    exact_matches = resolve_byprop("name", name, timeout=0.5)
    if exact_matches:
        return exact_matches
    if stream_type:
        return resolve_byprop("type", stream_type, timeout=0.5)
    return []


def wait_for_stream(name: str, wait_sec: int, stream_type: str = "") -> bool:
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        if find_streams(name, stream_type):
            return True
        time.sleep(0.2)
    return False


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


def cmd_recorder(args: argparse.Namespace) -> int:
    session_dir = Path(args.session_dir)
    stop_file = Path(args.stop_file)
    xdf_path = Path(args.xdf)
    session_dir.mkdir(parents=True, exist_ok=True)
    xdf_path.parent.mkdir(parents=True, exist_ok=True)
    if stop_file.exists():
        stop_file.unlink()
    if not wait_for_stream(args.markers_name, args.wait_sec, args.markers_type):
        raise SystemExit(f"Markers stream not found: {args.markers_name}")
    if not wait_for_stream(args.eeg_name, args.wait_sec, args.eeg_type):
        raise SystemExit(f"EEG stream not found: {args.eeg_name}")
    if not wait_for_rcs(args.rcs_host, args.rcs_port, args.wait_sec):
        raise SystemExit(f"LabRecorder RCS not reachable at {args.rcs_host}:{args.rcs_port}")
    root = str(xdf_path.parent)
    if not root.endswith("\\"):
        root += "\\"
    send_cmd(args.rcs_host, args.rcs_port, "select all")
    send_cmd(
        args.rcs_host,
        args.rcs_port,
        f"filename {{root:{root}}} "
        f"{{template:{xdf_path.name}}} "
        f"{{participant:{args.participant}}} "
        f"{{session:{args.session}}} "
        f"{{run:{args.run}}} "
        f"{{task:{args.task}}} "
        f"{{modality:eeg}}",
    )
    send_cmd(args.rcs_host, args.rcs_port, "update")
    send_cmd(args.rcs_host, args.rcs_port, "start")
    while True:
        if stop_file.exists():
            break
        time.sleep(0.25)
    send_cmd(args.rcs_host, args.rcs_port, "stop")
    return 0


def get_probe_failure_message(lsl_data: dict) -> str:
    status = lsl_data.get("status", {})
    eeg_found = bool(status.get("eeg_found"))
    markers_found = bool(status.get("markers_found"))
    if eeg_found and not markers_found:
        return "EEG stream was detected, but the marker stream was not found."
    if not eeg_found and markers_found:
        return "Marker stream was detected, but the EEG stream was not found."
    if not eeg_found and not markers_found:
        return "Neither EEG nor marker streams were detected."
    return "LSL probe reported failure for an unknown reason."


def prompt_if_missing(value: str | None, label: str) -> str:
    if value:
        return value
    return input(f"{label}: ").strip()


def cmd_main(args: argparse.Namespace) -> int:
    ensure_windows()
    root = app_root()
    config_path = resolve_config_path(root, args.config_path or "config/default.json")
    assert_path(config_path, "Config")
    config = read_json(config_path)
    protocol = config["protocol"]
    assert_value(protocol, "config.protocol")

    subject_id = prompt_if_missing(args.subject_id, "SubjectId")
    run = args.run or "01"
    session_id = args.session_id or time.strftime("%Y%m%d_%H%M%S")
    output_root = resolve_config_path(root, config["outputRoot"])
    session_dir = output_root / f"sub_{subject_id}" / f"ses_{session_id}"
    session_dir.mkdir(parents=True, exist_ok=True)

    python_exe = resolve_runtime_python(root, config)
    game_exe = resolve_preferred_path(root, config["scripts"]["gameApp"], "", [], "Game launcher")
    lab_exe = resolve_preferred_path(
        root,
        config["windows"]["labRecorderExePath"],
        config["windows"].get("labRecorderExeEnvVar", ""),
        config["windows"].get("labRecorderExeCandidates", []),
        "LabRecorder GUI",
    ) if config["windows"]["enableLabRecorder"] else None
    cgx_exe = None
    if config["windows"]["enableStartCgx"]:
        cgx_exe = resolve_preferred_path(
            root,
            config["windows"]["cgxExePath"],
            config["windows"].get("cgxExeEnvVar", ""),
            config["windows"].get("cgxExeCandidates", []),
            "CGX Acquisition EXE",
        )
    xdf_path = session_dir / f"recording_{protocol}_{subject_id}_{run}.xdf"
    stop_file = session_dir / "STOP"
    start_time = time.time()
    game_proc = rec_proc = lab_proc = cgx_proc = bridge_proc = None
    write_json(
        session_dir / "manifest.json",
        {
            "subject": subject_id,
            "protocol": protocol,
            "run": run,
            "session_id": session_id,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "output_dir": str(session_dir),
            "xdf_path": str(xdf_path),
        },
    )
    try:
        if cgx_exe:
            print("Starting CGX Acquisition...")
            try:
                cgx_proc = start_windows_process(cgx_exe, cgx_exe.parent, elevate=False)
            except PermissionError:
                print("CGX launch needs elevation. Retrying with Windows UAC prompt...")
                cgx_proc = start_windows_process(cgx_exe, cgx_exe.parent, elevate=True)
            print(f"Waiting {config['windows']['preRollSec']} seconds for CGX dongle...")
            time.sleep(int(config["windows"]["preRollSec"]))

        print("Starting game LSL bridge...")
        bridge_proc = subprocess.Popen(launcher_command(python_exe, "bridge"), cwd=str(root))
        time.sleep(2)
        if bridge_proc.poll() is not None:
            raise RuntimeError(f"bridge exited immediately with code {bridge_proc.returncode}.")

        print("Starting game...")
        game_proc = subprocess.Popen([str(game_exe)], cwd=str(game_exe.parent))
        time.sleep(2)
        if game_proc.poll() is not None:
            raise RuntimeError(f"Game exited immediately with code {game_proc.returncode}.")

        input("\nGame window should now be visible.\nPress ENTER once the game has started successfully...")
        if game_proc.poll() is not None:
            raise RuntimeError(f"Game exited before acquisition started. Exit code: {game_proc.returncode}")

        lsl_out = session_dir / "lsl_streams.json"
        print("Searching for EEG and marker streams...")
        probe_cmd = launcher_command(
            python_exe,
            "probe",
            "--timeout", str(int(config["lsl"]["streamWaitSec"])),
            "--expected-eeg-name", config["lsl"]["expectedEegStreamName"],
            "--require_eeg",
            "--markers", config["lsl"]["expectedMarkerStreamName"],
            "--require_markers",
            "--out", str(lsl_out),
        )
        probe_result = subprocess.run(probe_cmd, cwd=str(root))
        lsl_data = read_json(lsl_out)
        if probe_result.returncode != 0 or not lsl_data.get("ok"):
            raise RuntimeError(get_probe_failure_message(lsl_data))

        eeg_name = lsl_data["found"]["eeg"][0]["name"]
        marker_name = lsl_data["found"]["markers"][0]["name"]
        print(f"EEG stream: {eeg_name}")
        print(f"Marker stream: {marker_name}")

        if lab_exe:
            print("Starting LabRecorder GUI...")
            lab_proc = subprocess.Popen([str(lab_exe)], cwd=str(session_dir))
            time.sleep(2)
            if lab_proc.poll() is not None:
                raise RuntimeError(f"LabRecorder exited immediately with code {lab_proc.returncode}.")
            input(
                f"In LabRecorder, select streams:\n"
                f"     EEG -> {eeg_name}\n"
                f"     Marker -> {marker_name}\n"
                f"     Output folder -> {session_dir}\n"
                f"Press ENTER once recording has started in LabRecorder..."
            )

        print("Starting recorder controller...")
        rec_cmd = launcher_command(
            python_exe,
            "recorder",
            "--session_dir", str(session_dir),
            "--stop_file", str(stop_file),
            "--xdf", str(xdf_path),
            "--markers_name", marker_name,
            "--eeg_name", eeg_name,
            "--rcs_host", config["windows"]["rcsHost"],
            "--rcs_port", str(config["windows"]["rcsPort"]),
            "--participant", subject_id,
            "--session", session_id,
            "--run", run,
            "--task", protocol,
        )
        rec_proc = subprocess.Popen(rec_cmd, cwd=str(root))
        time.sleep(2)
        if rec_proc.poll() is not None:
            raise RuntimeError(f"Recorder controller exited immediately with code {rec_proc.returncode}.")

        game_code = game_proc.wait()
        if game_code != 0:
            raise RuntimeError(f"Game exited with code {game_code}.")
        stop_file.touch(exist_ok=True)
        try:
            rec_code = rec_proc.wait(timeout=20)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Recorder controller did not exit after STOP was signaled.") from exc
        if rec_code != 0:
            raise RuntimeError(f"Recorder controller exited with code {rec_code}.")

        write_summary(session_dir, start_time, 0, xdf_path)
        print("Session completed successfully.")
        return 0
    except Exception as exc:
        extra = {
            "error": str(exc),
            "game_exit_code": get_exit_code_or_default(game_proc),
            "recorder_exit_code": get_exit_code_or_default(rec_proc),
            "lsl_bridge_exit_code": get_exit_code_or_default(bridge_proc),
            "labrecorder_exit_code": get_exit_code_or_default(lab_proc),
        }
        write_summary(session_dir, start_time, 2, xdf_path, extra)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    finally:
        stop_file.touch(exist_ok=True)
        stop_process_safe(rec_proc)
        stop_process_safe(bridge_proc)
        stop_process_safe(game_proc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sheeg release launcher")
    subparsers = parser.add_subparsers(dest="command")

    main_parser = subparsers.add_parser("main", help="Run the full session")
    main_parser.add_argument("--subject-id", default="")
    main_parser.add_argument("--run", default="01")
    main_parser.add_argument("--session-id", default="")
    main_parser.add_argument("--config-path", default="")

    bridge = subparsers.add_parser("bridge", help="Run UDP to LSL bridge")
    bridge.add_argument("--host", default="127.0.0.1")
    bridge.add_argument("--port", type=int, default=12001)
    bridge.add_argument("--stream-name", default=BRIDGE_DEFAULT_STREAM_NAME)
    bridge.add_argument("--stream-type", default=BRIDGE_DEFAULT_STREAM_TYPE)
    bridge.add_argument("--source-id", default=BRIDGE_DEFAULT_SOURCE_ID)

    probe = subparsers.add_parser("probe", help="Probe LSL streams")
    probe.add_argument("--timeout", type=float, default=30)
    probe.add_argument("--out", required=True)
    probe.add_argument("--markers", default="Markers")
    probe.add_argument("--expected-eeg-name", default="")
    probe.add_argument("--require-markers", "--require_markers", dest="require_markers", action="store_true")
    probe.add_argument("--require-eeg", "--require_eeg", dest="require_eeg", action="store_true")

    recorder = subparsers.add_parser("recorder", help="Control LabRecorder")
    recorder.add_argument("--session_dir", required=True)
    recorder.add_argument("--stop_file", required=True)
    recorder.add_argument("--xdf", required=True)
    recorder.add_argument("--markers_name", required=True)
    recorder.add_argument("--eeg_name", required=True)
    recorder.add_argument("--markers_type", default="Markers")
    recorder.add_argument("--eeg_type", default="EEG")
    recorder.add_argument("--wait_sec", type=int, default=30)
    recorder.add_argument("--rcs_host", default="127.0.0.1")
    recorder.add_argument("--rcs_port", type=int, default=22345)
    recorder.add_argument("--participant", required=True)
    recorder.add_argument("--session", required=True)
    recorder.add_argument("--run", required=True)
    recorder.add_argument("--task", required=True)

    return parser


def main() -> int:
    parser = build_parser()
    argv = sys.argv[1:]
    if not argv or argv[0].startswith("--"):
        argv = ["main", *argv]
    args = parser.parse_args(argv)
    if args.command == "main":
        return cmd_main(args)
    if args.command == "bridge":
        return cmd_bridge(args)
    if args.command == "probe":
        return cmd_probe(args)
    if args.command == "recorder":
        return cmd_recorder(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
