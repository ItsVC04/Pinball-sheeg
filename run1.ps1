[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SubjectId,

    [string]$Run = "01",
    [string]$SessionId = (Get-Date -Format "yyyyMMdd_HHmmss"),
    [string]$ConfigPath = ""
)

$ErrorActionPreference = "Stop"

$ROOT = if ($PSScriptRoot) { $PSScriptRoot } else { Get-Location }
if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path $ROOT "config\default.json"
}

function Assert-Path($Path, $Label) {
    if (-not (Test-Path $Path)) { throw "$Label not found: $Path" }
}

function Assert-Value($Value, $Label) {
    if ([string]::IsNullOrWhiteSpace([string]$Value)) {
        throw "$Label is missing or empty."
    }
}

function Read-Json($Path) {
    Get-Content -Raw -Path $Path | ConvertFrom-Json
}

function Write-Json($Path, $Obj) {
    $Obj | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $Path
}

function Get-EnvValue($Name) {
    if ([string]::IsNullOrWhiteSpace($Name)) {
        return ""
    }
    return [System.Environment]::GetEnvironmentVariable($Name)
}

function Expand-ConfigPath($PathValue) {
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
        return ""
    }
    return [System.Environment]::ExpandEnvironmentVariables($PathValue)
}

function Resolve-ConfigPath($RootPath, $ConfiguredPath) {
    $expanded = Expand-ConfigPath $ConfiguredPath
    if ([string]::IsNullOrWhiteSpace($expanded)) {
        return ""
    }
    if ([System.IO.Path]::IsPathRooted($expanded)) {
        return $expanded
    }
    return Join-Path $RootPath $expanded
}

function Resolve-PreferredPath($RootPath, $ConfiguredPath, $EnvVarName = "", $Candidates = @(), $Label = "Path") {
    $envPath = Resolve-ConfigPath $RootPath (Get-EnvValue $EnvVarName)
    if (-not [string]::IsNullOrWhiteSpace($envPath) -and (Test-Path $envPath)) {
        return $envPath
    }

    $directPath = Resolve-ConfigPath $RootPath $ConfiguredPath
    if (-not [string]::IsNullOrWhiteSpace($directPath) -and (Test-Path $directPath)) {
        return $directPath
    }

    foreach ($candidate in $Candidates) {
        $candidatePath = Resolve-ConfigPath $RootPath $candidate
        if (-not [string]::IsNullOrWhiteSpace($candidatePath) -and (Test-Path $candidatePath)) {
            return $candidatePath
        }
    }

    $details = @()
    if (-not [string]::IsNullOrWhiteSpace($EnvVarName)) {
        $details += "environment variable '$EnvVarName'"
    }
    if (-not [string]::IsNullOrWhiteSpace($ConfiguredPath)) {
        $details += "configured path '$ConfiguredPath'"
    }
    if ($Candidates -and $Candidates.Count -gt 0) {
        $details += "candidates: $($Candidates -join ', ')"
    }
    throw "$Label could not be resolved. Checked " + ($details -join "; ")
}

function Stop-ProcessSafe($Proc) {
    if ($Proc -and -not $Proc.HasExited) {
        try { Stop-Process -Id $Proc.Id -Force } catch {}
    }
}

function Get-ExitCodeOrDefault($Proc, $DefaultCode = -1) {
    if ($Proc -and $Proc.HasExited) {
        return $Proc.ExitCode
    }
    return $DefaultCode
}

function Write-Summary($SessionDir, $StartTime, $ExitCode, $XdfPath, $Extra = @{}) {
    $summary = @{
        ended_at   = (Get-Date).ToString("o")
        duration_s = [int]((Get-Date) - $StartTime).TotalSeconds
        exit_code  = $ExitCode
        xdf_path   = $XdfPath
    }
    foreach ($key in $Extra.Keys) {
        $summary[$key] = $Extra[$key]
    }
    Write-Json (Join-Path $SessionDir "summary.json") $summary
}

function Start-LslBridgeProcess($BridgePath, $PythonExe, $RootPath) {
    return Start-Process -PassThru -FilePath $PythonExe -WorkingDirectory $RootPath -ArgumentList @(
        $BridgePath
    )
}

function Start-GameProcess($GamePath, $PythonExe, $RootPath, $SessionDir, $SubjectId, $SessionId, $Protocol, $Run, $MarkerStreamName) {
    $extension = [System.IO.Path]::GetExtension($GamePath).ToLowerInvariant()
    if ($extension -eq ".py") {
        return Start-Process -PassThru -FilePath $PythonExe -WorkingDirectory $RootPath -ArgumentList @(
            $GamePath,
            "--session_dir", $SessionDir,
            "--subject", $SubjectId,
            "--session", $SessionId,
            "--protocol", $Protocol,
            "--run", $Run,
            "--marker_stream", $MarkerStreamName
        )
    }

    return Start-Process -PassThru -FilePath $GamePath -WorkingDirectory (Split-Path -Parent $GamePath)
}

function Get-ProbeFailureMessage($LslData) {
    $eegFound = $false
    $markersFound = $false

    if ($LslData.status) {
        $eegFound = [bool]$LslData.status.eeg_found
        $markersFound = [bool]$LslData.status.markers_found
    } else {
        $eegFound = ($LslData.found.eeg -and $LslData.found.eeg.Count -gt 0)
        $markersFound = ($LslData.found.markers -and $LslData.found.markers.Count -gt 0)
    }

    if ($eegFound -and -not $markersFound) {
        return "EEG stream was detected, but the marker stream was not found."
    }
    if (-not $eegFound -and $markersFound) {
        return "Marker stream was detected, but the EEG stream was not found."
    }
    if (-not $eegFound -and -not $markersFound) {
        return "Neither EEG nor marker streams were detected."
    }
    return "LSL probe reported failure for an unknown reason."
}

Assert-Path $ConfigPath "Config"
$config = Read-Json $ConfigPath
$protocol = $config.protocol
Assert-Value $protocol "config.protocol"

$IsWin = $env:OS -eq "Windows_NT"
if (-not $IsWin) {
    throw "run1.ps1 currently supports Windows-only acquisition tools. Please run it from Windows PowerShell."
}

$outputRoot = Resolve-ConfigPath $ROOT $config.outputRoot
$sessionDir = Join-Path $outputRoot ("sub_{0}\ses_{1}" -f $SubjectId, $SessionId)
New-Item -ItemType Directory -Force -Path $sessionDir | Out-Null

$logPath = Join-Path $sessionDir "run.log"
Start-Transcript -Path $logPath | Out-Null

$pythonExe = Resolve-PreferredPath $ROOT $config.python.exeWin $config.python.envVar @() "Python interpreter"
Assert-Path $pythonExe "Python interpreter"

$gameScript = Resolve-PreferredPath $ROOT $config.scripts.gameApp "" @() "Game launcher script"
$gameLslBridge = ""
if (-not [string]::IsNullOrWhiteSpace([string]$config.scripts.gameLslBridge)) {
    $gameLslBridge = Resolve-PreferredPath $ROOT $config.scripts.gameLslBridge "" @() "Game LSL bridge script"
}
$probeScript = Resolve-PreferredPath $ROOT $config.scripts.lslProbe "" @() "LSL probe script"
$recScript = Resolve-PreferredPath $ROOT $config.scripts.recorderController "" @() "Recorder controller script"

Assert-Path $gameScript "Game launcher"
if (-not [string]::IsNullOrWhiteSpace($gameLslBridge)) {
    Assert-Path $gameLslBridge "Game LSL bridge"
}
Assert-Path $probeScript "lsl_probe.py"
Assert-Path $recScript "recorder_controller.py"

$labRecorderExe = $null
if ($config.windows.enableLabRecorder) {
    $labRecorderExe = Resolve-PreferredPath `
        $ROOT `
        $config.windows.labRecorderExePath `
        $config.windows.labRecorderExeEnvVar `
        $config.windows.labRecorderExeCandidates `
        "LabRecorder GUI"
    Assert-Path $labRecorderExe "LabRecorder GUI"
}

$xdfPath = Join-Path $sessionDir ("recording_{0}_{1}_{2}.xdf" -f $protocol, $SubjectId, $Run)
$stopFile = Join-Path $sessionDir "STOP"
$startTime = Get-Date

try {
    Write-Json (Join-Path $sessionDir "manifest.json") @{
        subject    = $SubjectId
        protocol   = $protocol
        run        = $Run
        session_id = $SessionId
        started_at = $startTime.ToString("o")
        output_dir = $sessionDir
        xdf_path   = $xdfPath
    }

    if ($config.windows.enableStartCgx) {
        $cgxExe = Resolve-PreferredPath `
            $ROOT `
            $config.windows.cgxExePath `
            $config.windows.cgxExeEnvVar `
            $config.windows.cgxExeCandidates `
            "CGX Acquisition EXE"
        Assert-Path $cgxExe "CGX Acquisition EXE"
        Write-Host "Starting CGX Acquisition..."
        $cgxProc = Start-Process -PassThru -FilePath $cgxExe -WorkingDirectory (Split-Path -Parent $cgxExe)
        Write-Host "Waiting $($config.windows.preRollSec) seconds for CGX dongle..."
        Start-Sleep -Seconds $config.windows.preRollSec
    }

    if (-not [string]::IsNullOrWhiteSpace($gameLslBridge)) {
        Write-Host "Starting game LSL bridge..."
        $lslBridgeProc = Start-LslBridgeProcess `
            $gameLslBridge `
            $pythonExe `
            $ROOT
        Start-Sleep -Seconds 2
        if ($lslBridgeProc.HasExited) {
            throw "Game LSL bridge exited immediately with code $($lslBridgeProc.ExitCode)."
        }
    } else {
        Write-Host "Using the game's direct LSL marker outlet; no bridge required."
    }

    Write-Host "Starting game..."
    $gameProc = Start-GameProcess `
        $gameScript `
        $pythonExe `
        $ROOT `
        $sessionDir `
        $SubjectId `
        $SessionId `
        $protocol `
        $Run `
        $config.lsl.expectedMarkerStreamName
    Start-Sleep -Seconds 2
    if ($gameProc.HasExited) {
        throw "Game process exited immediately with code $($gameProc.ExitCode)."
    }

    Write-Host ""
    Write-Host "Game window should now be visible."
    Write-Host "Press ENTER once the game has started successfully..."
    Read-Host
    if ($gameProc.HasExited) {
        throw "Game process exited before acquisition started. Exit code: $($gameProc.ExitCode)"
    }

    $lslOut = Join-Path $sessionDir "lsl_streams.json"
    Write-Host "Searching for EEG and marker streams..."
    & $pythonExe $probeScript `
        --timeout ([int]$config.lsl.streamWaitSec) `
        --expected-eeg-name $config.lsl.expectedEegStreamName `
        --require_eeg `
        --markers $config.lsl.expectedMarkerStreamName `
        --require_markers `
        --out $lslOut

    $lslData = Get-Content -Raw -Path $lslOut | ConvertFrom-Json
    if (-not $lslData.ok) {
        Write-Host "Probe summary:"
        Write-Host "     EEG found -> $($lslData.status.eeg_found)"
        Write-Host "     Markers found -> $($lslData.status.markers_found)"
        if ($lslData.found.eeg) {
            foreach ($stream in $lslData.found.eeg) {
                Write-Host "     EEG stream -> $($stream.name)"
            }
        }
        if ($lslData.found.markers) {
            foreach ($stream in $lslData.found.markers) {
                Write-Host "     Marker stream -> $($stream.name)"
            }
        }
        throw (Get-ProbeFailureMessage $lslData)
    }
    if (-not $lslData.found.eeg -or $lslData.found.eeg.Count -lt 1) {
        throw "No EEG stream was available after a successful probe."
    }
    if (-not $lslData.found.markers -or $lslData.found.markers.Count -lt 1) {
        throw "No marker stream was available after a successful probe."
    }

    $eegName = $lslData.found.eeg[0].name
    $markerName = $lslData.found.markers[0].name

    Write-Host "EEG stream: $eegName"
    Write-Host "Marker stream: $markerName"

    if ($config.windows.enableLabRecorder) {
        Write-Host "Starting LabRecorder GUI..."
        $labProc = Start-Process -PassThru -FilePath $labRecorderExe -WorkingDirectory $sessionDir
        Start-Sleep -Seconds 2
        if ($labProc.HasExited) {
            throw "LabRecorder exited immediately with code $($labProc.ExitCode)."
        }

        Write-Host "In LabRecorder, select streams:"
        Write-Host "     EEG -> $eegName"
        Write-Host "     Marker -> $markerName"
        Write-Host "     Output folder -> $sessionDir"
        Write-Host "Press ENTER in PowerShell once recording has started in LabRecorder..."
        Read-Host
        if ($labProc.HasExited) {
            throw "LabRecorder closed before recording control was armed."
        }
    }

    Write-Host "Starting recorder_controller.py..."
    $recProc = Start-Process -PassThru -FilePath $pythonExe -WorkingDirectory $ROOT -ArgumentList @(
        $recScript,
        "--session_dir", $sessionDir,
        "--stop_file", $stopFile,
        "--xdf", $xdfPath,
        "--markers_name", $markerName,
        "--eeg_name", $eegName,
        "--rcs_host", $config.windows.rcsHost,
        "--rcs_port", ([string]$config.windows.rcsPort),
        "--participant", $SubjectId,
        "--session", $SessionId,
        "--run", $Run,
        "--task", $protocol
    )
    Start-Sleep -Seconds 2
    if ($recProc.HasExited) {
        throw "recorder_controller.py exited immediately with code $($recProc.ExitCode)."
    }

    Wait-Process -Id $gameProc.Id
    if ($gameProc.ExitCode -ne 0) {
        throw "Game process exited with code $($gameProc.ExitCode)."
    }

    New-Item -ItemType File -Force -Path $stopFile | Out-Null
    Wait-Process -Id $recProc.Id -Timeout 20
    if (-not $recProc.HasExited) {
        throw "recorder_controller.py did not exit after STOP was signaled."
    }
    if ($recProc.ExitCode -ne 0) {
        throw "recorder_controller.py exited with code $($recProc.ExitCode)."
    }

    Write-Summary $sessionDir $startTime 0 $xdfPath
    Write-Host "Session completed successfully."
    exit 0
}
catch {
    Write-Error $_
    $extra = @{
        error = $_.ToString()
    }
    if ($gameProc) {
        $extra["game_exit_code"] = Get-ExitCodeOrDefault $gameProc
    }
    if ($recProc) {
        $extra["recorder_exit_code"] = Get-ExitCodeOrDefault $recProc
    }
    if ($lslBridgeProc) {
        $extra["lsl_bridge_exit_code"] = Get-ExitCodeOrDefault $lslBridgeProc
    }
    if ($labProc) {
        $extra["labrecorder_exit_code"] = Get-ExitCodeOrDefault $labProc
    }
    Write-Summary $sessionDir $startTime 2 $xdfPath $extra
    exit 2
}
finally {
    if (-not (Test-Path $stopFile)) {
        try { New-Item -ItemType File -Force -Path $stopFile | Out-Null } catch {}
    }
    Stop-ProcessSafe $recProc
    Stop-ProcessSafe $lslBridgeProc
    if ($gameProc -and -not $gameProc.HasExited) {
        Stop-ProcessSafe $gameProc
    }
    try { Stop-Transcript | Out-Null } catch {}
}
