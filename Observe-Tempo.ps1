param(
    [ValidateRange(1, 3600)]
    [int]$Seconds = 180
)
$ErrorActionPreference = 'Stop'
$targets = @(Get-Process -Name rekordbox -ErrorAction SilentlyContinue)
if ($targets.Count -ne 1) {
    throw 'Start exactly one instance of Rekordbox and select PERFORMANCE mode.'
}
$resultPath = Join-Path $PSScriptRoot ('artifacts\observation-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '.jsonl')
Write-Host 'Read-only observation. Load a track and move the GUI tempo fader; test hardware faders if connected.'
Write-Host "Log: $resultPath"
& python (Join-Path $PSScriptRoot 'tools\observe_tempo.py') --pid $targets[0].Id --seconds $Seconds --output $resultPath
if ($LASTEXITCODE -ne 0) { throw "Observation failed (exit $LASTEXITCODE)." }
