# Sheeg Release Build

## Goal

Produce a single Windows executable for the final user-facing launcher.

Output:

- `dist\SheegLauncher.exe`

## What Gets Bundled

The release EXE bundles:

- the main session launcher logic
- the UDP-to-LSL bridge logic
- the LSL probe logic
- the LabRecorder controller logic
- `config/default.json`
- `scripts/GameScript/researchGamesLSL.exe`
- `scripts/GameScript/researchGamesLSL.pck`

## What Stays External

These still need to be installed on the Windows machine:

- CGX Acquisition
- LabRecorder

Those paths are still resolved through `config/default.json`.

## Build On Windows

From the project root:

```powershell
.\build_release.ps1
```

Or manually:

```powershell
.venv\Scripts\python.exe -m pip install pyinstaller
.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm .\SheegLauncher.spec
```

## Run

Example:

```powershell
.\dist\SheegLauncher.exe --subject-id 1
```

If `--subject-id` is omitted, the EXE prompts for it interactively.

## Notes

- This release path is intended for Windows only.
- The EXE uses subcommands internally so the bridge, probe, and recorder logic can all live inside one final binary.
- If you want a quieter operator experience later, the next step would be to add a small GUI on top of this launcher.
