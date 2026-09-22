param(
    [ValidateSet('Install','Restore')][string]$Action='Install',
    [string]$Exe='D:\Programs\rekordbox 7.2.18\rekordbox.exe'
)
$ErrorActionPreference='Stop'
if (Get-Process -Name rekordbox -ErrorAction SilentlyContinue) {
    throw 'Rekordbox vor dem Installieren oder Wiederherstellen beenden.'
}
& python (Join-Path $PSScriptRoot 'tools\patch_app.py') $Action.ToLowerInvariant() --exe $Exe
if ($LASTEXITCODE -ne 0) { throw "Dateipatch fehlgeschlagen (Exit $LASTEXITCODE)." }
