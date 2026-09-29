param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('Install','Restore','Check')][string]$Action,
    [string]$Exe
)
$ErrorActionPreference = 'Stop'
try {
    if (-not [Environment]::Is64BitOperatingSystem) {
        throw 'This package requires Windows x64.'
    }
    if ($Action -ne 'Check' -and (Get-Process -Name rekordbox -ErrorAction SilentlyContinue)) {
        throw 'Close Rekordbox normally, then run Setup again.'
    }
    if (-not $Exe) {
        Add-Type -AssemblyName System.Windows.Forms
        $picker = New-Object System.Windows.Forms.OpenFileDialog
        try {
            $picker.Title = 'RB PLUS: select your installed rekordbox.exe (7.2.18)'
            $picker.Filter = 'Rekordbox (rekordbox.exe)|rekordbox.exe'
            $picker.InitialDirectory = $env:ProgramFiles
            if ($picker.ShowDialog() -ne 'OK') { exit 0 }
            $Exe = $picker.FileName
        } finally {
            $picker.Dispose()
        }
    }
    if ($Action -ne 'Check' -and (Get-Process -Name rekordbox -ErrorAction SilentlyContinue)) {
        throw 'Close Rekordbox normally, then run Setup again.'
    }
    & (Join-Path $PSScriptRoot 'runtime\python.exe') -I -B `
        (Join-Path $PSScriptRoot 'tools\release_patch.py') $Action.ToLowerInvariant() --exe $Exe
    if ($LASTEXITCODE -ne 0) {
        throw 'Operation failed. If access was denied, right-click the CMD file and run it as administrator.'
    }
} catch {
    Write-Host ('ERROR: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
exit 0
