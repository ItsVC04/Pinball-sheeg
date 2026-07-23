# Sheeg Developer Notes

## Project Team and Collaborators

- Harpreet Singh, PhD student in Computational Behavioural Neuroscience,
  University of Lethbridge; Research Analyst/Consultant, JITDataInsights Lab Inc.
- Dr. Hardeep Ryait, Supervisor, University of Lethbridge
- Gurjit Singh, Director, JITDataInsights Lab Inc.
- OlaBola Balogun, tester
- Charandeep Singh, tester
- Kyra Thompson, game program coder

## Purpose

This project runs a CGX EEG acquisition workflow together with a game that must publish LSL markers so the recording session can be aligned with task events.

The current launcher is:

- `run1.ps1`

The game is currently configured as:

- `scripts/GameScript/researchGamesLSL.exe`

The launcher starts the game, probes for LSL streams, then starts LabRecorder control.

## Current Problem

CGX EEG appears to be available, but the marker stream is not being found when the game is launched as `researchGamesLSL.exe`.

This suggests one of these:

- the executable is not publishing an LSL marker stream
- the executable is publishing a marker stream with a different stream name
- the executable is publishing a marker stream with a different stream type
- the executable needs startup arguments that were previously passed to the Python game

## Required Marker Stream Contract

The game should publish an LSL stream with the following metadata:

- Stream name: `Markers`
- Stream type: `Markers`
- Channel count: `1`
- Channel format: `string`
- Nominal sample rate: `0.0`

This matches the rest of the project:

- `config/default.json` expects marker stream name `Markers`
- `scripts/lsl_probe.py` probes for the marker stream by name
- `scripts/recorder_controller.py` waits for the marker stream by name
- `scripts/markers.py` defines the expected marker outlet format

## Expected Marker Payloads

The marker stream should send one string event per sample.

Examples used by the previous Python implementation:

- `START_BUTTON:`
- `SESSION_START:`
- `TRIAL_START:`
- `STIM_DIR:LEFT`
- `RESPONSE_WINDOW:`
- `RESPONSE_KEY:RIGHT`
- `SESSION_END:`

The exact event vocabulary can evolve, but the stream should remain a single-channel string marker stream.

## Reference Python Behavior

The previous Python game implementation created the marker stream like this:

```python
info = StreamInfo(
    args.marker_stream,
    "Markers",
    1,
    0,
    "string",
    f"{args.subject}_{args.session}"
)
outlet = StreamOutlet(info)
```

It then emitted event markers as string samples.

## Important Integration Detail

Previously the game was launched as a Python script and received these arguments:

- `--session_dir`
- `--subject`
- `--session`
- `--protocol`
- `--run`
- `--marker_stream`

If `researchGamesLSL.exe` depends on any of those values to initialize its LSL outlet, the executable must either:

- support equivalent command-line arguments, or
- internally default to the required marker stream settings without needing external arguments

## What the Developer Should Verify

1. Confirm the executable creates an LSL outlet at startup.
2. Confirm the outlet name is exactly `Markers`.
3. Confirm the outlet type is exactly `Markers`.
4. Confirm the outlet uses one string channel.
5. Confirm markers are emitted during the task, not only logged locally.
6. Confirm the executable does not require missing startup arguments from the old Python flow.

## Debugging Guidance

The probe and launcher were updated to report EEG and marker detection separately.

On a failed run, check:

- `sessions/.../lsl_streams.json`
- `sessions/.../run.log`

The probe now reports:

- whether EEG was found
- whether markers were found
- the names of discovered EEG streams
- the names of discovered marker streams

## Recommended Fix

The executable should publish:

- name `Markers`
- type `Markers`
- string payload events

If that is not possible, then the launcher and probe configuration must be updated to match the actual stream name and stream metadata emitted by the executable.

## License

Sheeg source code and project documentation are released under the MIT License.
See `LICENSE` for terms and `NOTICE.md` for notes about external tools,
bundled binaries, generated artifacts, and research data responsibilities.
