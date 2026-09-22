param(
    [ValidateRange(1, 3600)]
    [int]$Seconds = 180
)
$ErrorActionPreference = 'Stop'
$targets = @(Get-Process -Name rekordbox -ErrorAction SilentlyContinue)
if ($targets.Count -ne 1) {
    throw 'Bitte genau eine Rekordbox-Instanz starten und PERFORMANCE aktivieren.'
}
$resultPath = Join-Path $PSScriptRoot ('artifacts\observation-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '.jsonl')
Write-Host 'Rein lesende Beobachtung. Bitte einen Track laden und den GUI-Tempo-Fader bewegen; Hardware-Fader testen, falls angeschlossen.'
Write-Host "Log: $resultPath"
& python (Join-Path $PSScriptRoot 'tools\observe_tempo.py') --pid $targets[0].Id --seconds $Seconds --output $resultPath
if ($LASTEXITCODE -ne 0) { throw "Beobachtung fehlgeschlagen (Exit $LASTEXITCODE)." }
