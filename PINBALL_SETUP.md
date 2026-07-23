# Sheeg Pinball Setup

The pinball task publishes LSL markers directly. It does not need the missing
`script_lsl.py` UDP bridge.

## 1. Install the Python packages

From PowerShell in the Sheeg project folder:

```powershell
py -m pip install -r requirements-pinball.txt
```

`pylsl` 1.18 requires Python 3.9 or newer. Use the same Python interpreter that
the Sheeg launcher resolves through `.venv` or `SHEEG_PYTHON`.

## 2. Test the game by itself

```powershell
py scripts\pinball_game.py --subject TEST01 --session TEST01 --marker_stream Markers
```

The bottom of the game window should say `LSL: connected`. The session folder
contains:

- `event.csv`
- `lsl_stream.json`
- screenshots created with the `P` key

Controls:

- `Space`: launch the ball
- `Left Arrow`: left flipper
- `Right Arrow`: right flipper
- `P`: screenshot
- `Esc`: finish the session

## 3. Verify the LSL stream

While the game is open, run this in a second PowerShell window:

```powershell
py scripts\lsl_probe.py --timeout 10 --markers Markers --require_markers --out pinball_lsl_test.json
```

For this marker-only test, do not add `--require_eeg`. The report should show
`markers_found: true`, with stream name and type both equal to `Markers`.

## 4. Run the complete EEG session

Start the CGX hardware, then launch:

```powershell
.\run1.ps1 -SubjectId P001 -Run 01
```

The updated launcher starts `scripts\pinball_game.py`, verifies the CGX EEG and
`Markers` streams, and then continues into the LabRecorder workflow.

## Marker vocabulary

- `SESSION_START`
- `BALL_SPAWN`
- `BALL_LAUNCH`
- `FLIPPER_PRESS:LEFT`
- `FLIPPER_PRESS:RIGHT`
- `BUMPER_HIT:<1-5>`
- `SCORE:<total>`
- `BALL_LOST:<ball>`
- `GAME_OVER:<score>`
- `SESSION_END:<score>`
