param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('Install','Default','0.1','1','Status','Stop')]
    [string]$Step
)
$ErrorActionPreference = 'Stop'
$targets = @(Get-Process -Name rekordbox -ErrorAction SilentlyContinue)
if ($targets.Count -ne 1) { throw 'Bitte genau eine Rekordbox-Instanz starten.' }
if ($Step -in @('Install','0.1','1')) {
    Add-Type -AssemblyName UIAutomationClient
    Add-Type -AssemblyName UIAutomationTypes
    $processCondition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty,$targets[0].Id)
    $windows = [System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,$processCondition)
    $condition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,'PERFORMANCE')
    if (-not ($windows | Where-Object { $_.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$condition) })) {
        throw 'PERFORMANCE-Modus wurde nicht erkannt. Bitte Einstellungen und offene BPM-Eingaben schliessen oder direkt das eingebettete Einstellungsfeld verwenden.'
    }
}
$action = @{Install='install';Default='default';'0.1'='tenth';'1'='integer';Status='status';Stop='stop'}[$Step]
$result = & python (Join-Path $PSScriptRoot 'tools\tempo_control.py') --pid $targets[0].Id $action
if ($LASTEXITCODE -ne 0) { throw "Tempo-Steuerung fehlgeschlagen (Exit $LASTEXITCODE)." }
$result
if ($Step -in @('Default','0.1','1','Stop')) {
    $state = $result -join "`n" | ConvertFrom-Json
    if ($state.permanent) {
        Write-Host 'Auswahl gespeichert. Bereits erfasste Decks wurden zur Tempo-Neuberechnung aufgefordert.'
    } else {
        Write-Host 'Die Auswahl greift bei der naechsten Tempo-Eingabe. Bereits gesetztes Tempo bleibt bis dahin erhalten.'
    }
}
